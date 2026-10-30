import pandas as pd

from app import secure_store
from app.fraud.protect import hash_ids
from app.fraud.schema import inspect_mapping


def test_keyed_hash_differs_from_v1_and_is_stable():
    v = pd.Series(["7", "8", "7"])
    keyed, m = hash_ids(v, "salt-a", keyed=True)
    plain, _ = hash_ids(v, "salt-a", keyed=False)
    again, _ = hash_ids(v, "salt-a", keyed=True)
    assert keyed.tolist() == again.tolist() and keyed[0] == keyed[2] != keyed[1]
    assert keyed.tolist() != plain.tolist()
    assert hash_ids(v, "salt-b", keyed=True)[0].tolist() != keyed.tolist()
    assert (keyed >= 0).all() and len(m) == 2


def test_salt_round_trips_encrypted():
    enc = secure_store.encrypt_text("concours-demo-q4")
    assert enc.startswith("enc:") and "concours-demo-q4" not in enc
    assert secure_store.decrypt_text(enc) == "concours-demo-q4"
    assert secure_store.decrypt_text("legacy-plain") == "legacy-plain"


def test_card_number_customer_column_is_refused():
    n = 300
    df = pd.DataFrame({"id": range(n), "t": pd.date_range("2024-01-01", periods=n, freq="h").strftime("%Y-%m-%d %H:%M:%S"),
                       "pan": ["4111111111111111"] * n, "amt": ["1.00"] * n, "y": ["yes" if i % 30 == 0 else "no" for i in range(n)]})
    problems, _, _ = inspect_mapping(df, {"transaction_id": "id", "transaction_time": "t", "amount": "amt", "customer_id": "pan", "is_fraud": "y"})
    assert any("looks like card numbers" in p for p in problems)


def test_hash_ids_survives_blank_ids():
    """A real export has blank terminal IDs; NaN stays NaN through astype(str) on this pandas, and the keyed hash
    used to crash on it (the 2026-10-30 hosted check). Blanks share one bucket, every other value keeps its own."""
    import numpy as np
    import pandas as pd

    from app.fraud.protect import hash_ids

    s = pd.Series(["a", np.nan, "b", None, "a"])
    out, m = hash_ids(s, "salt-1", keyed=True)
    assert out.dtype == "int64" and out.iloc[0] == out.iloc[4] and out.iloc[1] == out.iloc[3] and out.iloc[0] != out.iloc[2]
    assert set(m["original"]) == {"a", "", "b"} and (out >= 0).all()
    out1, _ = hash_ids(s, "salt-1", keyed=False)
    assert out1.iloc[1] == out1.iloc[3] and out1.iloc[0] != out1.iloc[1]
