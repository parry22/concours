import numpy as np
import pandas as pd
import pytest

from app.config import TEMPLATES_DIR


@pytest.fixture(scope="session")
def fraud_df():
    p = TEMPLATES_DIR / "fraud" / "dataset.csv"
    if not p.exists():
        pytest.skip("fraud dataset not fetched")
    return pd.read_csv(p)


@pytest.fixture(scope="session")
def churn_df():
    p = TEMPLATES_DIR / "churn" / "dataset.csv"
    if not p.exists():
        pytest.skip("churn dataset not fetched")
    return pd.read_csv(p)


@pytest.fixture
def toy_df():
    rng = np.random.default_rng(0)
    n = 2000
    y = (rng.random(n) < 0.1).astype(int)
    return pd.DataFrame(
        {
            "row_id": np.arange(n),
            "amount": rng.gamma(2, 50, n),
            "email": [f"user{i}@example.com" for i in range(n)],
            "card_number": ["4111111111111111"] * n,
            "const": [1] * n,
            "dispute_status": y * rng.integers(1, 4, n),  # non-zero only for positives
            "signal": y * 0.5 + rng.normal(0, 1, n),
            "event_time": pd.date_range("2024-01-01", periods=n, freq="h").strftime("%Y-%m-%d %H:%M:%S"),
            "target": y,
        }
    )


@pytest.fixture(scope="session")
def leads_df():
    p = TEMPLATES_DIR / "leads" / "dataset.csv"
    if not p.exists():
        pytest.skip("leads dataset not fetched")
    return pd.read_csv(p)


@pytest.fixture(scope="session")
def readmissions_df():
    p = TEMPLATES_DIR / "readmissions" / "dataset.csv"
    if not p.exists():
        pytest.skip("readmissions dataset not fetched")
    return pd.read_csv(p, low_memory=False)
