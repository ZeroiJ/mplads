"""Isolation Forest (D1): unsupervised anomaly scoring on engineered features.

Trains on the F1-F4 feature columns; no labels needed. Outputs a continuous
anomaly score and an `is_anomaly` flag (decision_function <-0 boundary).
Rows with too many missing features are skipped (anomaly NaN) so the rules
still carry them.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from . import config
from .features import FEATURE_COLUMNS


def fit_anomaly_scores(feature_df: pd.DataFrame, seed=42) -> pd.DataFrame:
    """Return a DataFrame indexed like feature_df with anomaly_score, is_anomaly."""
    X = feature_df[FEATURE_COLUMNS].astype(object).where(pd.notna(feature_df[FEATURE_COLUMNS]) & (feature_df[FEATURE_COLUMNS] != pd.NA), np.nan).astype(float)
    mask = X.notna().sum(axis=1) >= 5  # need most features present
    Xf = X[mask].replace([np.inf, -np.inf], np.nan).fillna(X[mask].median())

    ifm = IsolationForest(
        n_estimators=config.IF_N_ESTIMATORS,
        contamination=config.IF_CONTAMINATION,
        max_samples=config.IF_MAX_SAMPLES,
        random_state=seed,
        n_jobs=-1,
    ).fit(Xf)

    raw = ifm.decision_function(Xf)  # higher = more normal
    # normalize anomaly score to 0..1 where 1 = most anomalous
    score = 1.0 - (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)
    is_anom = ifm.predict(Xf) == -1

    out = pd.DataFrame(index=feature_df.index, columns=["anomaly_score", "is_anomaly"], dtype=float)
    out["anomaly_score"] = np.nan
    out["is_anomaly"] = False
    out.loc[mask, "anomaly_score"] = score
    out.loc[mask, "is_anomaly"] = is_anom
    return out, ifm