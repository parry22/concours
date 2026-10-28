"""The fraud intake: three questions with defaults, answered in plain words. Deterministic (no LLM call), so it
works offline and every number it stores comes from the user's words or a stated default.

1. How many cases can your team review per day? (200)
2. What does one review cost, and what does a missed fraud cost on top of the amount? (10 per review, fee 0)
3. How long until fraud is usually confirmed, for example via chargebacks? (30 days)
"""
from __future__ import annotations

import re

from app.config import FRAUD_DEFAULTS
from app.models import FraudSettings, IntakeMessage

QUESTIONS = [
    "How many cases can your team review per day? Most teams start with about 200.",
    "What does one review cost, and what does a missed fraud cost you on top of the amount, such as a chargeback fee? "
    "Without numbers I use 10 per review and no fee.",
    "How long until fraud is usually confirmed, for example through chargebacks? Without a number I use 30 days.",
]
SUGGESTED = ["200 cases a day", "About 10 per review, no extra fee", "Usually about 30 days"]
NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k\b|thousand)?", re.I)
NONE_WORDS = re.compile(r"\b(no|none|nothing|zero)\b[^.]*\b(fee|extra|cost|on top)\b|\b(fee|extra)\b[^.]*\b(no|none|nothing|zero)\b", re.I)


def _numbers(text: str) -> list[float]:
    out = []
    for m in NUM.finditer(text):
        v = float(m.group(1).replace(",", ""))
        if m.group(2):
            v *= 1000
        out.append(v)
    return out


def parse(index: int, text: str, current: FraudSettings) -> tuple[FraudSettings, str]:
    """Apply the answer to question `index`. Returns the new settings and a one-line confirmation."""
    nums = _numbers(text)
    d = current.model_copy()
    if index == 0:
        d.daily_capacity = int(nums[0]) if nums and nums[0] >= 1 else int(FRAUD_DEFAULTS["daily_capacity"])
        d.daily_capacity = max(1, min(d.daily_capacity, 100_000))
        return d, f"Your queue holds {d.daily_capacity:,} cases a day."
    if index == 1:
        d.review_cost = nums[0] if nums else float(FRAUD_DEFAULTS["review_cost"])
        d.fraud_fee = nums[1] if len(nums) > 1 and not NONE_WORDS.search(text) else float(FRAUD_DEFAULTS["fraud_fee"])
        fee = f"a {d.fraud_fee:,.2f} fee on top of each missed fraud" if d.fraud_fee else "no fee on top of the fraud amount"
        return d, f"Each review costs {d.review_cost:,.2f}, with {fee}."
    days = None
    if nums:
        unit = text.lower()
        days = nums[0] * (7 if "week" in unit else 30 if "month" in unit else 1)
    d.label_delay_days = int(max(1, min(180, round(days)))) if days else int(FRAUD_DEFAULTS["label_delay_days"])
    return d, f"Fraud is confirmed within about {d.label_delay_days} days, so models are tested only on days that old or older."


def turn(history: list[IntakeMessage], text: str, current: FraudSettings) -> tuple[list[IntakeMessage], FraudSettings, str, bool]:
    """One answer. Returns the new history, settings, the assistant's message and whether all three are answered."""
    asked = sum(1 for m in history if m.role == "user")
    if asked >= len(QUESTIONS):
        return history, current, "All three answers are in.", True
    st, ack = parse(asked, text, current)
    done = asked + 1 >= len(QUESTIONS)
    reply = ack + (" " + QUESTIONS[asked + 1] if not done else
                   f" That is everything: a {st.daily_capacity:,}-case queue, {st.review_cost:,.2f} per review, confirmed within {st.label_delay_days} days.")
    hist = list(history)
    if not hist:
        hist.append(IntakeMessage(role="assistant", content=QUESTIONS[0]))
    hist += [IntakeMessage(role="user", content=text), IntakeMessage(role="assistant", content=reply)]
    return hist, st, reply, done
