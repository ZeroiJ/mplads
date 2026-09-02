"""Raw MPLADS CSVs -> master DataFrame (the D0 assembly layer).

This lets the pipeline start *entirely* from uploaded raw CSVs with no
precomputed `mplads_master_works_v3.csv`. It reproduces the master schema from
the six raw files:

    Works Recommended.csv
    Works Sanctioned.csv
    Works Completed.csv
    Expenditure on Completed and On-going Works as on Date.csv
    18th lok sabha allocated limit for honble MPs.csv
    Amount consented for Calamity.csv

Output columns match config.MASTER (see engine.py / features.py expectations):
work_id, mp_no, fy, work_no, mp_name, mp_state, state, constituency,
work_category, work_desc, work_status, recommended_date, recommended_amount,
sanction_date, sanction_amount, completion_date, amount_disbursed,
exp_pay_count, exp_total, exp_inprogress, exp_paid, exp_vendors, alloc_limit,
calamity_consent, is_recommended, is_sanctioned, is_completed, has_expenditure
"""

from __future__ import annotations

import glob
import os
import re

import pandas as pd

# ---------------------------------------------------------------------------
# Raw file name -> canonical role. Uploads reuse these exact names.
# ---------------------------------------------------------------------------
RAW_FILENAMES = {
    "recommended": "Works Recommended.csv",
    "sanctioned": "Works Sanctioned.csv",
    "completed": "Works Completed.csv",
    "expenditure": "Expenditure on Completed and On-going Works as on Date.csv",
    "alloc": "18th lok sabha allocated limit for honble MPs.csv",
    "calamity": "Amount consented for Calamity.csv",
}

# A work_id is embedded inside the free-text "Work"/"WORK"/"Work ID" field,
# e.g. "MP181/2020-2021/822555". Extract with this pattern across files.
_WORK_ID_RE = re.compile(r"(MP\d+/\d{4}-\d{4}/\d+)")


def _extract_work_id(series: pd.Series) -> pd.Series:
    """Extract the MPLADS work id from the raw free-text id column."""
    return series.astype(str).str.extract(_WORK_ID_RE, expand=False)


def _money(series: pd.Series) -> pd.Series:
    """Parse Indian rupee strings like '1,23,456 ( ₹ )' -> float rupees."""
    digits = series.astype(str).str.replace(r"[^\d]", "", regex=True)
    return pd.to_numeric(digits, errors="coerce").fillna(0.0)


def _date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def build_master_from_raw(raw_dir: str) -> pd.DataFrame:
    """Assemble the master DataFrame from the raw CSVs in ``raw_dir``.

    Any optional file that is missing is treated as empty (columns left null).
    The union of works comes from Recommended + Sanctioned + Completed.
    """
    paths = {}
    for role, fname in RAW_FILENAMES.items():
        p = os.path.join(raw_dir, fname)
        if os.path.exists(p):
            paths[role] = p
        elif glob.glob(p):
            paths[role] = glob.glob(p)[0]

    def _read(role: str) -> pd.DataFrame | None:
        p = paths.get(role)
        if not p:
            return None
        return pd.read_csv(p, low_memory=False)

    rec = _read("recommended")
    san = _read("sanctioned")
    com = _read("completed")
    exp = _read("expenditure")
    alloc = _read("alloc")
    calamity = _read("calamity")

    # --- base on the UNION of work ids across all sources ------------------
    # (the master includes works that appear only in sanctioned / completed /
    # expenditure, not just recommended.)
    unions = []
    if rec is not None:
        u = rec.copy()
        u["work_id"] = _extract_work_id(u.get("WORK"))
        unions.append(u)
    if san is not None:
        u = san.copy()
        u["work_id"] = _extract_work_id(u.get("Work"))
        unions.append(u)
    if com is not None:
        u = com.copy()
        u["work_id"] = _extract_work_id(u.get("Work"))
        unions.append(u)
    if exp is not None:
        u = exp.copy()
        u["work_id"] = _extract_work_id(u.get("Work ID"))
        unions.append(u)

    if not unions:
        raise ValueError("No raw CSV files provided with a work id.")

    base = pd.concat(unions, ignore_index=True)
    base = base[base["work_id"].notna()].drop_duplicates("work_id")

    def _col(df, *names, default=None):
        for n in names:
            if df is not None and n in df.columns:
                return df[n]
        return default

    out = pd.DataFrame({"work_id": base["work_id"]})
    out["work_desc"] = ""
    out["work_category"] = ""
    out["work_status"] = ""
    out["state"] = ""
    out["mp_name"] = ""
    out["constituency"] = ""
    out["recommended_date"] = pd.NaT
    out["recommended_amount"] = 0.0
    out["sanction_date"] = pd.NaT
    out["sanction_amount"] = 0.0
    out["completion_date"] = pd.NaT
    out["amount_disbursed"] = 0.0
    out["exp_pay_count"] = 0
    out["exp_total"] = 0.0
    out["exp_inprogress"] = 0.0
    out["exp_paid"] = 0.0
    out["exp_vendors"] = 0
    out["alloc_limit"] = 0.0
    out["calamity_consent"] = 0.0
    out["is_recommended"] = False
    out["is_sanctioned"] = False
    out["is_completed"] = False
    out["has_expenditure"] = False

    out = out.set_index("work_id")

    # --- merge recommended attributes -------------------------------------
    if rec is not None:
        r = rec.copy()
        r["work_id"] = _extract_work_id(r.get("WORK"))
        r = r[r["work_id"].notna()].drop_duplicates("work_id").set_index("work_id")
        r["_desc"] = _col(r, "Work description", "Work Description", default="").astype(str)
        r["_cat"] = _col(r, "Work category", "Work Category", default="")
        r["_state"] = _col(r, "State", default="").astype(str)
        r["_mp"] = _col(r, "Hon'ble Members of Parliament", "Hon'ble Members of Parliaments", default="").astype(str)
        r["_con"] = _col(r, "Constituency", default="").astype(str)
        r["_rd"] = _date(_col(r, "Recommended date", default=""))
        r["_ra"] = _money(_col(r, "RECOMMENDED AMOUNT   ( ₹ )", "Recommended Amount", default=""))
        for wid in r.index:
            if wid in out.index:
                out.at[wid, "work_desc"] = r.at[wid, "_desc"]
                out.at[wid, "work_category"] = r.at[wid, "_cat"]
                out.at[wid, "state"] = r.at[wid, "_state"]
                out.at[wid, "mp_name"] = r.at[wid, "_mp"]
                out.at[wid, "constituency"] = r.at[wid, "_con"]
                out.at[wid, "recommended_date"] = r.at[wid, "_rd"]
                out.at[wid, "recommended_amount"] = r.at[wid, "_ra"]
                out.at[wid, "is_recommended"] = True

    # --- merge sanctions ---------------------------------------------------
    if san is not None:
        s = san.copy()
        s["work_id"] = _extract_work_id(s.get("Work"))
        s = s[s["work_id"].notna()].drop_duplicates("work_id")
        s = s.set_index("work_id")
        s["_san_amount"] = _money(_col(s, "Sanction Amount ( ₹ )", default=""))
        s["_san_date"] = _date(_col(s, "Sanction Date", default=""))
        s["_san_status"] = _col(s, "Work Status", default="")
        s["_san_work_desc"] = _col(s, "Work description", default="")
        s["_san_state"] = _col(s, "State", default="").astype(str)
        s["_san_mp"] = _col(s, "Hon'ble Members of Parliament", default="").astype(str)
        s["_san_con"] = _col(s, "Constituency", default="").astype(str)
        for wid in s.index:
            if wid in out.index:
                out.at[wid, "sanction_amount"] = s.at[wid, "_san_amount"]
                out.at[wid, "sanction_date"] = s.at[wid, "_san_date"]
                out.at[wid, "work_status"] = s.at[wid, "_san_status"]
                out.at[wid, "is_sanctioned"] = True
                if out.at[wid, "work_desc"] == "":
                    out.at[wid, "work_desc"] = s.at[wid, "_san_work_desc"]
                if out.at[wid, "mp_name"] == "":
                    out.at[wid, "mp_name"] = s.at[wid, "_san_mp"]
                if out.at[wid, "state"] == "":
                    out.at[wid, "state"] = s.at[wid, "_san_state"]
                if out.at[wid, "constituency"] == "":
                    out.at[wid, "constituency"] = s.at[wid, "_san_con"]

    # --- merge completed ---------------------------------------------------
    if com is not None:
        c = com.copy()
        c["work_id"] = _extract_work_id(c.get("Work"))
        c = c[c["work_id"].notna()].drop_duplicates("work_id")
        c = c.set_index("work_id")
        c["_c_amt"] = _money(_col(c, "Amount Disbursed ( ₹ )", default=""))
        c["_c_date"] = _date(_col(c, "Completion Date", default=""))
        c["_c_desc"] = _col(c, "Work Description", default="")
        c["_c_state"] = _col(c, "State", default="").astype(str)
        c["_c_mp"] = _col(c, "Hon'ble Members of Parliament", default="").astype(str)
        c["_c_con"] = _col(c, "Constituency", default="").astype(str)
        for wid in c.index:
            if wid in out.index:
                out.at[wid, "completion_date"] = c.at[wid, "_c_date"]
                out.at[wid, "is_completed"] = True
                if out.at[wid, "amount_disbursed"] == 0.0:
                    out.at[wid, "amount_disbursed"] = c.at[wid, "_c_amt"]
                if out.at[wid, "work_desc"] == "":
                    out.at[wid, "work_desc"] = c.at[wid, "_c_desc"]
                if out.at[wid, "mp_name"] == "":
                    out.at[wid, "mp_name"] = c.at[wid, "_c_mp"]
                if out.at[wid, "state"] == "":
                    out.at[wid, "state"] = c.at[wid, "_c_state"]
                if out.at[wid, "constituency"] == "":
                    out.at[wid, "constituency"] = c.at[wid, "_c_con"]

    # --- merge expenditure aggregates -------------------------------------
    if exp is not None:
        e = exp.copy()
        e["work_id"] = _extract_work_id(e.get("Work ID"))
        e = e[e["work_id"].notna()]
        if len(e):
            g = e.groupby("work_id").agg(
                exp_pay_count=("Expenditure Date", "count"),
                exp_total=("Fund Disbursed Amount ( ₹ )", lambda s: _money(s).sum()),
                exp_vendors=("Vendor Name", "nunique"),
            )
            g["exp_paid"] = g["exp_total"]
            for wid in g.index:
                if wid in out.index:
                    for col in ["exp_pay_count", "exp_total", "exp_paid", "exp_vendors"]:
                        out.at[wid, col] = g.at[wid, col]
                    out.at[wid, "has_expenditure"] = True
                    if out.at[wid, "amount_disbursed"] == 0.0:
                        out.at[wid, "amount_disbursed"] = g.at[wid, "exp_total"]

    # --- alloc limit + calamity consent ------------------------------------
    if alloc is not None:
        a = alloc.copy()
        # match on MP name -> constituency -> limit
        a["_name"] = _col(a, "Hon'ble Members of Parliaments", default="").str.strip()
        a["_alloc"] = _money(_col(a, "Allocated AMOUNT ( ₹ )", default=""))
        namemap = dict(zip(a["_name"], a["_alloc"]))
        out["alloc_limit"] = out["mp_name"].map(namemap).fillna(0.0)

    if calamity is not None:
        cl = calamity.copy()
        cl["_name"] = _col(cl, "Hon'ble Members of Parliament", default="").str.strip()
        cl["_consent"] = _money(_col(cl, "Consent Amount ( ₹ )", default=""))
        consentmap = dict(zip(cl["_name"], cl["_consent"]))
        out["calamity_consent"] = out["mp_name"].map(consentmap).fillna(0.0)

    # --- fiscal year + mp_no from work_id ---------------------------------
    out = out.reset_index()

    def _fy(wid: str):
        m = re.search(r"(\d{4})-(\d{4})", str(wid))
        return f"{m.group(1)}-{m.group(2)}" if m else ""

    out["fy"] = out["work_id"].map(_fy)
    out["mp_no"] = out["work_id"].map(lambda w: re.search(r"(\d+)", str(w).replace("MP", "")).group(1) if re.search(r"(\d+)", str(w)) else "")
    out["work_no"] = out["work_id"].map(
        lambda w: re.search(r"/(\d+)$", str(w)).group(1) if re.search(r"/(\d+)$", str(w)) else ""
    )
    out["mp_state"] = out["state"]

    # ordering to match master
    cols = [
        "work_id", "mp_no", "fy", "work_no", "mp_name", "mp_state", "state",
        "constituency", "work_category", "work_desc", "work_status",
        "recommended_date", "recommended_amount", "sanction_date", "sanction_amount",
        "completion_date", "amount_disbursed", "exp_pay_count", "exp_total",
        "exp_inprogress", "exp_paid", "exp_vendors", "alloc_limit",
        "calamity_consent", "is_recommended", "is_sanctioned", "is_completed",
        "has_expenditure",
    ]
    out = out[cols].drop_duplicates("work_id").reset_index(drop=True)
    return out


def load_master(raw_dir: str) -> pd.DataFrame:
    """Top-level entry: build master purely from raw CSVs (no precomputed file)."""
    return build_master_from_raw(raw_dir)