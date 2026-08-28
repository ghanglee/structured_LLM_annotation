"""Recompute the building-regulation results from the shipped model outputs.

No model is called. Every number below comes from `outputs/` and `data/gold_labels.csv`, so the
tables reproduce without an API key, without cost, and without the provision text.

    python reproduce_acc.py [--dir ..]
"""
import argparse
import os
from collections import Counter

import pandas as pd
from scipy.stats import binomtest

MODELS = [("claude-opus-5", "acc_opus5.csv"), ("gemini-3.1-pro", "acc_gemini31pro.csv"),
          ("gpt-5.6-sol", "acc_gpt56sol.csv"), ("claude-haiku-4.5", "acc_haiku45.csv")]
LOW = lambda s: s.astype(str).str.strip().str.lower()


def mcnemar(a_ok, b_ok):
    n01 = int((a_ok & ~b_ok).sum())
    n10 = int((~a_ok & b_ok).sum())
    n = n01 + n10
    return n01, n10, (binomtest(n01, n, 0.5).pvalue if n else 1.0)


def main(base):
    gold = pd.read_csv(f"{base}/data/gold_labels.csv")
    g = dict(zip(gold.id, LOW(gold.verdict)))

    print("=== Table 3: proposed configurations and SOTA baselines, Claude Opus 5 ===")
    d = pd.read_csv(f"{base}/outputs/acc_opus5.csv")
    d["gold"] = d.id.map(g)
    for cfg, flag in (("A1", None), ("A2", None), ("A3", "A3_check_failed"), ("A4", "A4_check_failed")):
        ok = LOW(d[f"{cfg}_verdict"]) == d.gold
        fl = (d[flag] == 1) if flag else pd.Series(False, index=d.index)
        auto = ok[~fl]
        print(f"  {cfg}  all {ok.mean():6.1%}   auto {auto.mean():6.1%}   referred {fl.mean():5.1%}")

    print("\n=== Section 5.1: paired exact McNemar against the SOTA baselines ===")
    b = pd.read_csv(f"{base}/outputs/acc_baselines.csv")
    b["gold"] = b.id.map(g)
    b["v"] = LOW(b.verdict)
    for cfg in ("A1", "A2"):
        pv = dict(zip(d.id, LOW(d[f"{cfg}_verdict"])))
        for m, grp in b.groupby("method"):
            grp = grp[grp.v.isin(["yes", "no"]) & (grp.is_demo.fillna(0).astype(int) == 0)]
            a_ok = pd.Series([pv[i] == g[i] for i in grp.id], index=grp.index)
            b_ok = grp.v == grp.gold
            n01, n10, p = mcnemar(a_ok, b_ok)
            print(f"  {cfg} vs {m:16s} n={len(grp):3d}  {a_ok.mean():.1%} vs {b_ok.mean():.1%}  "
                  f"{cfg} only {n01:3d} / other {n10:3d}  p={p:.3g}")

    print("\n=== Table 5: human annotators ===")
    r = pd.read_csv(f"{base}/data/raters.csv")
    r["gold"] = r.id.map(g)
    for col in ("rater_1", "rater_2", "rater_3", "majority"):
        acc = (LOW(r[col]) == r.gold).mean()
        pv = dict(zip(d.id, LOW(d.A2_verdict)))
        a_ok = pd.Series([pv[i] == g[i] for i in r.id], index=r.index)
        n01, n10, p = mcnemar(a_ok, LOW(r[col]) == r.gold)
        print(f"  {col:9s} {acc:6.1%}   A2 vs it: A2 only {n01:3d} / it {n10:3d}  p={p:.3g}")
    un = r.unanimous == 1
    pv = dict(zip(d.id, LOW(d.A2_verdict)))
    a_ok = pd.Series([pv[i] == g[i] for i in r.id], index=r.index)
    print(f"\n  unanimous n={int(un.sum())}, contested n={int((~un).sum())}")
    print(f"  A2        unanimous {a_ok[un].mean():.1%}  contested {a_ok[~un].mean():.1%}")
    for col in ("rater_1", "rater_2", "rater_3"):
        ok = LOW(r[col]) == r.gold
        print(f"  {col}   unanimous {ok[un].mean():.1%}  contested {ok[~un].mean():.1%}")

    print("\n=== Table 4: attribution of the advantage ===")
    comp_ok = LOW(d.A1_verdict) == d.gold
    hol_ok = LOW(d.Ah_Verdict) == d.gold
    n01, n10, p = mcnemar(comp_ok, hol_ok)
    print(f"  holistic verdict under the codebook  {hol_ok.mean():.1%}")
    print(f"  composed from seven properties (A1)  {comp_ok.mean():.1%}   "
          f"composed only {n01} / holistic only {n10}  p={p:.3g}")

    print("\n=== Table 6: across four models ===")
    for name, fn in MODELS:
        if not os.path.exists(f"{base}/outputs/{fn}"):
            continue
        m = pd.read_csv(f"{base}/outputs/{fn}")
        m["gold"] = m.id.map(g)
        a1 = (LOW(m.A1_verdict) == m.gold).mean()
        a2 = (LOW(m.A2_verdict) == m.gold).mean()
        f3 = m.A3_check_failed == 1
        f4 = m.A4_check_failed == 1
        a3 = (LOW(m.A3_verdict) == m.gold)[~f3].mean()
        a4 = (LOW(m.A4_verdict) == m.gold)[~f4].mean()
        print(f"  {name:17s} A1 {a1:5.1%}  A2 {a2:5.1%} ({a2-a1:+.1%})  "
              f"A3auto {a3:5.1%} ({f3.mean():.1%})  A4auto {a4:5.1%} ({a4-a3:+.1%})")

    print("\n=== error concentration ===")
    print("  share of a configuration's errors inside its queue, over the share of the corpus queued")
    for cfg, flag in (("A3", "A3_check_failed"), ("A4", "A4_check_failed")):
        ok = LOW(d[f"{cfg}_verdict"]) == d.gold
        fl = d[flag] == 1
        share_err = ((~ok) & fl).sum() / (~ok).sum()
        print(f"  {cfg}: queue {fl.mean():.1%} holds {share_err:.1%} of errors -> "
              f"{share_err/fl.mean():.2f}-fold")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(os.path.dirname(__file__), ".."))
    main(ap.parse_args().dir)
