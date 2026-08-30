"""
Real-data duplicate sweep: does the fine-tuned model surface real duplicate-claim
candidates in the actual MPLADS works?

Method (mirrors the training recipe):
  - Group works by (mp_no, recommended_amount)
  - Embed work_desc with the fine-tuned model (and separately the frozen model)
  - Within each group, cosine-sim all pairs; flag sim >= 0.80 (the training positive
    threshold) as a duplicate-claim candidate

Outputs metrics/real_sweep.csv with the candidate pairs, so a human can confirm whether
the flagged pairs are genuine duplicate resubmissions (real fraud lead) or false positives.
"""

import csv
import os
import sys
import time

import pandas as pd
import torch
from sentence_transformers import SentenceTransformer, util

BASE = "/home/zeroij/mplads"
MASTER = f"{BASE}/data/mplads_master_works_v3.csv"
OUT = f"{BASE}/metrics/real_sweep.csv"
POS_THRESHOLD = 0.80
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BEST = open(f"{BASE}/models/best/best.txt").read().strip()
MIN_GROUP = 2
BATCH = 256


def sweep(model, df, model_label):
    recs = []
    t0 = time.time()
    n = len(df)
    for gi, ( (mp_no, amt), grp) in enumerate(df.groupby(["mp_no", "recommended_amount"], dropna=False)):
        if len(grp) < MIN_GROUP:
            continue
        descs = grp["work_desc"].to_list()
        if not any(len(d) >= 10 for d in descs):
            continue
        if len(descs) > 2000:
            descs = descs[:2000]
        emb = model.encode(
            descs,
            batch_size=BATCH,
            convert_to_tensor=True,
            normalize_embeddings=True,
        )
        sims = util.cos_sim(emb, emb)
        ids = list(grp["work_id"])
        sts = list(grp["work_status"])
        mps = list(grp["mp_name"])
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                s = float(sims[i][j])
                if s >= POS_THRESHOLD:
                    recs.append({
                        "model": model_label,
                        "similarity": round(s, 4),
                        "work_a": ids[i],
                        "work_b": ids[j],
                        "work_status_a": sts[i],
                        "work_status_b": sts[j],
                        "mp_name": mps[i],
                    })
        if gi % 500 == 0:
            print(f"  {model_label}: {gi}/{n} groups, found {len(recs)}", flush=True)
    print(f"  {model_label} done in {time.time()-t0:.1f}s, total {len(recs)}", flush=True)
    return recs


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df = pd.read_csv(MASTER)
    df["work_desc"] = df["work_desc"].fillna("").astype(str).str.strip()
    df["work_desc"] = df["work_desc"].where(df["work_desc"].str.len() >= 10)
    df = df.dropna(subset=["work_desc"]).copy()
    df["recommended_amount"] = df["recommended_amount"].fillna(0.0)
    print(f"works scanned: {len(df)}  groups: {df.groupby(['mp_no','recommended_amount']).ngroups}", flush=True)

    fine = SentenceTransformer(BEST)
    fine.eval()
    ft_recs = sweep(fine, df, "finetuned")

    frozen = SentenceTransformer(MODEL_NAME)
    frozen.eval()
    fz_recs = sweep(frozen, df, "frozen")

    all_recs = ft_recs + fz_recs
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_recs[0].keys()) if all_recs else ["model"])
        w.writeheader()
        w.writerows(all_recs)

    print(f"\n=== real-data duplicate candidates (sim >= {POS_THRESHOLD}) ===", flush=True)
    print(f"frozen   : {len(fz_recs)} pairs", flush=True)
    print(f"finetuned: {len(ft_recs)} pairs", flush=True)
    fz_set = {(x["work_a"], x["work_b"]) for x in fz_recs} | {(x["work_b"], x["work_a"]) for x in fz_recs}
    excl = [r for r in ft_recs if (r["work_a"], r["work_b"]) not in fz_set]
    print(f"newly flagged by fine-tune only: {len(excl)}", flush=True)
    if ft_recs:
        print("\n=== top 10 finetuned candidates (review these by hand) ===", flush=True)
        for r in sorted(ft_recs, key=lambda x: -x["similarity"])[:10]:
            print(f"  {r['similarity']:.3f} | {r['work_a']} ({r['work_status_a']}) ~ {r['work_b']} ({r['work_status_b']}) | MP {r['mp_name']}", flush=True)
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    sys.exit(main())