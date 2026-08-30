"""Deterministic rule flags (D3): delay / overrun / abandoned / unparseable.

These are pure rules (no model) - the "why this work looks wrong" part that
must be transparent and reproducible for investigators. Every flag row carries
a human-readable reason string.
"""

import pandas as pd

from . import config


def flag_unparseable(work_id) -> bool:
    return str(work_id).strip().upper().startswith("NA-")


def rule_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add boolean flag columns to a copy of df. Returns (out, flag_columns)."""
    out = df.copy()
    out["flag_unparseable"] = out["work_id"].map(flag_unparseable)

    is_san = out.get("is_sanctioned", pd.Series(0, index=out.index)) == 1
    is_done = out.get("is_completed", pd.Series(0, index=out.index)) == 1

    san_date = pd.to_datetime(out["sanction_date"], errors="coerce", format="%Y-%m-%d")
    stall = pd.Timestamp(config.STALL_BEFORE)

    # stalled/abandoned: sanctioned before threshold and never completed
    out["flag_stalled"] = is_san & ~is_done & san_date.lt(stall)

    # not completed at all (any sanction date) - wider, lower confidence
    out["flag_incomplete"] = is_san & ~is_done & san_date.notna()

    # sanction overrun: sanctioned amount much higher than recommended
    rec = out["recommended_amount"].astype(float).fillna(0.0)
    san = out["sanction_amount"].astype(float).fillna(0.0)
    out["flag_sanction_overrun"] = (rec > 0) & (san > rec * config.SANCTION_DELTA_RATIO)

    # zero disbursal: sanctioned but nothing paid
    out["flag_zero_disbursal"] = is_san & (out["amount_disbursed"].astype(float).fillna(0.0) == 0)

    # over-expenditure: paid out more than sanctioned
    out["flag_cost_overrun"] = is_san & (out["exp_total"].astype(float).fillna(0.0) > san)

    # zero physical progress flags are derived from missing completion + sanctions above.

    flag_cols = [
        "flag_unparseable",
        "flag_stalled",
        "flag_incomplete",
        "flag_sanction_overrun",
        "flag_zero_disbursal",
        "flag_cost_overrun",
    ]
    return out, flag_cols


def rule_reason(row, flag_cols) -> str:
    """Human-readable reason string built from the flagged columns."""
    reasons = {
        "flag_unparseable": "unparseable/NA- work id (kept, flagged)",
        "flag_stalled": f"stalled: sanctioned before {config.STALL_BEFORE}, never completed",
        "flag_incomplete": "sanctioned but never completed",
        "flag_sanction_overrun": f"sanctioned > {int(config.SANCTION_DELTA_RATIO*100)}% of recommended amount",
        "flag_zero_disbursal": "sanctioned but zero amount disbursed",
        "flag_cost_overrun": "paid out more than sanctioned amount",
    }
    hits = [reasons[c] for c in flag_cols if row.get(c)]
    return "; ".join(hits) if hits else ""