import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from app.shared import metrics as m

y = np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 1])
s = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.95, 0.8, 0.9, 0.7])


def test_recall_at_fpr_hand():
    # fpr 0 -> positives must beat every negative (max neg 0.95): none -> 0
    assert m.recall_at_fpr(y, s, 0.0) == 0.0
    # 8 negatives, fpr 0.125 -> 1 negative allowed above; threshold = 0.8; positives > 0.8: 0.9 -> 0.5
    assert m.recall_at_fpr(y, s, 0.125) == 0.5
    assert m.recall_at_fpr(y, s, 0.25) == 1.0


def test_recall_at_top_k():
    assert m.recall_at_top_k(y, s, 0.2) == 0.5  # top 2 = 0.95, 0.9 -> one positive
    assert m.recall_at_top_k(y, s, 0.4) == 1.0


def test_auc_matches_sklearn():
    rng = np.random.default_rng(1)
    yy = rng.integers(0, 2, 500)
    ss = rng.random(500) + yy * 0.3
    ss[::7] = 0.5  # ties
    assert abs(m.roc_auc(yy, ss) - roc_auc_score(yy, ss)) < 1e-9
    assert abs(m.pr_auc(yy, ss) - average_precision_score(yy, ss)) < 1e-9


def test_threshold_at_fpr_consistent():
    thr = m.threshold_at_fpr(y, s, 0.125)
    flagged_neg = (s[y == 0] >= thr).mean()
    assert flagged_neg <= 0.125


def test_nan_safe():
    assert m.recall_at_fpr(y, np.where(s > 0.5, np.nan, s), 0.5) >= 0.0


def test_compute_dispatch():
    assert m.compute("recall_at_top_k", y, s, {"top_k": 0.4}) == 1.0
    assert m.compute("wape", [10, 20], [11, 18]) == 0.1
