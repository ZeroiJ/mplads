SIH 2026 problem statement SIH26102: fraud/anomaly detection over MPLADS (public works scheme, 543 Lok Sabha + Rajya Sabha MPs, ~₹5cr/year each). Customer = enforcement agencies (ED/CBI/CVC/ACB), not the public. Output = evidence trail + legal route, never an accusation or verdict.

Locked rules — never violate these
1. Model NEVER outputs legal citations. Fraud-type→statute mapping is a HARDCODED lookup table only.
2. Never drop unparseable "NA-" work IDs — keep them with a flag.
3. Work field splits into ID + TITLE, not ID + Category. "Work Category" (Normal/Others, Trust and Society) is its own separate column — do not conflate the two.
4. Never silently swallow a wrong number or failed check — report the actual result, even if it disproves an earlier claim.
5. Smoke-test / dummy-data metrics (e.g. val_acc 1.0) NEVER appear in the final report. Only real training-run numbers count.
6. No fraud labels used in training. Detection is rule-based (thresholds) + unsupervised (Isolation Forest) + self-supervised (embedding fine-tuning on duplicate/non-duplicate pairs). Real supervised labels only arrive later via the agency feedback loop — that's roadmap, not built yet.

Current state
- Master data: mplads_master_works_v3.csv, 17,879 works, 28 cols (Lok Sabha only — Rajya Sabha not yet pulled, blocked on Sarthak)
- Baseline captured: frozen paraphrase-multilingual-MiniLM-L12-v2 scored on 10 fixed jury pairs, saved to metrics/baseline_metrics.csv BEFORE any fine-tuning touched the model
- pairs.csv built: 70,607 pairs (30,034 pos / 30,034 hard-neg / 10,539 easy-neg), labeled via description-similarity ratio within same (mp_no, recommended_amount) group
- KNOWN GAP: positive pairs were labeled by text-similarity ratio, which likely means cross-vocabulary duplicates (Hindi-transliterated title vs English title, e.g. Shauchalaya vs toilet) are NOT represented as positive pairs. Before claiming "fixed cross-language duplicate matching," verify this — if the gap is real, scope the claim narrowly to "improves literal/near-identical duplicate detection" only.

Task: fine-tune paraphrase-multilingual-MiniLM-L12-v2
1. Run the cross-vocabulary check on pairs.csv first (see KNOWN GAP above) — report findings honestly before proceeding
2. Reinstall CUDA torch (--index-url https://download.pytorch.org/whl/cu124 --force-reinstall)
3. Run finetune.py for real (not smoke test)
4. Run evaluate_after.py — compare against baseline_metrics.csv
5. Log every step to GitHub (commit per meaningful step, not one giant commit) and Notion (progress log page)

Operational rules
- One task at a time, sequential — EXCEPT while fine-tuning is actively running: spawn a parallel logging agent to post progress updates (GitHub commit + Notion note) without interrupting the training process
- CRITICAL: since agents die on inactivity, make sure finetune.py itself prints a heartbeat/progress line at LEAST every 30-60 seconds during training (per-step or per-N-seconds), even if just "step X/Y, loss=Z" — do not let training run silently for minutes at a time, or the process may be mistaken for dead and killed
- If VRAM OOMs on the RTX 3050 (4GB), drop batch size before dropping anything else — do not silently switch back to CPU without saying so

User is offline / unreachable
Do not wait for confirmation on routine steps. Only pause and flag clearly (in Notion + a direct note) if:
- The cross-vocabulary check reveals the fine-tune won't meaningfully help the demo's core pitch
- Training fails repeatedly (3+ crashes) with the same error
- Any legal-citation-output rule would be violated by a design choice
Otherwise, proceed autonomously through the full plan.