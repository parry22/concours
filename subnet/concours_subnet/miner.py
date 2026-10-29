"""concours-miner: submit a fraud solver to the Concours subnet.

    concours-miner submit path/to/submission.py --netuid 123 --wallet miner --hotkey m1 \
        --validator http://VALIDATOR:8091 [--network test]
    concours-miner status --netuid 123 --wallet miner --hotkey m1 [--network test]

`submit` uploads the file to the validator, signed with the hotkey, then publishes its sha256 as the hotkey's
on-chain commitment. The validator scores only code whose hash is committed on chain by a registered hotkey, so
the chain records who submitted what, and when. A submission is a `submission.py` with a `Solver` class, the same
contract as `backend/solvers/*/submission.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from bittensor.wallet import Wallet

from concours_subnet.common import MAX_CODE_BYTES, code_sha, commit, commitment_text, connect, parse_commitment, upload_message


def _wallet(a) -> Wallet:
    return Wallet(name=a.wallet, hotkey=a.hotkey, path=a.wallet_path) if a.wallet_path else Wallet(name=a.wallet, hotkey=a.hotkey)


def cmd_submit(a) -> int:
    code = Path(a.file).read_bytes()
    if len(code) > MAX_CODE_BYTES:
        print(f"submission is over {MAX_CODE_BYTES // 1000} KB", file=sys.stderr)
        return 2
    sha = code_sha(code)
    wallet = _wallet(a)
    hotkey = wallet.hotkey
    sig = bytes(hotkey.sign(upload_message(a.netuid, sha).encode())).hex()
    body = json.dumps({"hotkey": hotkey.ss58_address, "sha256": sha, "signature": sig, "code": code.decode()}).encode()
    req = urllib.request.Request(a.validator.rstrip("/") + "/submit", data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"uploaded to validator: {r.read().decode().strip()}")
    except urllib.error.HTTPError as e:
        print(f"validator refused the upload: {e.code} {e.read().decode().strip()}", file=sys.stderr)
        return 1
    sub = connect(a.network)
    res = commit(sub, wallet, a.netuid, commitment_text(sha))
    if not res.success:
        print(f"commitment failed: {res.error}", file=sys.stderr)
        return 1
    print(f"committed {sha[:16]}… on netuid {a.netuid} ({a.network}) from {hotkey.ss58_address}")
    print("the validator scores it on its next pass; check with: concours-miner status")
    return 0


def cmd_status(a) -> int:
    sub = connect(a.network)
    ss58 = _wallet(a).hotkey.ss58_address
    c = sub.identity.commitment(a.netuid, ss58)
    sha = parse_commitment((getattr(c, "value", None) or getattr(c, "data", None)) if c else None)
    print(f"hotkey {ss58} on netuid {a.netuid} ({a.network})")
    print(f"commitment: {sha or 'none'}" + (f" at block {c.block}" if c and sha else ""))
    if a.validator:
        try:
            with urllib.request.urlopen(a.validator.rstrip("/") + f"/status/{ss58}", timeout=30) as r:
                print(json.dumps(json.loads(r.read()), indent=2))
        except urllib.error.URLError as e:
            print(f"validator unreachable: {e}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="concours-miner", description="Submit a fraud solver to the Concours subnet.")
    sp = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("submit", cmd_submit), ("status", cmd_status)):
        q = sp.add_parser(name)
        if name == "submit":
            q.add_argument("file")
        q.add_argument("--netuid", type=int, required=True)
        q.add_argument("--network", default="test", help="test | local | finney | ws://...")
        q.add_argument("--wallet", required=True)
        q.add_argument("--hotkey", required=True)
        q.add_argument("--wallet-path")
        q.add_argument("--validator", required=(name == "submit"), help="the validator's intake URL, e.g. http://host:8091")
        q.set_defaults(fn=fn)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
