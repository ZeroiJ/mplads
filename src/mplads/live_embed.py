"""Live embedding client: get 384-dim vectors for work descriptions.

Calls a Hugging Face Space exposing `POST /predict` -> { "text": "..." } ->
JSON array of 384 floats. Used by the live-duplicate path (D2) so the backend
does not need a precomputed embeddings sweep and can run entirely from uploaded
raw CSVs. The backend never loads the sentence-transformer model itself.
"""

from __future__ import annotations

from typing import Callable, Dict, List

import numpy as np

DEFAULT_THRESHOLD = 0.80

# Shared cosine implementation (no scipy needed on the backend host).
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    an = np.linalg.norm(a, axis=1, keepdims=True)
    bn = np.linalg.norm(b, axis=1, keepdims=True)
    an[an == 0] = 1e-9
    bn[bn == 0] = 1e-9
    a_n = a / an
    b_n = b / bn
    return np.clip(a_n @ b_n.T, -1.0, 1.0)


def embed_texts(
    texts: List[str],
    embed_one: Callable[[str], List[float]],
    batch_size: int = 64,
    flat: bool = True,
) -> np.ndarray:
    """Embed a list of texts via ``embed_one`` (which calls the HF Space).

    Returns an (n_texts, 384) float array. Failing embeddings fall back to a
    zero vector so detection still proceeds (those rows simply won't match).
    """
    vecs: List[np.ndarray] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for t in batch:
            try:
                v = np.asarray(embed_one(t), dtype=float)
                if v.ndim == 0 or len(v) == 0:
                    v = np.zeros(384)
            except Exception:
                v = np.zeros(384)
            if v.ndim == 1 and v.shape[0] >= 384:
                vecs.append(v[:384])
            else:
                vecs.append(np.zeros(384))
    if not vecs:
        return np.zeros((0, 384))
    return np.vstack(vecs)


def build_pair_table(
    work_ids: List[str],
    group_keys: List[str],
    embs: np.ndarray,
    threshold: float = DEFAULT_THRESHOLD,
) -> "pd.DataFrame":
    """Return duplicate pairs {work_a, work_b, similarity} within group keys.

    Only pairs sharing the same ``group_keys`` (e.g. mp_no + rounded amount)
    and with cosine >= ``threshold`` are kept.
    """
    import pandas as pd

    pairs = []
    seen: Dict[frozenset, float] = {}
    n = len(work_ids)
    for i in range(n):
        for j in range(i + 1, n):
            if group_keys[i] == group_keys[j]:
                s = float(cosine_similarity(embs[i : i + 1], embs[j : j + 1])[0, 0])
                if s >= threshold:
                    key = frozenset((work_ids[i], work_ids[j]))
                    if key not in seen or s > seen[key]:
                        seen[key] = s
    if seen:
        keys = list(seen.keys())
        pairs = [
            {"work_a": sorted(k)[0], "work_b": sorted(k)[1], "similarity": seen[k]}
            for k in keys
        ]
    return pd.DataFrame(pairs)