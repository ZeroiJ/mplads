"""Central configuration: paths, thresholds, feature definitions.

All magic numbers live here (one file) so the detection engine stays configurable
and the thresholds can be justified to judges ("why these features / values").
"""

import os

BASE_DIR = "/home/zeroij/mplads"
DATA_DIR = f"{BASE_DIR}/data"
MASTER = f"{DATA_DIR}/mplads_master_works_v3.csv"
RAW_DIR = f"{DATA_DIR}/raw"
PAIRS = f"{DATA_DIR}/pairs.csv"

METRICS_DIR = f"{BASE_DIR}/metrics"
EVIDENCE_DIR = f"{BASE_DIR}/evidence"
FLAGS_CSV = f"{METRICS_DIR}/flags.csv"
MP_AGGREGATE_CSV = f"{METRICS_DIR}/mp_aggregate.csv"
WORST_OFFENDERS_CSV = f"{METRICS_DIR}/worst_offenders.csv"
REAL_SWEEP_CSV = f"{METRICS_DIR}/real_sweep.csv"

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
CHAMBER = os.environ.get("MPLADS_CHAMBER", "ls")
_MODEL_BEST_TXT = f"{BASE_DIR}/models/{CHAMBER}/best.txt"
if os.path.exists(_MODEL_BEST_TXT):
    BEST_MODEL = open(_MODEL_BEST_TXT).read().strip()
else:
    BEST_MODEL = f"{BASE_DIR}/models/{CHAMBER}/epoch_4.0"

EMBED_BATCH = 256

# --- Rule thresholds (D3) ---------------------------------------------
# A work sanctioned strictly before this date and still not completed is
# "abandoned/stalled". (Anchors the verified RF2 red flag: 1,190 stale works.)
STALL_BEFORE = "2025-01-01"
MIN_DESC_LEN = 10            # rows with shorter/no description are not text-mineable
SANCTION_DELTA_RATIO = 1.20  # sanctioned > 120% of recommended -> sanction overrun flag

# --- Duplicate matching (D2) -------------------------------------------
# Cosine similarity >= this (same MP + same amount group) = duplicate-claim candidate.
DUP_SIM_THRESHOLD = 0.80
# A duplicate *lead* (for risk scoring) is a strong pair across financial years.
DUP_CROSS_FY_ONLY = True

# --- Isolation Forest (D1) ----------------------------------------------
IF_CONTAMINATION = 0.05          # ~5% of works expected anomalous
IF_N_ESTIMATORS = 200
IF_MAX_SAMPLES = 512             # speed on 17,879 rows

# --- Risk score (engine) ------------------------------------------------
# Weights for the transparent risk formula; scores normalized to 0..100.
RISK_WEIGHTS = {
    "stalled": 35,          # sanctioned long ago, never completed
    "unparseable": 10,      # NA-/unparseable work id (kept, flagged)
    "sanction_overrun": 15,  # sanctioned amount >> recommended amount
    "zero_disbursal": 20,    # sanctioned but nothing paid out
    "duplicate_lead": 25,    # cross-FY duplicate resubmission candidate
    "anomaly": 20,           # Isolation Forest outlier
}
MIN_DESC_LEN_FOR_DUP = MIN_DESC_LEN