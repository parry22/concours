"""Pure numpy value computation. No I/O. See docs/VALUE_MODEL.md for the formulas."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.models import CurvePoint, ProblemSpec, Sensitivity, ValueParam, ValuePoint
from app.shared.metrics import threshold_at_fpr

BOOTSTRAP_DRAWS = 1000
BOOTSTRAP_SEED = 0
CURVE_POINTS = 80
CURVE_MIN_SHARE = 0.0005
CURVE_MAX_SHARE = 0.5


@dataclass(frozen=True)
class Econ:
    rows_per_month: float
    value_per_positive: float
    action_success_rate: float
    cost_per_action: float
    cost_per_false_positive: float

    @classmethod
    def from_params(cls, params: list[ValueParam]) -> "Econ":
        d = {p.key: p.value for p in params}
        return cls(
            rows_per_month=d.get("rows_per_month", 0.0),
            value_per_positive=d.get("value_per_positive", 0.0),
            action_success_rate=d.get("action_success_rate", 0.0),
            cost_per_action=d.get("cost_per_action", 0.0),
            cost_per_false_positive=d.get("cost_per_false_positive", 0.0),
        )

    def replace(self, **kw: float) -> "Econ":
        return Econ(**{**self.__dict__, **kw})


def _prep(y, s) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y).astype(np.int8).ravel()
    s = np.asarray(s, dtype=np.float64).ravel()
    if y.shape != s.shape:
        raise ValueError(f"labels and scores differ in length: {len(y)} vs {len(s)}")
    return y, np.nan_to_num(s, nan=0.0, posinf=1.0, neginf=0.0)


def counts(y, s, thr: float) -> tuple[int, int, int, int]:
    """(tp, fp, fn, tn) with flag = score >= thr."""
    y, s = _prep(y, s)
    flag = s >= thr
    tp = int((flag & (y == 1)).sum())
    fp = int(flag.sum()) - tp
    fn = int((y == 1).sum()) - tp
    tn = len(y) - tp - fp - fn
    return tp, fp, fn, tn


def money(tp: float, fp: float, e: Econ) -> tuple[float, float, float]:
    """(gross, costs, net) for monthly counts tp and fp."""
    gross = tp * e.action_success_rate * e.value_per_positive
    costs = (tp + fp) * e.cost_per_action + fp * e.cost_per_false_positive
    return gross, costs, gross - costs


def threshold_for_share(s, share: float) -> float:
    """Threshold that flags the top `share` of rows (at least one row)."""
    s = np.asarray(s, dtype=np.float64).ravel()
    n_flag = min(len(s), max(1, int(np.ceil(share * len(s)))))
    return float(np.sort(s)[::-1][n_flag - 1])


def contract_threshold(spec: ProblemSpec, y, s) -> float:
    """The operating point agreed in intake, chosen on the split given (the public leaderboard slice)."""
    if spec.primary_metric == "recall_at_top_k":
        return threshold_for_share(s, float(spec.metric_params.get("top_k", 0.10)))
    return threshold_at_fpr(y, s, float(spec.metric_params.get("fpr", 0.001)))


def point(name: str, y, s, thr: float, e: Econ, *, bootstrap: bool = True) -> ValuePoint:
    y, s = _prep(y, s)
    n = len(y)
    tp, fp, fn, tn = counts(y, s, thr)
    scale = e.rows_per_month / n if n else 0.0
    gross, costs, net = money(tp * scale, fp * scale, e)
    pos = tp + fn
    neg = fp + tn
    out = ValuePoint(
        name=name,  # type: ignore[arg-type]
        threshold=float(thr),
        flagged_share=(tp + fp) / n if n else 0.0,
        fpr=fp / neg if neg else 0.0,
        recall=tp / pos if pos else 0.0,
        precision=tp / (tp + fp) if tp + fp else 0.0,
        tp=tp * scale,
        fp=fp * scale,
        fn=fn * scale,
        tn=tn * scale,
        gross=gross,
        costs=costs,
        net=net,
    )
    if bootstrap and n:
        # At a fixed threshold every row sits in one cell, so resampling rows is a multinomial draw over the cells.
        rng = np.random.default_rng(BOOTSTRAP_SEED)
        draws = rng.multinomial(n, np.array([tp, fp, fn, tn], dtype=np.float64) / n, size=BOOTSTRAP_DRAWS)
        tp_b, fp_b, fn_b = draws[:, 0], draws[:, 1], draws[:, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            rec_b = np.where(tp_b + fn_b > 0, tp_b / np.maximum(tp_b + fn_b, 1), 0.0)
        _, _, net_b = money(tp_b * scale, fp_b * scale, e)
        out.recall_low, out.recall_high = (float(x) for x in np.percentile(rec_b, [5, 95]))
        out.net_low, out.net_high = (float(x) for x in np.percentile(net_b, [5, 95]))
    return out


def curve(y, s, e: Econ) -> tuple[list[CurvePoint], float]:
    """Net value across operating points. Returns the points and the threshold with the highest net."""
    y, s = _prep(y, s)
    n = len(y)
    if n == 0:
        return [], 0.0
    scale = e.rows_per_month / n
    order = np.argsort(-s, kind="stable")
    y_sorted = y[order]
    s_sorted = s[order]
    cum_tp = np.cumsum(y_sorted == 1)
    pos = int((y == 1).sum())
    neg = n - pos
    shares = np.geomspace(CURVE_MIN_SHARE, CURVE_MAX_SHARE, CURVE_POINTS)
    pts: list[CurvePoint] = []
    best_net = -np.inf
    best_thr = float(s_sorted[0])
    seen: set[int] = set()
    for share in shares:
        k = min(n, max(1, int(np.ceil(share * n))))
        if k in seen:
            continue
        seen.add(k)
        thr = float(s_sorted[k - 1])
        k_eff = int((s >= thr).sum())  # ties: everything at the threshold is flagged
        tp = int(cum_tp[k_eff - 1])
        fp = k_eff - tp
        _, _, net = money(tp * scale, fp * scale, e)
        pts.append(CurvePoint(flagged_share=k_eff / n, recall=tp / pos if pos else 0.0, fpr=fp / neg if neg else 0.0, net=net))
        if net > best_net:
            best_net, best_thr = net, thr
    return pts, best_thr


def sensitivity(tp_month: float, fp_month: float, e: Econ, labels: dict[str, str]) -> list[Sensitivity]:
    out = []
    for key in ("value_per_positive", "action_success_rate", "cost_per_action", "cost_per_false_positive", "rows_per_month"):
        base = getattr(e, key)
        lo_v, hi_v = base * 0.5, base * 1.5
        if key == "action_success_rate":
            hi_v = min(1.0, hi_v)
        if key == "rows_per_month":
            # volume scales the counts, not the unit economics
            lo_net = money(tp_month * 0.5, fp_month * 0.5, e)[2]
            hi_net = money(tp_month * 1.5, fp_month * 1.5, e)[2]
        else:
            lo_net = money(tp_month, fp_month, e.replace(**{key: lo_v}))[2]
            hi_net = money(tp_month, fp_month, e.replace(**{key: hi_v}))[2]
        out.append(Sensitivity(key=key, label=labels.get(key, key), low_value=lo_v, low_net=lo_net, high_value=hi_v, high_net=hi_net))
    return out


def breakeven(tp_month: float, fp_month: float, e: Econ) -> dict[str, float | None]:
    """Parameter values at which net value is zero, holding the rest fixed."""
    gross = tp_month * e.action_success_rate * e.value_per_positive
    action_costs = (tp_month + fp_month) * e.cost_per_action
    cfp = (gross - action_costs) / fp_month if fp_month > 0 else None
    asr = ((tp_month + fp_month) * e.cost_per_action + fp_month * e.cost_per_false_positive) / (tp_month * e.value_per_positive) if tp_month > 0 and e.value_per_positive > 0 else None
    return {
        "cost_per_false_positive": float(cfp) if cfp is not None and cfp >= 0 else None,
        "action_success_rate": float(asr) if asr is not None and 0 <= asr <= 1 else None,
    }
