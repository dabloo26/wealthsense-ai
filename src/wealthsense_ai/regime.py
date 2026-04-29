from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from hmmlearn.hmm import GaussianHMM
except Exception:  # pragma: no cover
    GaussianHMM = None  # type: ignore[assignment]


def detect_market_regime(
    returns: np.ndarray,
    vix: np.ndarray,
    volume: np.ndarray,
) -> dict[str, object]:
    if len(returns) < 50:
        return {"regime_index": 0, "regime_label": "low_vol_bull", "regime_probs": [1.0, 0.0, 0.0], "method": "fallback_short_series"}

    frame = pd.DataFrame({"returns": returns, "vix": vix, "volume": volume}).replace([np.inf, -np.inf], np.nan).dropna()
    if frame.empty:
        return {"regime_index": 0, "regime_label": "low_vol_bull", "regime_probs": [1.0, 0.0, 0.0], "method": "fallback_empty"}

    x = frame.values.astype(float)
    if GaussianHMM is None:
        avg_vix = float(np.mean(frame["vix"]))
        avg_ret = float(np.mean(frame["returns"]))
        if avg_ret < 0:
            return {"regime_index": 2, "regime_label": "bear", "regime_probs": [0.0, 0.0, 1.0], "method": "fallback_rules"}
        if avg_vix > np.percentile(frame["vix"], 70):
            return {"regime_index": 1, "regime_label": "high_vol_bull", "regime_probs": [0.0, 1.0, 0.0], "method": "fallback_rules"}
        return {"regime_index": 0, "regime_label": "low_vol_bull", "regime_probs": [1.0, 0.0, 0.0], "method": "fallback_rules"}

    model = GaussianHMM(n_components=3, covariance_type="diag", n_iter=200, random_state=42)
    model.fit(x)
    states = model.predict(x)
    probs = model.predict_proba(x)[-1]

    regime_stats: dict[int, tuple[float, float]] = {}
    for state in range(3):
        mask = states == state
        if np.any(mask):
            regime_stats[state] = (float(np.mean(frame["returns"][mask])), float(np.mean(frame["vix"][mask])))
        else:
            regime_stats[state] = (0.0, float(np.mean(frame["vix"])))

    sorted_states = sorted(regime_stats.items(), key=lambda item: (item[1][0], item[1][1]))
    bear_state = sorted_states[0][0]
    high_vol_bull_state = sorted_states[-1][0] if sorted_states[-1][1][1] > sorted_states[1][1][1] else sorted_states[1][0]
    low_vol_bull_state = [s for s in [0, 1, 2] if s not in {bear_state, high_vol_bull_state}][0]
    mapping = {low_vol_bull_state: "low_vol_bull", high_vol_bull_state: "high_vol_bull", bear_state: "bear"}

    current_state = int(states[-1])
    return {
        "regime_index": current_state,
        "regime_label": mapping[current_state],
        "regime_probs": probs.tolist(),
        "method": "hmm",
    }
