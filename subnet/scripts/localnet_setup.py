"""Set up a Concours subnet on a LOCAL subtensor chain for testing (never testnet or mainnet).

    docker run -d --name concours-localnet -p 9944:9944 -p 9945:9945 ghcr.io/opentensor/subtensor-localnet:devnet-ready
    .venv/bin/python scripts/localnet_setup.py --wallet-path /tmp/concours-localnet-wallets

Creates throwaway, unencrypted wallets under --wallet-path (owner with hotkey `validator`, miner with hotkeys `m1`
and `m2`), funds them from the chain's public dev account //Alice, registers a subnet, starts its emissions,
registers the hotkeys and stakes to the validator. Prints the netuid. The dev keys are public; nothing here is a
secret, and the script refuses any network other than local.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import bittensor as bt
from bittensor.keyfiles import Keypair
from bittensor.wallet import Wallet


def wallet(path: str, name: str, hotkeys: list[str]) -> Wallet:
    w = Wallet(name=name, hotkey=hotkeys[0], path=path)
    if not Path(path, name, "coldkey").exists():
        w.create_new_coldkey(use_password=False, on_mnemonic=lambda m: None)
    for hk in hotkeys:
        h = Wallet(name=name, hotkey=hk, path=path)
        if not Path(path, name, "hotkeys", hk).exists():
            h.create_new_hotkey(use_password=False, on_mnemonic=lambda m: None)
    return w


def ok(res, what: str):
    if not res.success:
        raise SystemExit(f"{what} failed: {res.error}")
    print(f"ok: {what}")
    return res


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wallet-path", required=True)
    p.add_argument("--network", default="local")
    p.add_argument("--netuid", type=int, help="reuse a subnet this owner already registered")
    a = p.parse_args()
    if a.network not in ("local", "ws://127.0.0.1:9944"):
        raise SystemExit("localnet only")
    path = a.wallet_path
    alice = Wallet(name="alice", hotkey="default", path=path)
    if not Path(path, "alice", "coldkey").exists():
        alice._set_coldkey(Keypair.create_from_uri("//Alice"), encrypt=False, overwrite=True, save_coldkey_to_env=False, coldkey_password=None)
        alice._set_coldkeypub(Keypair.create_from_uri("//Alice"), overwrite=True) if hasattr(alice, "_set_coldkeypub") else None
    owner = wallet(path, "owner", ["validator"])
    miner = wallet(path, "miner", ["m1", "m2"])
    sub = bt.Subtensor(a.network)
    for w, amount in ((owner, 3000), (miner, 100)):
        if sub.balances.get(w.coldkeypub.ss58_address).tao < amount / 2:
            ok(sub.execute(bt.Transfer(dest_ss58=w.coldkeypub.ss58_address, amount_tao=amount), alice), f"fund {w.name} {amount} τ")
    netuid = a.netuid
    if netuid is None:
        before = {s.netuid for s in sub.subnets.all()}
        ok(sub.execute(bt.RegisterSubnet(hotkey_ss58=owner.hotkey.ss58_address), owner), "register subnet")
        netuid = max({s.netuid for s in sub.subnets.all()} - before)
        try:
            ok(sub.execute(bt.StartCall(netuid=netuid), owner), "start emissions")
        except bt.BittensorError as e:
            print(f"start call: {e} (may need more blocks; rerun with --netuid {netuid})")
    print(f"netuid {netuid}")
    for hk in ("m1", "m2"):
        mw = Wallet(name="miner", hotkey=hk, path=path)
        try:
            ok(sub.execute(bt.BurnedRegister(netuid=netuid, hotkey_ss58=mw.hotkey.ss58_address), mw), f"register miner {hk}")
        except Exception:  # noqa: BLE001  older local runtimes
            # older local runtimes lack storage the intent's preview reads; the raw call is the same extrinsic
            call = bt.calls.SubtensorModule.burned_register(netuid=netuid, hotkey=mw.hotkey.ss58_address)
            ok(sub.submit_call(call, mw), f"register miner {hk} (raw call)")
    ok(sub.execute(bt.AddStake(hotkey_ss58=owner.hotkey.ss58_address, netuid=netuid, amount_tao=1000, slippage_protection=False), owner), "stake validator")
    out = {"netuid": netuid, "wallet_path": path, "validator": owner.hotkey.ss58_address,
           "miners": {hk: Wallet(name="miner", hotkey=hk, path=path).hotkey.ss58_address for hk in ("m1", "m2")}}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
