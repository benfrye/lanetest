"""Step 01: build the race-level dataset with outcomes, baselines, controls and inclusion flags.

Implements METHODOLOGY §2.2 (margins), §2.3 (inclusion), §2.4 (partial-count tiers), §2.6 (controls).
Every exclusion is logged with a reason in work/exclusions.json.
Output: work/dataset.json (list of row dicts).
"""
import glob
import re

from common import (COMPETITIVE_WINDOW, MAIN_OUTCOME, logit50, RESEARCH, WORK, Log, fnum, jmodel, load_json, save_json, state_code, two_party, ymodel)

log = Log("01_build_dataset")

states = {r["id"]: r for r in load_json(RESEARCH / "states.json")["rows"]}
# 2020->2024 presidential swing on current lines (the "Harris bounce-back" control, O-9). District
# baselines come from the history files (Downballot sheets): 2020 pres on 2022 lines and 2024 pres
# on 2024 lines; used only where lines are unchanged 2022->2026, else the state's swing.
_H = {}
for _y in (2022, 2024):
    _f = RESEARCH / "history" / f"house_{_y}.json"
    if _f.exists():
        for _r in load_json(_f)["races"]:
            _b = (_r.get("baseline") or {}).get("pres_margin")
            if _b is not None:
                _H[(_y, _r["state"], str(_r["district"]))] = float(_b)
REDRAWN_2024 = {"AL", "GA", "LA", "NY", "NC"}


def swing2024_for(row):
    st = row["state"]
    r = states.get(st) or {}
    p24 = (r.get("pres2024") or {}).get("margin")
    p20 = r.get("pres2020_margin")
    state_sw = (p24 - p20) if (p24 is not None and p20 is not None) else 0.0
    if row["office"] in ("House", "Special") and row.get("lines") == "2024_same" and st not in REDRAWN_2024:
        d = str(row.get("district"))
        b20, b24 = _H.get((2022, st, d)), _H.get((2024, st, d))
        if b20 is not None and b24 is not None:
            return (b24 - b20) / 10.0, "district"
    return state_sw / 10.0, "state"


def state_other_share(st):
    r = states.get(st)
    if not r or not isinstance(r.get("pres2024"), dict):
        return None
    d, p = fnum(r["pres2024"].get("dem_pct")), fnum(r["pres2024"].get("rep_pct"))
    if d is None or p is None:
        return None
    return 1 - (d + p) / 100.0


def state_m24_2p(st):
    r = states.get(st)
    if not r:
        return None
    p = r["pres2024"]
    return two_party(p.get("dem_votes"), p.get("rep_votes"))


def total_to_2p(margin, st):
    m = fnum(margin)
    if m is None:
        return None
    o = state_other_share(st)
    if o is None:
        o = 0.0
    return m / (1 - o)


# Incumbents who won their seat in a 2025-26 special: the 2024 race was a different person.
offyear = load_json(RESEARCH / "offyear.json")
special_winner_seats = set()
for e in offyear["elections"]:
    if e["office"].startswith("US House special"):
        seat = e["jurisdiction"].split(" ")[0]
        special_winner_seats.add(seat)
log("seats won in 2025-26 specials (no personal vote from the 2024 race):", sorted(special_winner_seats))

ELECTED_OFFICE_FLAGS = {"state_senator", "former_state_senator", "statewide_officeholder"}
RESULT_SOURCE_PAT = re.compile(r"nbcnews|apnews|cnn\.com|nytimes|decisiondesk|sos\.|\.gov|elections\.|cbsnews|abcnews|politico", re.I)

USER_FLAGGED_UNCALLED = ["SEN-AK", "SEN-MS", "GOV-KS", "GOV-AK", "ME-2", "TN-4", "TN-9", "VA-5", "NC-3", "NC-5", "NC-7"]


def pres_for_year(st, year, row_pres24_total):
    """Same-geography presidential margin (total-vote) for the cycle of a previous race."""
    r = states.get(st)
    if year is None:
        return None
    y = int(year)
    if y >= 2024:
        return row_pres24_total
    if r is None:
        return None
    # 2020, and 2022 midterm -> nearest prior presidential (2020). Documented approximation.
    if y in (2020, 2021, 2022, 2023):
        return fnum(r.get("pres2020_margin"))
    if y in (2016, 2017, 2018, 2019):
        return fnum(r.get("pres2016_margin"))
    return None


def build_row(r, src):
    office = r.get("office")
    st = r.get("state")
    dem = r.get("dem") or {}
    rep = r.get("rep") or {}
    res = r.get("result") or {}
    base = r.get("baseline") or {}
    notes = r.get("notes") or ""
    row = {
        "id": r.get("id"), "office": office, "state": st, "district": r.get("district"),
        "source_file": src, "period": "nov2026", "tier": r.get("tier"),
        "open_seat": bool(r.get("open_seat")), "incumbent_party": r.get("incumbent_party"),
        "dem_name": dem.get("name"), "dem_party_label": dem.get("party_label"),
        "ideology": dem.get("ideology"), "posture": dem.get("posture"), "archetype": dem.get("archetype"),
        "style_confidence": dem.get("style_confidence"), "style_evidence": dem.get("style_evidence") or "",
        "dem_background": dem.get("background") or "", "dem_incumbent": bool(dem.get("incumbent")),
        "rep_name": rep.get("name"), "rep_style_raw": rep.get("style"), "rep_incumbent": bool(rep.get("incumbent")),
        "rep_quality_flags": rep.get("quality_flags") or [],
        "alt_dem": r.get("alt_dem"),
        "dem_pct": fnum(res.get("dem_pct")), "rep_pct": fnum(res.get("rep_pct")), "other_pct": fnum(res.get("other_pct")),
        "margin_total": fnum(res.get("margin")), "pct_counted": fnum(res.get("pct_expected_vote_counted")),
        "called": res.get("called"), "called_by": res.get("called_by"), "flipped": res.get("flipped"),
        "pres24_total": fnum(base.get("pres2024_margin")), "lines": base.get("lines"),
        "house24_total": fnum(base.get("house2024_margin")), "prev_seat_margin": fnum(base.get("prev_seat_margin")),
        "prev_seat_year": base.get("prev_seat_year"),
        "overperf_reported": fnum(r.get("overperformance_vs_pres2024")),
        "uncontested": bool(r.get("uncontested")), "same_party_general": bool(r.get("same_party_general")),
        "sources": r.get("sources") or [], "notes": notes, "verified": r.get("verified"),
        "data_flags": [],
    }
    return row


rows = []
files = sorted(glob.glob(str(RESEARCH / "house" / "*.json"))) + [str(RESEARCH / "senate.json"), str(RESEARCH / "governors.json")]
for f in files:
    d = load_json(f)
    races = d.get("races") or []
    exp = d.get("expected_rows")
    log(f"{f.split('research/')[-1]}: {len(races)} races (expected_rows={exp})")
    for r in races:
        rows.append(build_row(r, f.split("research/")[-1]))
n_house = sum(1 for r in rows if r["office"] == "House")
log(f"House rows: {n_house} (expect 435); Senate {sum(r['office']=='Senate' for r in rows)}; Gov {sum(r['office']=='Governor' for r in rows)}")
ids = [r["id"] for r in rows]
dups = {i for i in ids if ids.count(i) > 1}
if dups:
    log("WARNING duplicate ids:", dups)

# --- specials and 2025 validation races from offyear.json
for e in offyear["elections"]:
    off = e["office"]
    date = e["date"]
    if off.startswith("US House special"):
        seat = e["jurisdiction"].split(" ")[0]
        st = seat.split("-")[0]
        y, mth = int(date[:4]), int(date[5:7])
        period = f"special_{y}H{1 if mth <= 6 else 2}"
        row = {
            "id": f"SPECIAL-{seat}-{date[:7]}", "office": "Special", "state": st, "district": seat.split("-")[1],
            "source_file": "offyear.json", "period": period, "tier": None, "open_seat": True, "incumbent_party": None,
            "dem_name": e.get("dem_candidate"), "dem_party_label": "D", "ideology": e.get("ideology"),
            "posture": e.get("posture"), "archetype": e.get("archetype"), "style_confidence": e.get("style_confidence"),
            "style_evidence": e.get("style_evidence") or "", "dem_background": "", "dem_incumbent": False,
            "rep_name": e.get("rep_candidate"), "rep_style_raw": e.get("rep_style"), "rep_incumbent": False,
            "rep_quality_flags": e.get("rep_quality_flags") or [], "alt_dem": None,
            "dem_pct": fnum(e.get("dem_pct")), "rep_pct": fnum(e.get("rep_pct")), "other_pct": None,
            "margin_total": fnum(e.get("margin")), "pct_counted": 100.0, "called": "final", "called_by": None,
            "flipped": None, "pres24_total": fnum(e.get("pres2024_margin")), "lines": "special_lines",
            "house24_total": None, "prev_seat_margin": None, "prev_seat_year": None,
            "overperf_reported": fnum(e.get("overperformance_vs_pres2024")), "uncontested": False,
            "same_party_general": e.get("rep_pct") is None, "sources": e.get("sources") or [],
            "notes": e.get("notes") or "", "verified": e.get("verified"), "data_flags": [], "date": date,
        }
        if "combined" in (e.get("dem_candidate") or "").lower():
            row["data_flags"].append("combined_multi_dem_vote")
        rows.append(row)
    elif e["id"] in ("va_gov_2025", "nj_gov_2025", "nyc_mayor_2025"):
        st = {"va_gov_2025": "VA", "nj_gov_2025": "NJ", "nyc_mayor_2025": "NY"}[e["id"]]
        rows.append({
            "id": e["id"].upper(), "office": "Validation2025", "state": st, "district": None,
            "source_file": "offyear.json", "period": "validation_2025", "tier": None, "open_seat": True,
            "incumbent_party": None, "dem_name": e.get("dem_candidate"), "dem_party_label": "D",
            "ideology": e.get("ideology"), "posture": e.get("posture"), "archetype": e.get("archetype"),
            "style_confidence": e.get("style_confidence"), "style_evidence": e.get("style_evidence") or "",
            "dem_background": "", "dem_incumbent": False, "rep_name": e.get("rep_candidate"),
            "rep_style_raw": e.get("rep_style"), "rep_incumbent": False, "rep_quality_flags": [], "alt_dem": None,
            "dem_pct": fnum(e.get("dem_pct")), "rep_pct": fnum(e.get("rep_pct")), "other_pct": None,
            "margin_total": fnum(e.get("margin")), "pct_counted": 100.0, "called": "final", "called_by": None,
            "flipped": None, "pres24_total": fnum(e.get("pres2024_margin")), "lines": "2024_same",
            "house24_total": None, "prev_seat_margin": None, "prev_seat_year": None,
            "overperf_reported": fnum(e.get("overperformance_vs_pres2024")), "uncontested": False,
            "same_party_general": False, "sources": e.get("sources") or [], "notes": e.get("notes") or "",
            "verified": e.get("verified"), "data_flags": [], "date": date,
        })

# --- derived quantities
for row in rows:
    st = row["state"]
    flags = row["data_flags"]
    row["statewide"] = row["office"] in ("Senate", "Governor")
    # 2026 two-party margin
    row["m26"] = two_party(row["dem_pct"], row["rep_pct"])
    # 2024 pres two-party
    if row["statewide"] and st in states and row["source_file"] != "offyear.json":
        row["m24"] = state_m24_2p(st)
        if row["pres24_total"] is not None and row["m24"] is not None:
            # consistency check vs the row's total-vote margin
            chk = total_to_2p(row["pres24_total"], st)
            if abs(chk - row["m24"]) > 0.6:
                flags.append("pres24_row_vs_states_json_mismatch")
    else:
        row["m24"] = total_to_2p(row["pres24_total"], st)
    row["house24"] = total_to_2p(row["house24_total"], st) if row.get("lines") == "2024_same" else None
    row["y"] = (row["m26"] - row["m24"]) if (row["m26"] is not None and row["m24"] is not None) else None
    row["swing2024"], row["swing2024_src"] = swing2024_for(row)
    row["y_model"] = ymodel(row)
    row["J"] = jmodel(row) if row["m26"] is not None else 1.0
    row["p"] = None if row["pct_counted"] is None else row["pct_counted"] / 100.0
    if row["p"] is not None and row["p"] > 1.0:
        row["p"] = 1.0
    # partial-count tier (§2.4)
    p = row["p"]
    row["count_tier"] = None if p is None else ("final" if p >= 0.95 else ("latent" if p >= 0.80 else "provisional"))
    row["sd_count"] = 0.0 if (p is None or p >= 0.95) else 25.0 * (1 - p)
    row["late_shift_prior_mean"] = 1.0 if st in ("CA", "WA", "OR") else 0.0

    # Opponent coding
    rs = row["rep_style_raw"]
    if rs not in ("maga", "traditional", "moderate"):
        flags.append(f"rep_style_{rs or 'missing'}_treated_as_traditional")
    row["rep_style"] = rs if rs in ("maga", "traditional", "moderate") else "traditional"
    row["rep_maga"] = 1.0 if rs == "maga" else 0.0
    row["rep_moderate"] = 1.0 if rs == "moderate" else 0.0
    qf = set(row["rep_quality_flags"])
    row["rep_quality"] = float(len(qf & ELECTED_OFFICE_FLAGS))
    row["rep_scandal"] = 1.0 if "scandal" in qf else 0.0

    # Incumbency + personal vote (§2.6)
    row["inc_D"] = 1.0 if row["dem_incumbent"] else 0.0
    row["inc_R"] = 1.0 if (row["rep_incumbent"] and not row["dem_incumbent"]) else 0.0
    row["R_inc_pv"] = 0.0
    row["D_inc_pv"] = 0.0
    seat = row["id"] if row["office"] == "House" else None
    pv_ok = row["prev_seat_margin"] is not None
    appointed = bool(re.search(r"appoint", row["notes"], re.I)) or "appointee" in qf
    if row["office"] == "House":
        pv_ok = pv_ok and row["lines"] == "2024_same" and str(row["prev_seat_year"]) == "2024" and seat not in special_winner_seats
    elif row["statewide"]:
        pv_ok = pv_ok and not appointed
    else:
        pv_ok = False
    if pv_ok and abs(row["prev_seat_margin"]) >= 95:
        # §2.3: prior-race baselines only where the prior race was contested
        pv_ok = False
        if row["inc_R"] or row["inc_D"]:
            flags.append("prior_race_uncontested_no_personal_vote")
    if pv_ok and (row["inc_R"] or row["inc_D"]):
        pres_prev = pres_for_year(st, row["prev_seat_year"], row["pres24_total"])
        if pres_prev is not None:
            pv = row["prev_seat_margin"] - pres_prev
            row["pv_margin"] = pv
            if MAIN_OUTCOME == "logit50":  # O-6: personal vote on the same scale as the outcome
                pv = logit50(row["prev_seat_margin"]) - logit50(pres_prev)
            if row["inc_R"]:
                row["R_inc_pv"] = pv
            else:
                row["D_inc_pv"] = pv
            if row["statewide"] and str(row["prev_seat_year"]) in ("2022", "2018"):
                flags.append("pv_midterm_prev_race_vs_prior_pres_baseline")
    elif (row["inc_R"] or row["inc_D"]) and row["statewide"] and appointed:
        flags.append("incumbent_appointed_no_personal_vote")

    # Data-quality flags
    res_src = [u for u in row["sources"] if RESULT_SOURCE_PAT.search(u)]
    if res_src and all("nbcnews" in u for u in res_src):
        flags.append("single_source_nbc")
    if row["called"] in ("D", "R") and not row["called_by"]:
        flags.append("call_inferred_no_caller")
    if row["called"] is None and row["office"] in ("House", "Senate", "Governor"):
        flags.append("uncalled")
    if st in ("CA", "WA", "OR", "AZ", "NV", "UT", "AK", "CO", "HI") and p is not None and p < 0.95:
        flags.append("western_incomplete_count")

# --- inclusion rules (§2.3)
exclusions = []


def exclude(row, reason):
    row["exclusion_reason"] = reason
    exclusions.append({"id": row["id"], "office": row["office"], "archetype": row["archetype"], "reason": reason})


for row in rows:
    row["exclusion_reason"] = None
    row["independent_backed"] = (row["dem_party_label"] or "D") != "D"
    alt = row.get("alt_dem") or {}
    alt_pct = fnum(alt.get("pct")) if isinstance(alt, dict) else None
    if row["office"] == "Validation2025":
        exclude(row, "validation_only_2025_offyear (§2.3)")
    elif not row["dem_name"] or row["archetype"] is None and row["dem_pct"] is None:
        exclude(row, "no_democrat_on_ballot")
    elif row["uncontested"] or row["rep_pct"] is None or not row["rep_name"]:
        exclude(row, "uncontested_or_no_major_party_opponent")
    elif row["same_party_general"]:
        exclude(row, "same_party_general")
    elif row["independent_backed"]:
        exclude(row, "independent_backed (Dem-backed independent; descriptive only)")
    elif "combined_multi_dem_vote" in row["data_flags"]:
        exclude(row, "combined_multi_dem_vote (all-party special, two Democrats summed)")
    elif alt_pct is not None and alt_pct >= 10:
        exclude(row, "split_dem_vote (second Democrat >= 10%)")
    elif row["other_pct"] is not None and row["other_pct"] >= 10:
        exclude(row, "third_candidate_ge_10pct (aggregate other_pct >= 10)")
    elif row["m24"] is None:
        exclude(row, "no_pres2024_on_current_lines")
    elif row["m26"] is None:
        exclude(row, "no_vote_share")
    elif row["p"] is None:
        exclude(row, "pct_counted_missing")
    elif row["archetype"] not in ("progressive", "left_populist", "center_populist", "mainstream_liberal", "moderate"):
        exclude(row, f"archetype_missing_or_unknown ({row['archetype']})")

    contested_ok = row["exclusion_reason"] is None
    m24 = row["m24"]
    row["in_full"] = contested_ok
    row["in_provisional"] = contested_ok and row["p"] >= 0.5
    row["in_extended"] = contested_ok and row["p"] >= 0.80 and (row["statewide"] or row["office"] == "Special" or abs(m24) <= 30)
    # O-6 (user decision 2026-11-04): no House lean window in the main sample; competitive-only is robustness R4
    row["competitive"] = contested_ok and (row["statewide"] or row["office"] == "Special" or abs(m24) <= COMPETITIVE_WINDOW)
    if contested_ok and row["p"] < 0.80:
        exclude(row, "partial_count_lt_80pct (provisional refit only)")
    row["in_main"] = row["exclusion_reason"] is None

# --- reports
from collections import Counter

cnt = Counter((e["reason"].split(" (")[0]) for e in exclusions)
log("exclusion counts:", dict(cnt))
main = [r for r in rows if r["in_main"]]
log(f"main sample: {len(main)} rows; by office {dict(Counter(r['office'] for r in main))}")
log(f"main by archetype: {dict(Counter(r['archetype'] for r in main))}")
no_pres = Counter(r["archetype"] for r in rows if r["exclusion_reason"] == "no_pres2024_on_current_lines")
log("rows lacking pres2024 on current lines by archetype (§2.3 report):", dict(no_pres))
row_by_id = {r["id"]: r for r in rows}
uncalled_check = []
for rid in USER_FLAGGED_UNCALLED:
    r = row_by_id.get(rid)
    if r is None:
        uncalled_check.append({"id": rid, "status": "not_found_in_data"})
    else:
        uncalled_check.append({"id": rid, "called_in_data": r["called"], "pct_counted": r["pct_counted"],
                               "in_main": r["in_main"], "exclusion_reason": r["exclusion_reason"]})
    log("user-flagged uncalled:", uncalled_check[-1])
all_uncalled = [r["id"] for r in rows if "uncalled" in r["data_flags"]]
log(f"uncalled in data: {len(all_uncalled)}")
flag_counts = Counter(f for r in rows for f in r["data_flags"])
log("data flag counts:", dict(flag_counts))

save_json(WORK / "dataset.json", rows, nd=None)
save_json(WORK / "exclusions.json", {"exclusions": exclusions, "counts": dict(cnt),
                                      "no_pres2024_by_archetype": dict(no_pres),
                                      "user_flagged_uncalled": uncalled_check,
                                      "uncalled_ids": all_uncalled, "data_flag_counts": dict(flag_counts)}, nd=None, indent=1)
log.save()
