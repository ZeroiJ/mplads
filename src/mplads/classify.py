"""FC1 - Fraud classification: map detection signals to a fraud type + narrative.

Important (locked rule): this maps *detected patterns* to *suspected* fraud types
for a human investigator. It never asserts guilt. Legal consequences are applied
exclusively by the hardcoded lookup in legal.py (LG1) - never by the ML/rule path.

Signal -> type mapping (deterministic, explainable):
  duplicate_lead          -> duplicate claim (resubmission)
  stalled + zero_disbursal-> ghost work / siphoned funds
  cost_overrun            -> over-invoicing / over-expenditure
  sanction_overrun        -> over-invoicing risk (inflated sanction)
  anomaly                 -> statistical anomaly (low / high ball)
Multiple signals: pick the highest-priority type and attach the rest as corroboration.
"""

import pandas as pd

_FRAUD_TYPES = ("duplicate_claim", "ghost_work", "siphoned_funds", "over_invoicing", "statistical_anomaly")


def classify(row: pd.Series) -> dict:
    """Return {'fraud_type', 'priority', 'corroboration', 'narrative'} for one flagged work."""
    sig = []
    if row.get("has_duplicate_lead"):
        sig.append("duplicate_resubmission")
    if row.get("flag_stalled") and row.get("flag_zero_disbursal"):
        sig.append("stalled_no_funds")
    elif row.get("flag_stalled"):
        sig.append("stalled")
    if row.get("flag_zero_disbursal"):
        sig.append("zero_disbursal")
    if row.get("flag_cost_overrun"):
        sig.append("cost_overrun")
    if row.get("flag_sanction_overrun"):
        sig.append("sanction_overrun")
    if row.get("is_anomaly"):
        sig.append("anomaly")

    if "duplicate_resubmission" in sig:
        ftype = "duplicate_claim"
        priority = 1
        narrative = (
            "Duplicate-claim candidate: a near-identical work description for the same "
            "MP and amount appears in a different financial year (cross-FY partner)."
        )
    elif "stalled_no_funds" in sig or "stalled" in sig:
        ftype = "siphoned_funds" if "stalled_no_funds" in sig else "ghost_work"
        priority = 2 if ftype == "siphoned_funds" else 3
        narrative = (
            f"Work was sanctioned ({row.get('sanction_amount', '?')}) but has not been "
            f"completed and has {'zero amount disbursed' if 'stalled_no_funds' in sig else 'no recorded completion'}."
        )
    elif "cost_overrun" in sig or "sanction_overrun" in sig:
        ftype = "over_invoicing"
        priority = 4
        narrative = "Amount paid or sanctioned exceeds the recommended/sanctioned baseline (cost or sanction overrun)."
    else:
        ftype = "statistical_anomaly"
        priority = 5
        narrative = "Statistical outlier on the engineered features (F1-F4) - unusual compared with other works."

    corroboration = [s for s in sig if not (
        (s == "duplicate_resubmission" and ftype == "duplicate_claim")
        or (s in ("stalled_no_funds", "stalled") and ftype in ("siphoned_funds", "ghost_work"))
        or (s in ("cost_overrun", "sanction_overrun") and ftype == "over_invoicing")
        or (s == "anomaly" and ftype == "statistical_anomaly")
    )]
    return {"fraud_type": ftype, "priority": priority, "signals": sig, "corroboration": corroboration, "narrative": narrative}


def annotate(flags: pd.DataFrame) -> pd.DataFrame:
    """Add FC1 columns (fraud_type, fraud_priority, fraud_narrative, fraud_signals) to flags."""
    out = flags.copy()
    res = []
    for _, r in out.iterrows():
        if not r.get("is_flagged"):
            res.append({"fraud_type": "", "fraud_priority": 0, "fraud_signals": "[]",
                        "fraud_narrative": "No detection signal."})
        else:
            c = classify(r)
            res.append({"fraud_type": c["fraud_type"], "fraud_priority": c["priority"],
                        "fraud_signals": ",".join(c["signals"]), "fraud_narrative": c["narrative"]})
    d = pd.DataFrame(res, index=out.index)
    out = pd.concat([out, d], axis=1)
    return out