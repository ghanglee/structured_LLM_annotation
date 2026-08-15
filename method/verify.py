"""Deterministic composition, verification and constraint propagation over a declared rule set.

No model is called and no network access is used. Everything here is executed exactly as the
rule file states it.

Three operations, in the order the method applies them:

  compose(rules, elicited)    derive coarser granularities from finer ones by the declared
                              conjunctions. The derived value replaces nothing; it is returned
                              alongside so it can be compared.

  propagate(rules, elicited)  where a mapping's inverse image is a singleton, the coarse value
                              ENTAILS the finer label, so the finer label is overwritten. The
                              determining values are computed by inverting the mapping; they are
                              not declared by hand.

  detect(rules, elicited)     compare each elicited coarse value against the value derived from
                              the finer one. A mismatch is a contradiction: at least one of the
                              two elicitations is wrong, and the instance is flagged.

The single precondition the method places on a rule set is that the relations be STIPULATED by
the codebook rather than inferred by the researcher. A stipulated rule is truth preserving, so a
mismatch is a genuine contradiction. A rule fitted to data is a hypothesis about the labels, and
testing an annotation against a hypothesis is not verification.

Usage
-----
    python verify.py --rules rules/goemotions.json --input elicitations.csv --out labelled.csv

`elicitations.csv` needs an `id` column plus one column per granularity, each holding the value
obtained in a call that could not see the other granularities. Blind elicitation is what makes
the check informative: granularities requested in a single response are reconciled by the model
itself, and the rules then fire on nothing.
"""
from __future__ import annotations
import argparse
import json
from collections import defaultdict


# ----------------------------------------------------------------------------- rule loading
def load_rules(path):
    with open(path, encoding="utf-8") as fh:
        rules = json.load(fh)
    rules.setdefault("compositions", [])
    rules.setdefault("mappings", [])
    rules.setdefault("satisfied_when", {})
    return rules


def determining_values(mapping):
    """Coarse values whose inverse image is a singleton. These ENTAIL the finer label.

    Computed by inverting the declared mapping; nothing is fitted and no data is consulted.
    """
    inverse = defaultdict(list)
    for fine, coarse in mapping["map"].items():
        inverse[coarse].append(fine)
    return {coarse: fines[0] for coarse, fines in inverse.items() if len(fines) == 1}


def independent_constraints(rules):
    """Constraints the check can test independently. A mapping entailed by others adds nothing."""
    return (len(rules["compositions"])
            + sum(1 for m in rules["mappings"] if m.get("independent", True)))


# ----------------------------------------------------------------------------- operations
def compose(rules, row):
    """Derive every composed granularity from the finer values present in `row`."""
    derived, sat = {}, rules["satisfied_when"]
    scope = dict(row)
    for comp in rules["compositions"]:
        operands = comp["operands"]
        if any(scope.get(o) in (None, "") for o in operands):
            derived[comp["target"]] = None
            continue
        if comp.get("operator", "and") != "and":
            raise ValueError(f"unsupported operator {comp['operator']!r}")
        holds = all(str(scope[o]).strip().lower() in
                    [v.lower() for v in sat.get(o, [])] for o in operands)
        value = comp["emit"]["true" if holds else "false"]
        derived[comp["target"]] = value
        scope.setdefault(comp["target"], value)   # later compositions may build on this one
    return derived


def propagate(rules, row):
    """Overwrite the finer label wherever an elicited coarse value determines it."""
    repairs = []
    out = dict(row)
    for mapping in rules["mappings"]:
        if not mapping.get("independent", True):
            continue                              # an entailed mapping determines nothing new
        table = determining_values(mapping)
        elicited = str(out.get(mapping["to"], "")).strip().lower()
        if elicited in table:
            before = out.get(mapping["from"])
            after = table[elicited]
            if before != after:
                repairs.append({"mapping": mapping["name"], "granularity": mapping["from"],
                                "from": before, "to": after, "because": mapping["to"] + "=" + elicited})
            out[mapping["from"]] = after
    return out, repairs


def detect(rules, row):
    """Flag contradictions between an elicited coarse value and the value derived from the finer."""
    conflicts = []
    derived = compose(rules, row)
    for target, value in derived.items():
        elicited = row.get(target)
        if value is not None and elicited not in (None, "") and \
                str(elicited).strip().lower() != str(value).strip().lower():
            conflicts.append({"granularity": target, "elicited": elicited, "derived": value})
    for mapping in rules["mappings"]:
        if not mapping.get("independent", True):
            continue
        fine = str(row.get(mapping["from"], "")).strip().lower()
        coarse = row.get(mapping["to"])
        if fine in mapping["map"] and coarse not in (None, ""):
            expected = mapping["map"][fine]
            if str(coarse).strip().lower() != expected:
                conflicts.append({"granularity": mapping["to"], "elicited": coarse,
                                  "derived": expected})
    return conflicts, derived


def apply_rules(rules, row):
    """Full step 4: propagate first, then detect on what remains."""
    repaired, repairs = propagate(rules, row)
    conflicts, derived = detect(rules, repaired)
    label = repaired.get(rules.get("reported_granularity")) \
        or derived.get(rules.get("reported_granularity"))
    return {"label": label, "repairs": repairs, "conflicts": conflicts,
            "flagged": bool(conflicts), "derived": derived}


# ----------------------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rules", required=True)
    ap.add_argument("--input", required=True, help="CSV with an id column and one column per granularity")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import csv
    rules = load_rules(args.rules)
    with open(args.input, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    results = []
    for row in rows:
        r = apply_rules(rules, row)
        results.append({"id": row.get("id"), "label": r["label"],
                        "flagged": int(r["flagged"]),
                        "repaired": int(bool(r["repairs"])),
                        "conflicts": ";".join(f'{c["granularity"]}:{c["elicited"]}!={c["derived"]}'
                                              for c in r["conflicts"])})
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)

    n = len(results)
    flagged = sum(r["flagged"] for r in results)
    repaired = sum(r["repaired"] for r in results)
    print(f"{n} instances | {repaired} repaired by propagation ({repaired/n:.1%}) | "
          f"{flagged} flagged for review ({flagged/n:.1%})")
    print(f"independent constraints in this rule set: {independent_constraints(rules)}")
    for mapping in rules["mappings"]:
        if mapping.get("independent", True):
            det = determining_values(mapping)
            if det:
                print(f"  {mapping['name']}: determining values {det}")


if __name__ == "__main__":
    main()
