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

import numpy as np
import pandas as pd

from . import config
from .live_embed import build_pair_table


def load_sweep() -> pd.DataFrame:
    sweep = pd.read_csv(config.REAL_SWEEP_CSV)
    # keep only the fine-tuned model's verdicts (the one we ship)
    return sweep[sweep["model"] == "finetuned"].reset_index(drop=True)


def _aggregate_pairs(pairs: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    """Turn a {work_a, work_b, similarity} table into per-work dup signals."""
    fy = master[["work_id", "fy"]].rename(columns={"fy": "fy"})

    pairs = pairs.merge(
        fy.rename(columns={"fy": "fy_a"}), left_on="work_a", right_on="work_id", how="left"
    ).merge(
        fy.rename(columns={"fy": "fy_b"}), left_on="work_b", right_on="work_id", how="left"
    )
    pairs["cross_fy"] = pairs["fy_a"].fillna("") != pairs["fy_b"].fillna("")

    a = pairs.rename(columns={"work_a": "work_id", "work_b": "partner", "fy_a": "self_fy", "fy_b": "partner_fy"})
    b = pairs.rename(columns={"work_b": "work_id", "work_a": "partner", "fy_b": "self_fy", "fy_a": "partner_fy"})
    stacked = pd.concat(
        [a[["work_id", "partner", "similarity", "cross_fy"]],
         b[["work_id", "partner", "similarity", "cross_fy"]]],
        ignore_index=True,
    )

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


def compute_dup_signals(master: pd.DataFrame) -> pd.DataFrame:
    """Return per-work_id duplicate signals aligned to master's work_id column.

    Uses the precomputed `real_sweep.csv` (offline model sweep). See
    ``compute_dup_signals_live`` for the fully-from-uploads path.
    """
    sweep = load_sweep()
    if sweep.empty:
        raise RuntimeError(f"real_sweep.csv empty/absent: {config.REAL_SWEEP_CSV}")
    return _aggregate_pairs(sweep, master)


def compute_dup_signals_live(
    master: pd.DataFrame,
    embed_many,
    threshold: float = config.DUP_SIM_THRESHOLD,
    batch_size: int = 64,
    max_embeddings: int = 1500,
) -> pd.DataFrame:
    """Duplicate signals computed live from uploaded CSVs (no real_sweep).

    ``embed_many`` is a callable `(batch_texts: List[str]) -> (n, 384) array`
    that embeds a whole batch (e.g. a batched Gradio SSE call to the HF Space).
    Embeds a capped set of work descriptions (``max_embeddings``, prioritised
    by recommended amount) to keep a free HF Space responsive, finds
    near-duplicate pairs within the same (mp_no, rounded recommended-amount)
    group, and aggregates into per-work signals. Rows with empty descriptions
    produce zero signals.
    """
    from .live_embed import build_pair_table, embed_texts_batched

    m = master.reset_index(drop=True)
    desc = m["work_desc"].astype(str).str.strip() if "work_desc" in m.columns else pd.Series("", index=m.index)
    usable = desc.ne("").to_numpy()

    # Prioritise larger-value works within the cap (duplicates of high-value
    # claims matter most); still leaves room for smaller ones.
    order = np.argsort(
        -m["recommended_amount"].replace("", np.nan).astype(float).fillna(0.0).to_numpy()
    )
    idxs = [i for i in order if usable[i]][:max_embeddings]

    if not idxs:
        return _empty_signals(m)

    texts = [desc.iloc[i] for i in idxs]
    embs = embed_texts_batched(texts, embed_many, batch_size=batch_size)

    # group key: mp_no + recommended_amount rounded to nearest 1000
    mp = m["mp_no"].astype(str).fillna("").to_numpy()
    amt = m["recommended_amount"].replace("", np.nan).astype(float).fillna(0.0).to_numpy()
    key_arr = [f"{mp[i]}|{int(round(amt[i] / 1000))}" for i in idxs]

    pairs = build_pair_table(
        [m["work_id"].iloc[i] for i in idxs],
        key_arr,
        embs,
        threshold=threshold,
    )

    if pairs.empty:
        return _empty_signals(m)

    return _aggregate_pairs(pairs, m)


def _empty_signals(master: pd.DataFrame) -> pd.DataFrame:
    out = master[["work_id"]].copy()
    out["dup_partner_count"] = 0
    out["dup_partner_sim_max"] = 0.0
    out["dup_partner_cross_fy"] = 0
    out["has_duplicate_lead"] = False
    return out