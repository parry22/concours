# VENDORED from macrocosm-os/apex-competitions-builder @ 49eb05e (src/apex_sdk/gym_v1). Imports rewritten; player.py do_POST patched by Brief.
"""The gym_v1 duel protocol: player server base, referee harness, and referee-side client."""

from gym_v1.client import PlayerClient, PlayerError
from gym_v1.player import Player, serve
from gym_v1.referee import GameResult, Referee, RefereeContext

__all__ = [
    "Player",
    "serve",
    "PlayerClient",
    "PlayerError",
    "Referee",
    "GameResult",
    "RefereeContext",
]
