"""Duplicate fuzzy-match (D2): semantic embeddings + MP/amount grouping.

Reuses the pre-computed real-data sweep (metrics/real_sweep.csv) so the engine
does not have to re-embed 10k+ works every run. The sweep already applied the
trained `paraphrase-multilingual-MiniLM-L12-v2` model with cosine threshold
0.80 inside (mp_no, recommended_amount) groups.

This module turns the pair list into per-work duplicate-claim signals:
  - dup_partner_count   : how many strong candidates partner this work_id
  - has_duplicate_lead  : True when a partner is in a *different financial year*,
                          the canonical duplicate-resubmission fraud pattern.
"""

import pandas as pd

from . import config


def load_sweep() -> pd.DataFrame:
    sweep = pd.read_csv(config.REAL_SWEEP_CSV)
    # keep only the fine-tuned model's verdicts (the one we ship)
    return sweep[sweep["model"] == "finetuned"].reset_index(drop=True)


def compute_dup_signals(master: pd.DataFrame) -> pd.DataFrame:
    """Return per-work_id duplicate signals aligned to master's work_id column."""
    sweep = load_sweep()
    if sweep.empty:
        raise RuntimeError(f"real_sweep.csv empty/absent: {config.REAL_SWEEP_CSV}")

    fy = master[["work_id", "fy"]].rename(columns={"fy": "fy"})

    # attach FY to both endpoints of every pair
    pairs = sweep.merge(
        fy.rename(columns={"fy": "fy_a"}), left_on="work_a", right_on="work_id", how="left"
    ).merge(
        fy.rename(columns={"fy": "fy_b"}), left_on="work_b", right_on="work_id", how="left"
    )
    pairs["cross_fy"] = pairs["fy_a"].fillna("") != pairs["fy_b"].fillna("")

    # stack both endpoints so each work_id sees its partners
    a = pairs.rename(columns={"work_a": "work_id", "work_b": "partner", "fy_a": "self_fy", "fy_b": "partner_fy"})
    b = pairs.rename(columns={"work_b": "work_id", "work_a": "partner", "fy_b": "self_fy", "fy_a": "partner_fy"})
    stacked = pd.concat([a[["work_id", "partner", "similarity", "cross_fy"]], b[["work_id", "partner", "similarity", "cross_fy"]]], ignore_index=True)

    grp = (
        stacked.groupby("work_id")
        .agg(
            dup_partner_count=("similarity", "size"),
            dup_partner_sim_max=("similarity", "max"),
            dup_partner_cross_fy=("cross_fy", "sum"),
        )
        .reset_index()
    )

    out = master[["work_id"]].merge(grp, on="work_id", how="left")
    out["dup_partner_count"] = out["dup_partner_count"].fillna(0).astype(int)
    out["dup_partner_cross_fy"] = out["dup_partner_cross_fy"].fillna(0).astype(int)
    out["dup_partner_sim_max"] = out["dup_partner_sim_max"].fillna(0.0)
    if config.DUP_CROSS_FY_ONLY:
        out["has_duplicate_lead"] = out["dup_partner_cross_fy"] > 0
    else:
        out["has_duplicate_lead"] = out["dup_partner_count"] > 0
    return out