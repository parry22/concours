"""Shared by the miner and the validator: the commitment format, the signed upload message, chain helpers."""
from __future__ import annotations

import hashlib
import re

import bittensor as bt

PREFIX = "concours:"
COMMIT_RE = re.compile(r"^concours:([0-9a-f]{64})$")
MAX_CODE_BYTES = 200_000


def code_sha(code: bytes) -> str:
    return hashlib.sha256(code).hexdigest()


def commitment_text(sha: str) -> str:
    """What a miner publishes on chain: the sha256 of the submission.py it uploaded to the validator."""
    return f"{PREFIX}{sha}"


def parse_commitment(text: str | None) -> str | None:
    m = COMMIT_RE.match((text or "").strip())
    return m.group(1) if m else None


def upload_message(netuid: int, sha: str) -> str:
    """The message a miner signs with its hotkey when uploading code, so nobody else can upload in its name."""
    return f"concours-upload:{netuid}:{sha}"


def connect(network: str) -> bt.Subtensor:
    """`test`, `local`, `finney` or a ws:// endpoint. Blocking client."""
    return bt.Subtensor(network)


def commit(sub: bt.Subtensor, wallet, netuid: int, text: str):
    """Publish `text` as the hotkey's commitment on `netuid` (the fee is charged to the hotkey's coldkey)."""
    data = text.encode()
    call = bt.calls.Commitments.set_commitment(netuid=netuid, info={"fields": [{f"Raw{len(data)}": "0x" + data.hex()}]})
    return sub.submit_call(call, wallet, signer="hotkey")
