"""Evidence dossier (E1): per-work investigation pack pulled from raw files.

For each flagged work, pull the matching rows from the original raw imports
(Works Recommended / Works Sanctioned / Works Completed / Expenditure) plus a
checklist of what the flag means and what to verify. Output:
  evidence/<work_id>.md           one dossier per flagged work
  evidence/dossiers.md            index of all dossiers
"""

import os
import re

import pandas as pd

from . import config
from .classify import classify
from .legal import legal_route

RAW_FILES = {
    "recommended": f"{config.RAW_DIR}/Works Recommended.csv",
    "sanctioned": f"{config.RAW_DIR}/Works Sanctioned.csv",
    "completed": f"{config.RAW_DIR}/Works Completed.csv",
    "expenditure": f"{config.RAW_DIR}/Expenditure on Completed and On-going Works as on Date.csv",
}


def _safe_name(work_id: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]", "_", str(work_id))
    return s.strip("_") or "work"


_ID_RE = re.compile(r"(MP\d+/20\d\d-\d\d\d\d/\d+)")


def _find_row(path: str, work_id: str) -> pd.Series | None:
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, low_memory=False)
    for col in df.columns:
        s = df[col].astype(str)
        extracted = s.str.extract(_ID_RE, expand=False)
        hit = extracted == str(work_id).strip()
        if hit.any():
            return df[hit].iloc[0]
    return None


def _kv(series: pd.Series | None, cols) -> str:
    if series is None:
        return "_missing_"
    picked = []
    for c in series.index:
        if any(k.lower() in c.lower() for k in cols):
            picked.append(f"{c}: {series[c]}")
    return "; ".join(picked) if picked else "_missing_"


def _template(work: pd.Series, rows: dict, flag_reasons: str) -> str:
    cls = classify(work)
    legal = legal_route(cls["fraud_type"] if work.get("is_flagged") else "statistical_anomaly")
    lines = []
    lines.append(f"# Work {work['work_id']}")
    lines.append("")
    lines.append(f"- **Risk score:** `{work.get('risk_score', '?')}/100`  ")
    lines.append(f"- **Suspected pattern:** `{cls['fraud_type'] or 'none'}`  ")
    lines.append(f"- **Flags:** {flag_reasons or '(row-level flags none; aggregated signal)'}")
    lines.append("")
    lines.append("## Flag reasoning")
    lines.append("")
    lines.append(f"> {work.get('reasons', '') or 'see checklist below'}")
    lines.append("")
    if cls["fraud_type"]:
        lines.append("## Fraud classification (FC1 - pattern only, no verdict)")
        lines.append("")
        lines.append(f"- Signals: `{', '.join(cls['signals']) or 'none'}`")
        lines.append(f"- Narrative: {cls['narrative']}")
        lines.append("")
        lines.append("## Legal route (LG1 - hardcoded lookup, model never cites law)")
        lines.append("")
        lines.append(f"- Route: **{legal['route']}**")
        if legal["statutes"]:
            lines.append("- Statutory areas to assess: " + "; ".join(legal["statutes"]))
        lines.append(f"- Refer to: {legal['refer_to']}")
        lines.append(f"- Note: {legal['note']}")
        lines.append("")
    for src, s in rows.items():
        lines.append(f"## Raw {src.capitalize()} row")
        lines.append("")
        lines.append(_kv(s, ["work", "sanction", "recommend", "amount", "date", "status", "description", "state"])
                     or "_missing_")
        lines.append("")
    lines.append("## Verification checklist (human step)")
    lines.append("")
    lines.append("- [ ] Confirm duplicate/description against constituency records")
    lines.append("- [ ] Check stage dates against original MIS claim")
    lines.append("- [ ] Contact controlling authority for status")
    lines.append("- [ ] Mark verdict: legitimate / needs-flagging / refer")
    lines.append("")
    lines.append("---")
    lines.append(f"_Auto-generated dossier. Model does **not** issue legal conclusions._")
    return "\n".join(lines)


def build_dossiers(flags: pd.DataFrame, limit=None) -> list[str]:
    os.makedirs(config.EVIDENCE_DIR, exist_ok=True)
    flagged = flags[flags["is_flagged"]].copy()
    if limit:
        flagged = flagged.head(limit)

    index_rows = []
    for _, row in flagged.iterrows():
        wid = row["work_id"]
        rows = {name: _find_row(path, wid) for name, path in RAW_FILES.items()}
        md = _template(row, rows, row.get("reasons", ""))
        fname = os.path.join(config.EVIDENCE_DIR, f"{_safe_name(wid)}.md")
        with open(fname, "w") as f:
            f.write(md)
        index_rows.append(f"- [{wid}]({os.path.basename(fname)}) — risk {row.get('risk_score', '?')}/100 — {row.get('reasons', '')}")

    idx = f"# Flagged-work dossiers ({len(index_rows)})\n\n"
    idx += "\n".join(index_rows) + "\n"
    with open(f"{config.EVIDENCE_DIR}/dossiers.md", "w") as f:
        f.write(idx)
    return index_rows