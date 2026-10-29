"""concours-validator: Concours as the validator of its own Bittensor subnet.

    CONCOURS_API_KEY=ck_... concours-validator --netuid 123 --wallet owner --hotkey validator \
        --api http://127.0.0.1:8000 --project 6974713c0ea7 [--network test] [--port 8091]

Two things run side by side:

- an upload intake on --port: miners POST their submission.py signed with their hotkey (see miner.py). The code is
  kept on disk under --state, keyed by sha256. Nothing is scored yet.
- a loop every --interval seconds: read every commitment on the subnet; for each registered hotkey whose committed
  sha256 matches an uploaded file, forward it to Concours (`POST /projects/{id}/chain/submissions`). Concours scores
  it on the private holdout and promotes it only if it passes the five gates. Then read the winner back
  (`GET /projects/{id}/chain`) and set weights on chain: all weight to the miner whose code is the active version,
  or to the subnet owner's uid while no miner has won. Report state with `PUT /projects/{id}/chain/state`.

The private holdout never reaches this process or the miners: it lives in the referee image on the Concours server.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import bittensor as bt
from bittensor.wallets import verify_message

from concours_subnet.common import MAX_CODE_BYTES, code_sha, connect, parse_commitment, upload_message

log = logging.getLogger("concours.validator")


class Concours:
    """The Concours API, with an API key."""

    def __init__(self, base: str, key: str, project: str):
        self.base, self.key, self.project = base.rstrip("/"), key, project

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.base}/projects/{self.project}{path}", data=data, method=method,
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.key}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except json.JSONDecodeError:
                return e.code, {}


class State:
    """Uploaded code and what has been forwarded, under --state/<network>-<netuid>/."""

    def __init__(self, root: Path):
        self.root = root
        (root / "code").mkdir(parents=True, exist_ok=True)
        self.file = root / "forwarded.json"
        self.forwarded: dict[str, dict] = json.loads(self.file.read_text()) if self.file.exists() else {}
        self.lock = threading.Lock()

    def code_path(self, sha: str) -> Path:
        return self.root / "code" / f"{sha}.py"

    def save(self) -> None:
        with self.lock:
            self.file.write_text(json.dumps(self.forwarded, indent=1))


def intake(state: State, netuid: int, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict) -> None:
            out = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def do_POST(self):  # noqa: N802
            if self.path != "/submit":
                return self._send(404, {"error": "not found"})
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_CODE_BYTES * 2 + 4096:
                return self._send(413, {"error": "too large"})
            try:
                body = json.loads(self.rfile.read(n))
                hotkey, sha, sig, code = body["hotkey"], body["sha256"], body["signature"], body["code"].encode()
            except (json.JSONDecodeError, KeyError, AttributeError):
                return self._send(400, {"error": "expected hotkey, sha256, signature, code"})
            if len(code) > MAX_CODE_BYTES:
                return self._send(413, {"error": f"submission is over {MAX_CODE_BYTES // 1000} KB"})
            if code_sha(code) != sha:
                return self._send(400, {"error": "sha256 does not match the code"})
            if not verify_message(upload_message(netuid, sha), sig, hotkey):
                return self._send(401, {"error": "signature does not match the hotkey"})
            state.code_path(sha).write_bytes(code)
            log.info("upload %s from %s", sha[:12], hotkey)
            return self._send(202, {"sha256": sha, "next": "publish the commitment; the validator scores it on its next pass"})

        def do_GET(self):  # noqa: N802
            if self.path.startswith("/status/"):
                hk = self.path.removeprefix("/status/")
                return self._send(200, {k: v for k, v in state.forwarded.items() if v.get("hotkey") == hk})
            return self._send(200, {"ok": True, "netuid": netuid})

        def log_message(self, *args):  # quiet
            pass

    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def one_pass(sub: bt.Subtensor, api: Concours, state: State, a, my_hotkey: str) -> None:
    meta = sub.subnets.metagraph(a.netuid)
    if meta is None:
        raise SystemExit(f"netuid {a.netuid} does not exist on {a.network}")
    uid_of = {n.hotkey: n.uid for n in meta.neurons}
    # 1. forward new committed code, oldest commitment first (first to commit a hash gets it)
    commits = sorted(meta.commitments.values(), key=lambda c: c.block)
    for c in commits:
        sha = parse_commitment(c.value)
        if not sha or c.hotkey not in uid_of:
            continue
        key = f"{c.hotkey}:{sha}"
        if key in state.forwarded and state.forwarded[key].get("status") != "retry":
            continue
        path = state.code_path(sha)
        if not path.exists():
            continue  # committed but not uploaded here (or uploaded elsewhere): ignored
        code, body = api.call("POST", "/chain/submissions", {"hotkey": c.hotkey, "uid": uid_of[c.hotkey], "block": c.block, "sha256": sha,
                                                              "code": path.read_text(), "network": a.network, "netuid": a.netuid})
        if code == 409:
            log.info("round busy; %s waits for the next pass (%s)", sha[:12], body.get("detail"))
            state.forwarded[key] = {"hotkey": c.hotkey, "sha256": sha, "status": "retry"}
            break
        if code >= 300:
            log.warning("concours refused %s: %s %s", sha[:12], code, body)
            state.forwarded[key] = {"hotkey": c.hotkey, "sha256": sha, "status": "refused", "detail": body.get("detail")}
            continue
        log.info("forwarded %s from uid %s as attempt %s", sha[:12], uid_of[c.hotkey], body.get("submission_id"))
        state.forwarded[key] = {"hotkey": c.hotkey, "sha256": sha, "status": "forwarded", "submission_id": body.get("submission_id")}
        break  # one round at a time
    state.save()
    # 2. weights: winner takes all; the owner's uid holds them while no miner has won
    _, chain = api.call("GET", "/chain")
    winner = chain.get("winner_hotkey")
    owner_uid = uid_of.get(meta.owner_hotkey, uid_of.get(my_hotkey, 0))
    target = uid_of.get(winner, owner_uid) if winner else owner_uid
    weights = {target: 1.0}
    last = {int(k): v for k, v in (chain.get("weights") or {}).items()}
    report = {"network": a.network, "netuid": a.netuid, "validator_hotkey": my_hotkey, "block": meta.block, "solvers": sum(1 for n in meta.neurons if n.hotkey != my_hotkey)}
    api.call("PUT", "/chain/state", report)  # the block and solver count, before a weights call that can take a while
    if weights != last or (meta.block - (chain.get("weights_block") or 0)) >= a.weights_every:
        try:
            # a stuck RPC must not stall the loop: give up after the timeout and try again next pass
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                pool.submit(set_weights, sub, a, weights).result(timeout=a.weights_timeout)
            except FuturesTimeout as e:
                raise TimeoutError(f"no answer from the chain within {a.weights_timeout}s") from e
            finally:
                pool.shutdown(wait=False)
            report.update(weights=weights, weights_block=meta.block, note=f"weights set: uid {target}" + (" (winner)" if winner else " (owner, no winner yet)"))
            log.info("set weights %s at block %s", weights, meta.block)
        except Exception as e:  # noqa: BLE001  (chain errors, rate limit, an older runtime)
            report["note"] = f"weights not set: {e}"[:300]
            log.warning("weights not set: %s", e)
        api.call("PUT", "/chain/state", report)


def set_weights(sub: bt.Subtensor, a, weights: dict[int, float]) -> None:
    """The SDK's set_weights (handles commit-reveal, limits, rate limit). A local chain older than the SDK lacks storage
    its preview reads; there, with commit-reveal off, the plain extrinsic is submitted directly."""
    try:
        bt.set_weights(a.netuid, weights, wallet=a.wallet, network=a.network)
        return
    except bt.ChainError:
        raise
    except Exception as e:  # noqa: BLE001
        if a.network != "local" and not a.network.startswith("ws://127.0.0.1"):
            raise
        log.info("SDK weights preview unavailable on this local runtime (%s); sending the plain extrinsic", type(e).__name__)
    uids = sorted(weights)
    top = max(weights.values()) or 1.0
    vals = [int(round(weights[u] / top * 65535)) for u in uids]
    call = bt.calls.SubtensorModule.set_weights(netuid=a.netuid, dests=uids, weights=vals, version_key=0)
    res = sub.submit_call(call, a.wallet, signer="hotkey")
    if not res.success:
        raise RuntimeError(f"set_weights: {res.error}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="concours-validator", description="Run Concours as the validator of its subnet.")
    p.add_argument("--netuid", type=int, required=True)
    p.add_argument("--network", default="test", help="test | local | finney | ws://...")
    p.add_argument("--wallet", required=True)
    p.add_argument("--hotkey", required=True)
    p.add_argument("--wallet-path", help="default ~/.bittensor/wallets")
    p.add_argument("--api", default=os.environ.get("CONCOURS_URL", "http://127.0.0.1:8000"))
    p.add_argument("--project", default=os.environ.get("CONCOURS_PROJECT"), required=not os.environ.get("CONCOURS_PROJECT"))
    p.add_argument("--port", type=int, default=8091, help="miner upload intake")
    p.add_argument("--interval", type=int, default=60, help="seconds between passes")
    p.add_argument("--weights-every", type=int, default=100, help="re-set unchanged weights after this many blocks")
    p.add_argument("--weights-timeout", type=int, default=120, help="seconds to wait for a weights extrinsic")
    p.add_argument("--state", default=str(Path.home() / ".concours-subnet"))
    p.add_argument("--once", action="store_true", help="one pass, then exit")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    key = os.environ.get("CONCOURS_API_KEY")
    if not key:
        raise SystemExit("set CONCOURS_API_KEY (Account > API keys in Concours)")
    if a.wallet_path:
        os.environ["BT_WALLET_PATH"] = a.wallet_path
    from bittensor.wallet import Wallet  # noqa: PLC0415

    w = Wallet(name=a.wallet, hotkey=a.hotkey, path=a.wallet_path) if a.wallet_path else Wallet(name=a.wallet, hotkey=a.hotkey)
    my_hotkey = w.hotkey.ss58_address
    state = State(Path(a.state) / f"{a.network.replace('://', '_').replace('/', '_').replace(':', '_')}-{a.netuid}-{a.project}")
    api = Concours(a.api, key, a.project)
    srv = intake(state, a.netuid, a.port)
    log.info("validator %s on netuid %s (%s); intake on :%s; project %s", my_hotkey, a.netuid, a.network, a.port, a.project)
    sub = connect(a.network)
    a.wallet = w  # bt.set_weights accepts a Wallet
    try:
        while True:
            try:
                one_pass(sub, api, state, a, my_hotkey)
            except SystemExit:
                raise
            except Exception as e:  # noqa: BLE001  (keep validating; the next pass retries)
                log.warning("pass failed: %s: %s", type(e).__name__, e)
            if a.once:
                return 0
            time.sleep(a.interval)
    finally:
        srv.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
