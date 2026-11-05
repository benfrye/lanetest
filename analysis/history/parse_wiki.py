"""Parse the per-state result tables of the Wikipedia "<year> United States House of Representatives
elections" pages (raw wikitext saved under research/history/raw/) into one record per district.

Output: research/history/raw/parsed_<year>.json  (list of dicts; no labels, no baselines yet)

For each district block we keep every candidate line (name, party, pct). If the block has a runoff /
instant-runoff section, the final-round lines are used for the two-party result (METHODOLOGY §2.2:
RCV races use the final round) and the first round is kept for reference.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "research" / "history" / "raw"

STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
    "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}

ROW_HDR = re.compile(r"^!\s*(?:[^{|]*\|\s*)?\{\{ushr\|\s*([A-Za-z ]+?)\s*\|\s*([A-Za-z0-9]+)\s*\|", re.I)
CAND = re.compile(r"^\*\s*(?:\{\{Party stripe\|[^}]*\}\})?\s*(.*?)\s*\(([^()]*?)\)\s*([\d.]+)\s*%")
RUNOFF = re.compile(r"(instant runoff|runoff|second round|final round)", re.I)


def clean_name(s):
    s = re.sub(r"\{\{Aye\}\}|\{\{Nay\}\}|'''|''", "", s)
    # {{sortname|First|Last|Link}} -> First Last
    s = re.sub(r"\{\{\s*[Ss]ortname\|([^|}]*)\|([^|}]*)(?:\|[^}]*)?\}\}", r"\1 \2", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", s)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip(" *")


def party_code(p):
    pl = p.lower()
    if pl.startswith("democrat") or "democratic" in pl or pl.startswith("dfl"):
        return "D"
    if pl.startswith("republican") or pl == "gop":
        return "R"
    return "O"


def parse(year):
    txt = (RAW / f"wiki_{year}_house.txt").read_text()
    lines = txt.split("\n")
    # restrict to per-state sections
    state = None
    blocks = []
    cur = None
    for ln in lines:
        m = re.match(r"^==\s*([A-Za-z ]+?)\s*==\s*$", ln)
        if m:
            nm = m.group(1).strip()
            if cur:
                blocks.append(cur)
                cur = None
            state = STATES.get(nm)
            continue
        if state is None:
            continue
        h = ROW_HDR.match(ln)
        if h:
            if cur:
                blocks.append(cur)
            st, d = h.group(1).strip(), h.group(2)
            st = STATES.get(st, st.upper())
            cur = {"state": st, "district": 0 if d.upper() in ("AL",) else int(d), "lines": [ln], "sec_state": state}
            continue
        if cur is not None:
            if ln.startswith("|}"):
                blocks.append(cur)
                cur = None
            else:
                cur["lines"].append(ln)
    if cur:
        blocks.append(cur)

    out = []
    for b in blocks:
        body = b["lines"]
        cands_all = []
        segment = 0
        for ln in body:
            s = ln.strip()
            if s.startswith("*") and RUNOFF.search(s) and "%" not in s:
                segment += 1
                continue
            m = CAND.match(s)
            if m and "%" in s:
                name = clean_name(m.group(1))
                party = clean_name(m.group(2).replace("[[", "[[").strip())
                cands_all.append({"name": name, "party": party, "p": party_code(party), "pct": float(m.group(3)),
                                  "won": "{{Aye}}" in s, "round": segment})
        unopposed = any("unopposed" in ln.lower() for ln in body)
        # incumbents: names on lines starting with "| [[" or "| {{sortname" before the candidate list
        incs = []
        inc_parties = []
        status = []
        for ln in body[1:]:
            s = ln.strip()
            if s.startswith("* ") or s.startswith("*{{"):
                continue
            if re.match(r"^\|\s*(\[\[|\{\{\s*[Ss]ortname)", s):
                nm = clean_name(s[1:]).replace("}}", "").strip()
                if not re.match(r"^[\d\s]+$", nm):
                    incs.append(nm)
            pm = re.search(r"Party shading/(?:Text/)?([A-Za-z\-– ]+?)(?:/Text)?\}\}", s)
            if pm:
                inc_parties.append(party_code(pm.group(1)))
            if re.search(r"(Incumbent|New seat|New member|elected|retired|lost|defeated|Democratic gain|Republican gain|hold)", s) and not s.startswith("| nowrap"):
                status.append(clean_name(s.lstrip("|")))
        final_round = max([c["round"] for c in cands_all], default=0)
        final = [c for c in cands_all if c["round"] == final_round]
        first = [c for c in cands_all if c["round"] == 0]
        out.append({"state": b["state"], "district": b["district"], "incumbents": incs, "incumbent_parties": inc_parties,
                    "status": status, "candidates_first_round": first, "candidates_final": final,
                    "rcv_or_runoff": final_round > 0, "unopposed_marker": unopposed})
    return out


if __name__ == "__main__":
    for y in sys.argv[1:]:
        rows = parse(y)
        (RAW / f"parsed_{y}.json").write_text(json.dumps(rows, indent=1))
        print(y, len(rows))
