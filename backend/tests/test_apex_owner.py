"""Owner settings fill spec.yaml, HANDOFF.md and ONBOARDING_ISSUE.md; unset keeps the TODO placeholders."""
import pytest
import yaml

from app import config
from app.apex_builder import adversarial, generator

CID = "concours_fraud_6974713c0ea7"


def _set(monkeypatch, repo="", name="", email=""):
    monkeypatch.setattr(config, "GITHUB_REPO", repo)
    monkeypatch.setattr(config, "OWNER_NAME", name)
    monkeypatch.setattr(config, "OWNER_EMAIL", email)


def _render(own: dict) -> dict:
    ctx = {"competition_id": CID, "version": "0.1.0", "display_name": "x", "cpu_limit": 2, "mem_limit": "2Gi",
           "player_digest": generator.ZERO, "referee_digest": generator.ZERO, "reveal_days": 7,
           "evaluate_timeout_s": 900, "referee_timeout_s": 900, "hidden_checksums": {}, "checksums": {}, "adversarial": [], "baseline_raw_score": 3960.6343, **own}
    return {t: generator.env.get_template(f"{t}.j2").render(ctx) for t in ("spec.yaml", "HANDOFF.md", "ONBOARDING_ISSUE.md")}


def test_owner_settings_fill_package(monkeypatch):
    _set(monkeypatch, "Parry22/concours-fraud", "Pat Owner", "pat@example.com")
    own = generator.owner(CID)
    # release.yml pushes to ghcr.io/${{ github.repository }}-<name>; GHCR names are lowercase
    assert own["image_ref"] == "ghcr.io/parry22/concours-fraud-player"
    assert own["referee_ref"] == "ghcr.io/parry22/concours-fraud-referee"
    out = _render(own)
    spec = yaml.safe_load(out["spec.yaml"])
    assert spec["image"]["ref"] == own["image_ref"] and spec["referee"]["image"]["ref"] == own["referee_ref"]
    assert spec["signature"]["cosign_identity"] == "https://github.com/Parry22/concours-fraud/.github/workflows/release.yml"
    assert "https://github.com/Parry22/concours-fraud" in out["ONBOARDING_ISSUE.md"]
    assert "Contact: Pat Owner <pat@example.com>." in out["HANDOFF.md"]
    assert "https://github.com/Parry22/concours-fraud @" in out["HANDOFF.md"]
    assert "your-org" not in "".join(out.values()) and "TODO owner" not in out["HANDOFF.md"]
    assert spec["defaults"]["baseline_raw_score"] == 3960.6343 and spec["defaults"]["baseline_score"] == 0.0


def test_owner_unset_keeps_placeholders(monkeypatch):
    _set(monkeypatch)
    own = generator.owner(CID)
    assert own["image_ref"] == "ghcr.io/your-org/concours-fraud-6974713c0ea7-player"
    out = _render(own)
    assert "your-org" in out["spec.yaml"]
    assert "Contact: TODO owner name and email." in out["HANDOFF.md"]
    assert "### Competition repo URL\n\nTODO" in out["ONBOARDING_ISSUE.md"]


def test_owner_repo_must_be_owner_slash_name(monkeypatch):
    _set(monkeypatch, "https://github.com/a/b")
    with pytest.raises(ValueError, match="owner/name"):
        generator.owner(CID)


def test_adversarial_verdicts_against_the_starting_bar():
    res = {"primary_metric": "fraud_amount_per_day", "submissions": [
        {"name": "constant", "ok": True, "raw_score": 3724.0},
        {"name": "random", "ok": True, "raw_score": 2751.0},
        {"name": "all_zeros", "ok": False, "raw_score": None},
    ]}
    v = {r["name"]: r for r in adversarial.verdicts(res, 3961.0)}
    assert all(r["below"] for r in v.values()) and "largest payments" in v["constant"]["note"]
    assert v["all_zeros"]["score"] == 0.0
    # a bar at the weaker first model lets the constant through: that is what the HANDOFF must flag
    assert not {r["name"]: r for r in adversarial.verdicts(res, 3714.0)}["constant"]["below"]
    assert not any(r["below"] for r in adversarial.verdicts(res, None))
    for name in adversarial.SUBMISSIONS:
        compile(adversarial.source(name), name, "exec")
