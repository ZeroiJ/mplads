"""MP-level aggregate (A1/A2): worst-offender table per MP / constituency.

From the flags table produces per-MP metrics (works, sanctioned, completed,
sums, stalled count, dup-lead count, anomaly count, weighted risk) and a
worst-offenders ranking file for the demo.
"""

import numpy as np
import pandas as pd

from . import config



def aggregate(flags: pd.DataFrame) -> pd.DataFrame:
    ok = flags.dropna(subset=["mp_no"])
    for col in ["recommended_amount", "sanction_amount", "amount_disbursed", "exp_total", "alloc_limit"]:
        if col not in ok.columns:
            ok[col] = np.nan
        ok[col] = pd.to_numeric(ok[col], errors="coerce").fillna(0.0)

    g = ok.groupby(["mp_no", "mp_name", "mp_state"], dropna=False).agg(
        works=("work_id", "count"),
        sanctioned=("is_sanctioned", "sum"),
        completed=("is_completed", "sum"),
        recommended_total=("recommended_amount", "sum"),
        sanctioned_total=("sanction_amount", "sum"),
        disbursed_total=("amount_disbursed", "sum"),
        spent_total=("exp_total", "sum"),
        alloc_limit=("alloc_limit", "max"),
        stalled=("flag_stalled", "sum"),
        zero_disbursal=("flag_zero_disbursal", "sum"),
        dup_leads=("has_duplicate_lead", "sum"),
        anomalies=("is_anomaly", "sum"),
        avg_risk_per_work=("risk_score", "mean"),
    ).reset_index()

    g["spend_pct_alloc"] = np.where(g["alloc_limit"] > 0, g["spent_total"] / g["alloc_limit"] * 100, np.nan)
    g["cumulative_risk_points"] = (
        g["stalled"] * 3
        + g["dup_leads"] * 4
        + g["anomalies"] * 2
        + g["zero_disbursal"] * 2
    )
    g = g.sort_values("cumulative_risk_points", ascending=False).reset_index(drop=True)
    g["risk_rank"] = np.arange(1, len(g) + 1)
    return g


def run(master_engine_flags: pd.DataFrame, save=True):
    agg = aggregate(master_engine_flags)
    if save:
        agg.to_csv(config.MP_AGGREGATE_CSV, index=False)
        agg.to_csv(config.WORST_OFFENDERS_CSV, index=False)
    return agg