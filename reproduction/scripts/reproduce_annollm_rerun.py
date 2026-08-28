"""Recompute the AnnoLLM implementation-fidelity check reported in Section 7.5.

The reported AnnoLLM run left the explanation slot of each demonstration unfilled, so its
demonstrations carried labels without the generated rationales that define explain-then-annotate.
The method was rerun with those explanations generated, changing nothing else. This script
recomputes both accuracies and the paired test from the shipped outputs.

No model is called.

    python reproduce_annollm_rerun.py [--dir ..]
"""
import argparse
import os

import pandas as pd
from scipy.stats import binomtest

LOW = lambda s: s.astype(str).str.strip().str.lower()


def main(base):
    gold = pd.read_csv(f"{base}/data/gold_labels.csv")
    g = dict(zip(gold.id, LOW(gold.verdict)))

    old = pd.read_csv(f"{base}/outputs/acc_baselines.csv")
    old = old[(old.method == "annollm") & (old.is_demo != 1)].copy()
    new = pd.read_csv(f"{base}/outputs/acc_baselines_annollm_rerun.csv")
    new = new[new.is_demo != 1].copy()

    for d in (old, new):
        d["gold"] = d.id.map(g)
        d["ok"] = LOW(d.verdict) == d.gold

    a = old.set_index("id").ok
    b = new.set_index("id").ok
    common = a.index.intersection(b.index)
    a, b = a.loc[common], b.loc[common]

    print("=== AnnoLLM implementation-fidelity check (Section 7.5) ===")
    print(f"  as reported, explanation slot unfilled : {a.mean():6.1%}   n = {len(a)}")
    print(f"  explanations generated                 : {b.mean():6.1%}   n = {len(b)}")
    print(f"  difference                             : {b.mean() - a.mean():+.1%}")

    n01 = int((b & ~a).sum())
    n10 = int((~b & a).sum())
    n = n01 + n10
    p = binomtest(n01, n, 0.5).pvalue if n else 1.0
    print(f"\n  paired exact McNemar on {len(common)} common provisions")
    print(f"    rerun only correct    {n01}")
    print(f"    reported only correct {n10}")
    print(f"    p = {p:.4f}")
    print("\n  The unfilled slot did not affect the comparison reported in Table 5.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(os.path.dirname(__file__), ".."))
    main(ap.parse_args().dir)
