"""Feature engineering (FEAT box): F1-F4 numeric features per work.

F1  sanctioned - recommended delta (normalized)
F2  disbursed / sanctioned ratio
F3  vendor count per work
F4  days between stage transitions (recommended -> sanctioned, sanctioned -> completed)

These feed the Isolation Forest (D1). All derived fields are NaN-safe.
"""

import pandas as pd


def parse_dates(df: pd.DataFrame, cols) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        df[c] = pd.to_datetime(df[c], errors="coerce", format="%Y-%m-%d")
    return df


def build_features(df: pd.DataFrame, ref_date=None) -> pd.DataFrame:
    """Return df with F1..F4 plus helper numeric columns. Input df is the master."""
    ref = pd.Timestamp(ref_date) if ref_date else pd.Timestamp.now().normalize()
    df = parse_dates(df, ["recommended_date", "sanction_date", "completion_date"])
    out = df.copy()

    # F1: normalized sanction overrun vs recommendation
    rec = out["recommended_amount"].astype(float).fillna(0.0)
    san = out["sanction_amount"].astype(float).fillna(0.0)
    denom = rec.replace(0, pd.NA)
    out["f1_sanction_delta_ratio"] = ((san - rec) / denom).where((rec > 0) & (san > 0), pd.NA)

    # F2: disbursed / sanctioned ratio
    out["f2_disbursed_ratio"] = (out["amount_disbursed"].astype(float) / san).where(san > 0, pd.NA)

    # F3: vendor / payment count
    out["f3_vendor_count"] = out["exp_vendors"].astype(float).fillna(0.0)
    out["f3_payment_count"] = out["exp_pay_count"].astype(float).fillna(0.0)

    # F4: stage-transition days
    out["f4_days_rec_to_san"] = (out["sanction_date"] - out["recommended_date"]).dt.days.astype(float)
    out["f4_days_san_to_done"] = (out["completion_date"] - out["sanction_date"]).dt.days.astype(float)
    out["f4_days_san_to_ref"] = (ref - out["sanction_date"]).dt.days.astype(float).where(out["sanction_date"].notna(), pd.NA)

    # Aux numeric features used by Isolation Forest
    out["aux_sanction_amount"] = san
    out["aux_amount_disbursed"] = out["amount_disbursed"].astype(float).fillna(0.0)
    out["aux_exp_total"] = out["exp_total"].astype(float).fillna(0.0)
    out["aux_exp_paid"] = out["exp_paid"].astype(float).fillna(0.0)
    out["aux_alloc_limit"] = out["alloc_limit"].astype(float).fillna(0.0)
    out["aux_exp_vendors"] = out["f3_vendor_count"]
    out["aux_exp_pay_count"] = out["f3_payment_count"]
    return out


FEATURE_COLUMNS = [
    "f1_sanction_delta_ratio",
    "f2_disbursed_ratio",
    "f3_vendor_count",
    "f4_days_rec_to_san",
    "f4_days_san_to_done",
    "f4_days_san_to_ref",
    "aux_sanction_amount",
    "aux_amount_disbursed",
    "aux_exp_total",
    "aux_alloc_limit",
    "aux_exp_pay_count",
]