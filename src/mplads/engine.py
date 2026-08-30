"""Detection engine (D0-D3 orchestration) -> metrics/flags.csv.

Combines:
  D1  Isolation Forest anomaly score       (anomaly.py)
  D2  duplicate fuzzy-match signals        (duplicates.py, from real_sweep.csv)
  D3  rule flags                           (rules.py)
into one flags table, with a transparent weighted risk score (0..100).

Output: metrics/flags.csv - one row per work, all raw fields + every signal
stored explicitly so investigators see *why* a work is flagged.
"""

import numpy as np
import pandas as pd

from . import config
from .anomaly import fit_anomaly_scores
from .duplicates import compute_dup_signals
from .features import build_features
from .rules import rule_flags, rule_reason


def run_engine(master_path=None, save=True) -> pd.DataFrame:
    master = pd.read_csv(master_path or config.MASTER)

    feats = build_features(master)
    flagged, flag_cols = rule_flags(feats)
    dup_signals = compute_dup_signals(master)
    anomaly, _ifmodel = fit_anomaly_scores(feats)

    out = pd.concat(
        [master.reset_index(drop=True), dup_signals.reset_index(drop=True)], axis=1
    )
    # drop the duplicated work_id column introduced by dup_signals merge key
    out = out.loc[:, ~out.columns.duplicated(keep="first")]
    out = pd.concat([out.reset_index(drop=True), anomaly.reset_index(drop=True)], axis=1)

    # attach rule flags explicitly
    for c in flag_cols:
        out[c] = flagged[c].values

    reasons = out.apply(lambda r: rule_reason(r, flag_cols), axis=1)
    dup_reasons = np.where(
        out.get("has_duplicate_lead", pd.Series(False, index=out.index)).fillna(False),
        "duplicate-resubmission candidate (cross-FY, same MP+amount, description sim >= "
        + str(config.DUP_SIM_THRESHOLD)
        + ")",
        "",
    )
    anom_reasons = np.where(
        out.get("is_anomaly", pd.Series(False, index=out.index)).fillna(False),
        "anomalous on F1-F4 features (Isolation Forest)",
        "",
    )
    out["reasons"] = ["; ".join(filter(None, parts)) for parts in zip(reasons, dup_reasons, anom_reasons)]

    # --- transparent risk score ----------------------------------------------
    risk = np.zeros(len(out))
    for name, wt in config.RISK_WEIGHTS.items():
        if name == "stalled":
            risk += wt * out.get("flag_stalled", pd.Series(False, index=out.index)).fillna(False).astype(int)
        elif name == "unparseable":
            risk += wt * out.get("flag_unparseable", pd.Series(False, index=out.index)).fillna(False).astype(int)
        elif name == "sanction_overrun":
            risk += wt * out.get("flag_sanction_overrun", pd.Series(False, index=out.index)).fillna(False).astype(int)
        elif name == "zero_disbursal":
            risk += wt * out.get("flag_zero_disbursal", pd.Series(False, index=out.index)).fillna(False).astype(int)
        elif name == "duplicate_lead":
            risk += wt * out.get("has_duplicate_lead", pd.Series(False, index=out.index)).fillna(False).astype(int)
        elif name == "anomaly":
            risk += wt * out.get("is_anomaly", pd.Series(False, index=out.index)).fillna(False).astype(int)
    out["risk_score"] = np.clip(risk, 0, 100).astype(int)

    out["is_flagged"] = out["reasons"].str.len() > 0

    out = out.sort_values("risk_score", ascending=False).reset_index(drop=True)

    if save:
        out.to_csv(config.FLAGS_CSV, index=False)
    return out


def summarize(flags: pd.DataFrame) -> dict:
    flagged = flags[flags["is_flagged"]]
    lead = flagged[flagged.get("has_duplicate_lead", pd.Series(False, index=flagged.index)).fillna(False)]
    return {
        "total_works": len(flags),
        "flagged": int(flagged.shape[0]),
        "with_any_rule": int(flagged["reasons"].str.contains("stalled|overrun|unparseable|zero disbursal", case=False).sum()),
        "duplicate_leads": int(lead.shape[0]),
        "anomalies": int(flags["is_anomaly"].fillna(False).sum()),
        "stalled": int(flags["flag_stalled"].fillna(False).sum()),
        "zero_disbursal": int(flags["flag_zero_disbursal"].fillna(False).sum()),
        "sanction_overrun": int(flags["flag_sanction_overrun"].fillna(False).sum()),
        "highest_risk": float(flags["risk_score"].max()),
    }