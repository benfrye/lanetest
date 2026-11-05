"""Build research/history/house_<year>.json from the parsed Wikipedia tables, the Daily Kos / Downballot
presidential-by-district sheets and the label files (research/history/labels_<year>.json).

Same definitions as the 2026 pipeline (METHODOLOGY §2.2-2.3, O-6):
  m_house  = 100*(D-R)/(D+R)            (two-party, final round for RCV / runoffs)
  m_pres   = 100*(Dpres-Rpres)/(Dpres+Rpres) on the lines in use that year
  overperformance        = m_house - m_pres                      (margin scale)
  overperformance_logit50 = logit50(m_house) - logit50(m_pres)   (main scale, O-6)
Exclusions: uncontested / no major-party opponent; same-party general (top-two); any third candidate
(or second Democrat) >= 10% (first round for RCV races, so AK-2022's Begich counts); no baseline.

Usage: python -I build_races.py 2018 2022 [2020 2024]
"""
import csv
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HIST = ROOT / "research" / "history"
RAW = HIST / "raw"
SHEETS = RAW / "sheets"

SHEET_2016_LINES = "1VfkHtzBTP5gf4jAu8tcVQgsBJ1IDvXEHjuMqYlOgYbA"   # DKE: 2016/2012/2008 pres by CD, 2016 lines
SHEET_2020_LINES = "1XbUXnI9OyfAuhP5P3vWtMuGc5UJlrhXbzZo3AwMuHtk"   # DKE: 2020/2016/2012/2008 pres by CD, 2020 lines (= 2018 lines + NC 2020 map)
SHEET_2022_LINES = "1CKngqOp8fzU22JOlypoxNsxL6KSAH920Whc-rd7ebuM"   # Downballot: 2020 pres by CD, 2022 lines
SHEET_2024_LINES = "1ng1i_Dm_RMDnEvauH44pgE6JCUsapcuu8F2pCfeLWFo"   # Downballot: 2024 + 2020 pres by CD, 2024 lines (integers)
SHEET_URL = "https://docs.google.com/spreadsheets/d/{}/export?format=csv"
WIKI_URL = "https://en.wikipedia.org/wiki/{}_United_States_House_of_Representatives_elections"

NATIONAL_HOUSE_ENV = {  # national House popular-vote margin, D minus R, points (see README for sources)
    2018: 8.6, 2020: 3.1, 2022: -2.7, 2024: -2.6, 2026: 13.0,
}


def logit50(m):
    m = max(min(m, 99.0), -99.0)
    s = (1 + m / 100) / 2
    return 50.0 * math.log(s / (1 - s))


def two_party(d, r):
    return 100.0 * (d - r) / (d + r)


def read_sheet(sid):
    out = {}
    with open(SHEETS / f"{sid}.csv") as f:
        for row in csv.reader(f):
            if len(row[0]) >= 4 and row[0][2] == "-" and row[0][:2].isalpha():
                st, d = row[0].split("-")
                out[(st, 0 if d == "AL" else int(d))] = row
    return out


def pres_baseline(year):
    """(state, district) -> dict(dem, rep, year, source)"""
    res = {}
    if year == 2018:
        s16 = read_sheet(SHEET_2016_LINES)
        s20 = read_sheet(SHEET_2020_LINES)
        for k, row in s16.items():
            if k[0] == "PA":  # 2018 court-ordered map: take 2016 pres from the 2020-lines sheet (PA map unchanged 2018->2020)
                r2 = s20[k]
                res[k] = {"dem": float(r2[5]), "rep": float(r2[6]), "pres_year": 2016, "lines": "2018_PA_court_map",
                          "source": SHEET_URL.format(SHEET_2020_LINES)}
            else:
                res[k] = {"dem": float(row[3]), "rep": float(row[4]), "pres_year": 2016, "lines": "2016_2018_same",
                          "source": SHEET_URL.format(SHEET_2016_LINES)}
    elif year == 2020:
        for k, row in read_sheet(SHEET_2020_LINES).items():
            res[k] = {"dem": float(row[3]), "rep": float(row[4]), "pres_year": 2020, "lines": "2020",
                      "source": SHEET_URL.format(SHEET_2020_LINES)}
    elif year == 2022:
        for k, row in read_sheet(SHEET_2022_LINES).items():
            res[k] = {"dem": float(row[3]), "rep": float(row[4]), "pres_year": 2020, "lines": "2022",
                      "source": SHEET_URL.format(SHEET_2022_LINES)}
    elif year == 2024:
        for k, row in read_sheet(SHEET_2024_LINES).items():
            res[k] = {"dem": float(row[3]), "rep": float(row[4]), "pres_year": 2024, "lines": "2024",
                      "source": SHEET_URL.format(SHEET_2024_LINES), "rounded_to_integer": True}
    return res


def prev_lines_same(year):
    """Districts whose lines were unchanged from the previous House election, plus the previous
    election's same-line presidential baseline (for the incumbent personal-vote control, §2.6)."""
    if year == 2018:   # 2016 -> 2018: only PA changed
        s16 = read_sheet(SHEET_2016_LINES)
        return 2016, {k: (float(r[3]), float(r[4])) for k, r in s16.items() if k[0] != "PA"}
    if year == 2020:   # 2018 -> 2020: only NC changed; previous race 2018 vs 2016 pres (nearest prior pres, as in 01_build)
        s20 = read_sheet(SHEET_2020_LINES)
        return 2018, {k: (float(r[5]), float(r[6])) for k, r in s20.items() if k[0] != "NC"}
    if year == 2024:   # 2022 -> 2024: compare the 2020 pres columns of the two sheets to find unchanged lines
        s22 = read_sheet(SHEET_2022_LINES)
        s24 = read_sheet(SHEET_2024_LINES)
        out = {}
        for k, r in s24.items():
            if k in s22 and abs(round(float(s22[k][3])) - float(r[6])) <= 1 and abs(round(float(s22[k][4])) - float(r[7])) <= 1:
                out[k] = (float(s22[k][3]), float(s22[k][4]))
        return 2022, out
    return None, {}   # 2022: national redistricting


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"\(.*?\)|\"[^\"]*\"", " ", s)
    s = re.sub(r"\b(Jr|Sr|II|III|IV)\b\.?", " ", s)
    toks = [t for t in re.split(r"[\s,]+", s.lower()) if t]
    return toks


def same_person(a, b):
    ta, tb = norm(a), norm(b)
    if not ta or not tb:
        return False
    if ta[-1] != tb[-1]:
        return False
    fa, fb = ta[0], tb[0]
    return fa == fb or fa[:3] == fb[:3] or (len(ta) > 2 and ta[1][:3] == fb[:3]) or (len(tb) > 2 and tb[1][:3] == fa[:3])


def build(year):
    parsed = [x for x in json.loads((RAW / f"parsed_{year}.json").read_text()) if len(x["state"]) == 2 and x["state"] not in ("AS", "DC", "GU", "MP", "PR", "VI")]
    base = pres_baseline(year)
    prev_year, prev_base = prev_lines_same(year)
    prev = {}
    if prev_year:
        for x in json.loads((RAW / f"parsed_{prev_year}.json").read_text()):
            c = x["candidates_final"]
            d = max([q for q in c if q["p"] == "D"], key=lambda q: q["pct"], default=None)
            r = max([q for q in c if q["p"] == "R"], key=lambda q: q["pct"], default=None)
            prev[(x["state"], x["district"])] = (d, r, c)
    labels_path = HIST / f"labels_{year}.json"
    labels = json.loads(labels_path.read_text())["labels"] if labels_path.exists() else {}
    out = []
    for x in parsed:
        k = (x["state"], x["district"])
        rid = f"{x['state']}-{x['district'] if x['district'] else 'AL'}"
        final, first = x["candidates_final"], x["candidates_first_round"]
        ds = sorted([q for q in final if q["p"] == "D"], key=lambda q: -q["pct"])
        rs = sorted([q for q in final if q["p"] == "R"], key=lambda q: -q["pct"])
        d = ds[0] if ds else None
        r = rs[0] if rs else None
        rec = {"id": rid, "cycle": year, "office": "House", "state": x["state"], "district": x["district"] or "AL",
               "incumbents_listed": x["incumbents"], "status_note": (x["status"] or [""])[0][:200]}
        dem_inc = bool(d and any(same_person(d["name"], i) for i in x["incumbents"]))
        rep_inc = bool(r and any(same_person(r["name"], i) for i in x["incumbents"]))
        rec["open_seat"] = not (dem_inc or rep_inc)
        rec["dem"] = None if d is None else {"name": d["name"], "incumbent": dem_inc, "party_label": d["party"]}
        rec["rep"] = None if r is None else {"name": r["name"], "incumbent": rep_inc, "party_label": r["party"], "style": None}
        excl = None
        other_first = None
        if d is None or r is None:
            if d is None and r is None and not final:
                excl = "uncontested_or_no_major_party_opponent"
            elif (d is None and len(rs) >= 2) or (r is None and len(ds) >= 2):
                excl = "same_party_general"
            else:
                excl = "uncontested_or_no_major_party_opponent"
        else:
            dp, rp = d["pct"], r["pct"]
            other = round(100 - dp - rp, 2)
            # third-candidate rule uses the first round where there is one (RCV)
            if x["rcv_or_runoff"] and first:
                f_d = max([q["pct"] for q in first if q["p"] == "D"], default=0)
                f_r = max([q["pct"] for q in first if q["p"] == "R"], default=0)
                biggest_other = max([q["pct"] for q in first if q["pct"] not in (f_d, f_r)] or [0])
                other_first = round(100 - f_d - f_r, 2)
            else:
                biggest_other = max([q["pct"] for q in final if q is not d and q is not r] or [0])
            if len(ds) >= 2 and ds[1]["pct"] >= 10:
                excl = "split_dem_vote (second Democrat >= 10%)"
            elif biggest_other >= 10:
                excl = "third_candidate_ge_10pct"
            rec["result"] = {"dem_pct": dp, "rep_pct": rp, "other_pct": max(other, 0.0), "margin": round(dp - rp, 2),
                             "margin_2p": round(two_party(dp, rp), 3), "round": "final_rcv" if x["rcv_or_runoff"] else "general",
                             "other_pct_first_round": other_first, "biggest_other_pct": biggest_other,
                             "dem_won": d.get("won", False) or dp > rp}
        b = base.get(k)
        if b is None and excl is None:
            excl = "no_presidential_baseline"
        if b:
            rec["baseline"] = {"pres_year": b["pres_year"], "lines": b["lines"], "pres_dem_pct": b["dem"], "pres_rep_pct": b["rep"],
                               "pres_margin": round(b["dem"] - b["rep"], 2), "pres_margin_2p": round(two_party(b["dem"], b["rep"]), 3),
                               "source": b["source"]}
            if b.get("rounded_to_integer"):
                rec["baseline"]["rounded_to_integer"] = True
        # personal vote (§2.6, O-6): previous race on unchanged lines, contested; logit50 scale
        rec["D_inc_pv"] = 0.0
        rec["R_inc_pv"] = 0.0
        if prev_year and k in prev_base and k in prev and (dem_inc or rep_inc):
            pd_, pr_, _ = prev[k]
            pres_prev = two_party(*prev_base[k])
            if pd_ and pr_:
                pm = two_party(pd_["pct"], pr_["pct"])
                inc_name = d["name"] if dem_inc else r["name"]
                was_same = same_person(inc_name, pd_["name"] if dem_inc else pr_["name"])
                if abs(pm) < 95 and was_same:
                    pv = logit50(pm) - logit50(pres_prev)
                    rec["prev_race"] = {"year": prev_year, "margin_2p": round(pm, 3), "pres_margin_2p_same_lines": round(pres_prev, 3)}
                    if dem_inc:
                        rec["D_inc_pv"] = round(pv, 3)
                    else:
                        rec["R_inc_pv"] = round(pv, 3)
        if "result" in rec and b:
            m, mp = rec["result"]["margin_2p"], rec["baseline"]["pres_margin_2p"]
            rec["overperformance"] = round(m - mp, 3)
            rec["overperformance_logit50"] = round(logit50(m) - logit50(mp), 3)
        rec["exclusion_reason"] = excl
        rec["included"] = excl is None
        lab = labels.get(rid)
        if rec["dem"] is not None:
            if lab and same_person(lab.get("name", d["name"]), d["name"]):
                for f in ("ideology", "posture", "archetype", "style_confidence", "style_evidence", "label_source_url", "label_tier",
                          "verified_fetch", "coder", "markers", "rule_archetype"):
                    rec["dem"][f] = lab.get(f)
            else:
                rec["dem"].update({"ideology": "liberal", "posture": "establishment", "archetype": "mainstream_liberal",
                                   "style_confidence": "low", "label_tier": "default_unresearched",
                                   "style_evidence": "Default: not individually researched (safe seat, no left/moderate marker found in the caucus and endorsement lists checked).",
                                   "label_source_url": None})
                if lab:
                    rec["dem"]["label_name_mismatch"] = lab.get("name")
        rec["sources"] = [WIKI_URL.format(year)] + ([rec["baseline"]["source"]] if b else [])
        if rec["dem"] is not None and rec["dem"].get("label_source_url"):
            rec["sources"].append(rec["dem"]["label_source_url"])
        out.append(rec)
    out.sort(key=lambda r: (r["state"], 0 if r["district"] == "AL" else r["district"]))
    meta = {"cycle": year, "as_of": "2026-11-04", "national_house_env_D_minus_R": NATIONAL_HOUSE_ENV.get(year),
            "n_races": len(out), "n_included": sum(r["included"] for r in out),
            "definitions": __doc__.strip(),
            "result_source": WIKI_URL.format(year) + " (raw wikitext, action=raw; percentages rounded to 0.1 by Wikipedia)",
            "label_file": str(labels_path.relative_to(ROOT)) if labels_path.exists() else None}
    (HIST / f"house_{year}.json").write_text(json.dumps({"meta": meta, "races": out}, indent=1, ensure_ascii=False))
    from collections import Counter
    print(year, len(out), "included", meta["n_included"], Counter(r["exclusion_reason"] for r in out))
    return out


if __name__ == "__main__":
    for y in sys.argv[1:]:
        build(int(y))
