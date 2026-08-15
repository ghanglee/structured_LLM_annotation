"""Verify a provision corpus against the shipped hashes.

Per-row source attribution was not recorded when this dataset was built, so this script cannot
fetch the provisions for you. What it can do is confirm that a corpus you already hold is the
same one the paper scored, row for row.

    python reconstruct_provisions.py --texts my_provisions.csv

`my_provisions.csv` needs an `id` column and a `text` column. Text is normalised by collapsing
whitespace before hashing, matching how the index was built.
"""
import argparse
import csv
import hashlib
import os
import re


def norm(s):
    return re.sub(r"\s+", " ", str(s)).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texts", required=True)
    ap.add_argument("--index", default=os.path.join(os.path.dirname(__file__),
                                                    "..", "data", "provisions_index.csv"))
    a = ap.parse_args()

    with open(a.index, newline="", encoding="utf-8-sig") as fh:
        index = {r["id"]: r for r in csv.DictReader(fh)}
    with open(a.texts, newline="", encoding="utf-8-sig") as fh:
        supplied = {r["id"]: r["text"] for r in csv.DictReader(fh)}

    ok = miss = bad = 0
    for pid, row in index.items():
        if pid not in supplied:
            miss += 1
            continue
        if hashlib.sha256(norm(supplied[pid]).encode()).hexdigest() == row["text_sha256"]:
            ok += 1
        else:
            bad += 1
            if bad <= 5:
                print(f"  mismatch at id {pid}: supplied {len(norm(supplied[pid]))} chars, "
                      f"expected {row['char_len']}")
    print(f"\n{ok} of {len(index)} provisions match. {miss} missing, {bad} mismatched.")
    if ok == len(index):
        print("This is the corpus the paper scored.")


if __name__ == "__main__":
    main()
