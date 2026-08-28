"""Recompute the GoEmotions results from the shipped elicitations.

No model is called. The comment text is not required and is not redistributed here; the corpus
is Google's and is fetched separately (see ../data/README_goemotions.md).

    python reproduce_goemotions.py [--dir ..]
"""
import argparse
import json
import os
from collections import Counter, defaultdict

import pandas as pd
from scipy.stats import binomtest


def mcnemar(a_ok, b_ok):
    n01 = int((a_ok & ~b_ok).sum())
    n10 = int((~a_ok & b_ok).sum())
    n = n01 + n10
    return n01, n10, (binomtest(n01, n, 0.5).pvalue if n else 1.0)


def main(base):
    rules = json.load(open(f"{base}/../method/rules/goemotions.json", encoding="utf-8"))
    F2E = next(m["map"] for m in rules["mappings"] if m["name"] == "fine_to_ekman")
    F2S = next(m["map"] for m in rules["mappings"] if m["name"] == "fine_to_sentiment")
    inv = defaultdict(list)
    for f, e in F2E.items():
        inv[e].append(f)
    DET = {e: v[0] for e, v in inv.items() if len(v) == 1}

    gold = pd.read_csv(f"{base}/data/goemotions_sample.csv")
    d = pd.read_csv(f"{base}/outputs/goemotions_proposed.csv").merge(
        gold[["sample_index", "fine"]].rename(columns={"fine": "gold"}), on="sample_index")

    fires = d.ekman_A.isin(DET)
    A3 = d.fine_A.where(~fires, d.ekman_A.map(DET))
    resid = (~fires) & (d.ekman_A != A3.map(F2E))
    A1 = d.combined_fine.where(~d.combined_ekman.isin(DET), d.combined_ekman.map(DET))
    M = dict(zip(d.sample_index, d.fine_M))
    A2 = pd.Series([a if a == b else (b if M.get(i) == b else a)
                    for i, a, b in zip(d.sample_index, d.fine_A, d.fine_B)], index=d.index)
    esc = (d.fine_A != d.fine_B).mean()

    print("=== Table 11: proposed configurations and SOTA baselines on GoEmotions ===")
    for nm, v, fl, calls in (("A1", A1, pd.Series(False, index=d.index), 1.00),
                             ("A2", A2, pd.Series(False, index=d.index), round(2 + esc, 2)),
                             ("A3", A3, resid, 2.00)):
        ok = v == d.gold
        print(f"  {nm}  calls {calls:4.2f}  all {ok.mean():6.1%}  "
              f"auto {ok[~fl].mean():6.1%}  referred {fl.mean():5.1%}")

    print("\n=== Table 12: paired exact McNemar against the SOTA baselines ===")
    b = pd.read_csv(f"{base}/outputs/goemotions_baselines.csv")
    gm = dict(zip(d.sample_index, d.gold))
    agg = {}
    for m, grp in b.groupby("method"):
        if m == "dream":
            r1 = grp[grp.pass_id == "lit_r1"].set_index("sample_index").label
            r2 = grp[grp.pass_id == "prag_r1"].set_index("sample_index").label
            agg[m] = {i: (r1[i] if r1[i] == r2[i] else None) for i in r1.index}
        else:
            byitem = defaultdict(list)
            for r in grp.itertuples():
                byitem[r.sample_index].append(r.label)
            agg[m] = {i: Counter(v).most_common(1)[0][0] for i, v in byitem.items()}
    for nm, v in (("A1", A1), ("A3", A3)):
        pv = dict(zip(d.sample_index, v))
        for m, lab in sorted(agg.items()):
            common = [i for i in pv if lab.get(i)]
            a_ok = pd.Series([pv[i] == gm[i] for i in common])
            b_ok = pd.Series([lab[i] == gm[i] for i in common])
            n01, n10, p = mcnemar(a_ok, b_ok)
            print(f"  {nm} vs {m:16s} n={len(common):3d}  {a_ok.mean():.1%} vs {b_ok.mean():.1%}  p={p:.3g}")

    print("\n=== Table 13: effect of blind elicitation ===")
    print(f"  fine label alone, one call                    {(d.fine_A==d.gold).mean():6.1%}")
    print(f"  all granularities in the SAME call            {(d.combined_fine==d.gold).mean():6.1%}")
    print(f"  fine and Ekman BLIND, rules applied           {(A3==d.gold).mean():6.1%}")
    selfcons = ((d.combined_ekman == d.combined_fine.map(F2E)) &
                (d.combined_sent == d.combined_fine.map(F2S))).mean()
    print(f"  single call is self-consistent on             {selfcons:6.1%}  -> the rules fire on nothing")

    print("\n=== entailment: the third constraint adds no flag ===")
    c1 = d.ekman_A == d.fine_A.map(F2E)
    c2 = d.sent_A == d.fine_A.map(F2S)
    c3 = d.sent_A == d.ekman_A.map({e: F2S[f] for e, f in DET.items()} |
                                   {e: F2S[v[0]] for e, v in inv.items()})
    print(f"  c1 and c2 flag        {int((~(c1 & c2)).sum())}/300 ({(~(c1&c2)).mean():.1%})")
    print(f"  c1, c2 and c3 flag    {int((~(c1 & c2 & c3)).sum())}/300")
    print(f"  caught by c3 alone    {int((~c3 & c1 & c2).sum())}")
    print(f"\n  Ekman constraint alone, no propagation  {int((~c1).sum())}/300 ({(~c1).mean():.1%})")
    print(f"  two-level residual after propagation     {int(resid.sum())}/300 ({resid.mean():.1%})")

    print("\n=== error concentration ===")
    ok = d.fine_A == d.gold
    share = ((~ok) & ~c1).sum() / (~ok).sum()
    print(f"  Ekman constraint: queue {(~c1).mean():.1%} holds {share:.1%} of errors -> "
          f"{share/(~c1).mean():.2f}-fold")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(os.path.dirname(__file__), ".."))
    main(ap.parse_args().dir)
