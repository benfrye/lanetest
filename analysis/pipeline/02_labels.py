"""Step 02: style label sets A/B/C, the source-date audit, label agreement (kappa), coordinates.

METHODOLOGY §2.5.
- Set A: agent labels from the race files. Audited for pre-election citations.
- Set B: rule-based endorsement coding + fixed posture lexicon applied to the label evidence text.
  The lexicon and thresholds below are fixed in code and never look at outcomes.
- Set C: soft probability vector built from style_confidence and Set B disagreement.
- Second coder: no blind 20% recode exists. The independent primaries research file
  (primaries.json) coded the same nominees separately, so it is used as a *proxy* second coder
  (not blind to results, not a random sample). This is recorded in label_sets_available.
Output: work/dataset_labeled.json, work/labels_report.json
"""
import re
from collections import Counter

from common import (ARCHETYPES, ELECTION_DAY, L_MAP, P_MAP, RESEARCH, WORK, Log, cohen_kappa,
                    load_json, save_json)

log = Log("02_labels")
rows = load_json(WORK / "dataset.json")

# ------------------------------------------------------------------ Set B rule lexicon (fixed)
LEFT_PAT = [r"Justice Democrats", r"Progressive Caucus", r"\bCPC\b", r"\bSanders\b", r"\bBernie\b",
            r"Our Revolution", r"Working Families", r"\bWFP\b"]
MOD_PAT = [r"Blue Dog", r"New Democrat"]
POP_PAT = [r"populis", r"billionaire", r"anti-corporate", r"corporate PAC", r"corporate money", r"rigged",
           r"working[- ]class", r"Wall Street", r"oligarch", r"anti-establishment", r"insurgent",
           r"cost[- ]of[- ]living", r"affordability"]
INST_PAT = [r"\bDCCC\b", r"Red to Blue", r"Problem Solvers", r"leadership", r"establishment-backed",
            r"bipartisan", r"\bDSCC\b", r"\bDGA\b", r"Jeffries", r"Pelosi", r"Schumer"]
NEG = re.compile(r"\b(not|no|without|declined|refused|lost)\b[^.;]{0,30}$", re.I)
POP_THRESH = 2   # >= 2 populist hits and net >= 1 -> populist; >= 1 hit and net >= 0 -> mixed


def hits(text, pats):
    n = 0
    found = []
    for p in pats:
        for m in re.finditer(p, text, re.I):
            pre = text[max(0, m.start() - 40):m.start()]
            if NEG.search(pre):
                continue
            n += 1
            found.append(m.group(0))
            break
    return n, found


def set_b(text):
    nl, fl = hits(text, LEFT_PAT)
    nm, fm = hits(text, MOD_PAT)
    np_, fp = hits(text, POP_PAT)
    ni, fi = hits(text, INST_PAT)
    ideology = "left" if nl else ("moderate" if nm else "liberal")
    net = np_ - ni
    posture = "populist" if (np_ >= POP_THRESH and net >= 1) else ("mixed" if (np_ >= 1 and net >= 0) else "establishment")
    if ideology == "left":
        arch = "left_populist" if posture == "populist" else "progressive"
    elif ideology == "moderate":
        arch = "center_populist" if posture == "populist" else "moderate"
    else:
        arch = "left_populist" if posture == "populist" else "mainstream_liberal"
    fired = bool(nl or nm or np_ or ni)
    return {"ideology": ideology, "posture": posture, "archetype": arch, "rule_fired": fired,
            "hits": {"left": fl, "moderate": fm, "populist": fp, "institutional": fi}}


# ------------------------------------------------------------------ primaries.json proxy second coder
prim = load_json(RESEARCH / "primaries.json")


def race_id_from_general(g):
    if not g:
        return None
    if g.startswith("HOUSE-"):
        st, dist = g[6:].split("-")[:2]
        try:
            return f"{st}-{int(dist)}"
        except ValueError:
            return f"{st}-{dist}"
    if g.startswith("SEN-FL"):
        return "SEN-FL-special"
    return g


def lastname(n):
    n = re.sub(r"\(.*?\)|\"[^\"]*\"", "", n or "").strip()
    return n.split()[-1].lower() if n.split() else ""


prim_by_race = {}
for c in prim["contests"]:
    rid = race_id_from_general(c.get("race_id_general"))
    if not rid or (c.get("date") or "9999") >= ELECTION_DAY:
        continue
    for cand in c.get("candidates") or []:
        if cand.get("won"):
            prim_by_race.setdefault(rid, []).append((c, cand))

DATE_PAT = re.compile(r"(20\d\d)[/-](\d\d)(?:[/-](\d\d))?")
ENDORSE_PAT = re.compile(r"endors|caucus|coalition|\bPAC\b|backed by|member|DSA|EMILY|AFL-CIO|union", re.I)

conf_num = {"high": 0.85, "medium": 0.6, "low": 0.35}
for r in rows:
    text = " ".join([r.get("style_evidence") or "", r.get("dem_background") or ""])
    matches = [(c, cand) for c, cand in prim_by_race.get(r["id"], []) if lastname(cand.get("name")) == lastname(r["dem_name"])]
    if matches:
        _, cand = matches[0]
        text += " " + " ".join(cand.get("key_endorsements") or []) + " " + (cand.get("style_evidence") or "")
    b = set_b(text)
    r["B_ideology"], r["B_posture"], r["B_archetype"] = b["ideology"], b["posture"], b["archetype"]
    r["B_rule_fired"] = b["rule_fired"]
    r["B_hits"] = b["hits"]
    # source-date audit (§2.5): the pipeline audits; it does not assert coded_at
    dated_pre = []
    for u in r.get("sources") or []:
        m = DATE_PAT.search(u)
        if m:
            d = f"{m.group(1)}-{m.group(2)}-{m.group(3) or '01'}"
            if d < ELECTION_DAY:
                dated_pre.append(u)
    if dated_pre:
        tier = "dated_pre_election_source"
    elif matches:
        tier = "primary_record"
    elif r["office"] in ("Special", "Validation2025") and r.get("date", "9999") < ELECTION_DAY:
        tier = "pre_election_contest"
    elif ENDORSE_PAT.search(r.get("style_evidence") or ""):
        tier = "endorsement_cited_undated"
    else:
        tier = "post_hoc"
    r["label_audit"] = tier
    r["second_coder"] = None
    if matches:
        _, cand = matches[0]
        r["second_coder"] = {"archetype": cand.get("archetype"), "ideology": cand.get("ideology"),
                             "posture": cand.get("posture"), "source": "primaries.json"}
    # main-fit labels: Set A where pre-election citation exists, else Set B
    if tier == "post_hoc" or r["archetype"] not in ARCHETYPES:
        r["label_source"] = "B"
        r["M_ideology"], r["M_posture"], r["M_archetype"] = r["B_ideology"], r["B_posture"], r["B_archetype"]
    else:
        r["label_source"] = "A"
        r["M_ideology"], r["M_posture"], r["M_archetype"] = r["ideology"], r["posture"], r["archetype"]
    r["strict_label_source"] = "A" if tier in ("dated_pre_election_source", "primary_record", "pre_election_contest") else "B"
    r["conf"] = conf_num.get(r.get("style_confidence"), 0.35)
    for tag, ideo, post in (("M", r["M_ideology"], r["M_posture"]), ("A", r["ideology"], r["posture"]),
                            ("B", r["B_ideology"], r["B_posture"])):
        r[f"L_{tag}"] = L_MAP.get(ideo)
        r[f"P_{tag}"] = P_MAP.get(post)
    # Strict-audit label set (robustness)
    if r["strict_label_source"] == "A" and r["archetype"] in ARCHETYPES:
        r["S_archetype"], r["L_S"], r["P_S"] = r["archetype"], r["L_A"], r["P_A"]
    else:
        r["S_archetype"], r["L_S"], r["P_S"] = r["B_archetype"], r["L_B"], r["P_B"]

# Set C (soft): probability vector over archetypes
for r in rows:
    main = r["M_archetype"]
    vec = {a: 0.0 for a in ARCHETYPES}
    if main not in ARCHETYPES:
        r["C_probs"] = None
        continue
    pm = r["conf"] if r["label_source"] == "A" else 0.5
    vec[main] = pm
    rest = 1 - pm
    alt = r["B_archetype"] if r["label_source"] == "A" else r["archetype"]
    others = [a for a in ARCHETYPES if a != main]
    if alt in others:
        vec[alt] += 0.6 * rest
        for a in others:
            vec[a] += 0.4 * rest / len(others)
    else:
        for a in others:
            vec[a] += rest / len(others)
    r["C_probs"] = vec

# ------------------------------------------------------------------ agreement statistics
lab = [r for r in rows if r["archetype"] in ARCHETYPES and r["office"] != "Validation2025"]
main_lab = [r for r in lab if r["in_main"]]


def kap(rs, fa, fb):
    pairs = [(fa(r), fb(r)) for r in rs if fa(r) is not None and fb(r) is not None]
    if not pairs:
        return {"kappa": None, "n": 0, "agree": None}
    a, b = zip(*pairs)
    return {"kappa": cohen_kappa(a, b), "n": len(pairs), "agree": sum(x == y for x, y in pairs) / len(pairs)}


sc = [r for r in lab if r["second_coder"]]
report = {
    "label_sets_available": {
        "A_agent": True,
        "B_rule_based": "implemented from label evidence text (style_evidence/background, plus primaries.json key_endorsements where matched); not from raw pre-election campaign text, which is not on disk",
        "C_soft": "constructed from style_confidence and A/B disagreement (no independent probability coding exists)",
        "second_coder_blind_20pct": False,
        "second_coder_proxy": "primaries.json nominee labels (independent research pass; not blind to results; not a random sample)",
    },
    "audit_counts_all": dict(Counter(r["label_audit"] for r in lab)),
    "audit_counts_main": dict(Counter(r["label_audit"] for r in main_lab)),
    "label_source_main": dict(Counter(r["label_source"] for r in main_lab)),
    "strict_label_source_main": dict(Counter(r["strict_label_source"] for r in main_lab)),
    "B_rule_fired_share_main": sum(r["B_rule_fired"] for r in main_lab) / max(1, len(main_lab)),
    "kappa_agent_vs_rules": {k: kap(lab, lambda r, k=k: r[k], lambda r, k=k: r["B_" + k]) for k in ("archetype", "ideology", "posture")},
    "kappa_agent_vs_rules_main": {k: kap(main_lab, lambda r, k=k: r[k], lambda r, k=k: r["B_" + k]) for k in ("archetype", "ideology", "posture")},
    "kappa_agent_vs_second_coder_proxy": {k: kap(sc, lambda r, k=k: r[k], lambda r, k=k: r["second_coder"][k]) for k in ("archetype", "ideology", "posture")},
    "second_coder_disagreements": [{"id": r["id"], "name": r["dem_name"], "agent": r["archetype"], "proxy": r["second_coder"]["archetype"]}
                                   for r in sc if r["archetype"] != r["second_coder"]["archetype"]],
    "lexicon": {"left": LEFT_PAT, "moderate": MOD_PAT, "populist": POP_PAT, "institutional": INST_PAT, "populist_threshold": POP_THRESH},
    "n_main_labeled": len(main_lab),
}
for k, v in report.items():
    log(k, v)

save_json(WORK / "dataset_labeled.json", rows, nd=None)
save_json(WORK / "labels_report.json", report, nd=None, indent=1)
log.save()
