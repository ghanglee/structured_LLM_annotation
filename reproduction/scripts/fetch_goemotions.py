"""Fetch the 300 sampled GoEmotions comments from source and verify them against the manifest.

The comment text is not redistributed in this repository. GoEmotions is Google's, released under
the Apache License 2.0, and is permanently available from several mirrors. Fetching rather than
copying means this package tracks the upstream corpus, including any redaction Google makes
later — a frozen copy could not.

    pip install datasets
    python fetch_goemotions.py --out ../data/goemotions_text.csv

The script joins on the corpus identifier and checks a SHA-256 of each normalised comment against
`data/goemotions_sample.csv`, so a mismatch is caught rather than silently scored.

Nothing in `scripts/` needs the text. Every number the paper reports is computed from labels
alone; the text is required only to re-run elicitation from scratch.
"""
import argparse
import csv
import hashlib
import os
import re
import sys

MIRRORS = [
    ("Hugging Face", "google-research-datasets/go_emotions"),
]


def norm(s):
    return re.sub(r"\s+", " ", str(s)).strip()


def load_manifest(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return {r["goemotions_id"]: r for r in csv.DictReader(fh)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=os.path.join(os.path.dirname(__file__),
                                                       "..", "data", "goemotions_sample.csv"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("Install the loader first:  pip install datasets")

    wanted = set(manifest)
    found = {}
    for split in ("train", "validation", "test"):
        ds = load_dataset(MIRRORS[0][1], "raw", split=split)
        for row in ds:
            rid = str(row.get("id"))
            if rid in wanted and rid not in found:
                found[rid] = row.get("text", "")
        if len(found) == len(wanted):
            break

    ok = bad = 0
    rows = []
    for rid, rec in manifest.items():
        text = found.get(rid)
        if text is None:
            continue
        digest = hashlib.sha256(norm(text).encode()).hexdigest()
        if digest == rec["text_sha256"]:
            ok += 1
        else:
            bad += 1
        rows.append({"sample_index": rec["sample_index"], "goemotions_id": rid, "text": text,
                     "verified": int(digest == rec["text_sha256"])})

    rows.sort(key=lambda r: int(r["sample_index"]))
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["sample_index", "goemotions_id", "text", "verified"])
        w.writeheader()
        w.writerows(rows)

    missing = len(manifest) - len(rows)
    print(f"{ok} of {len(manifest)} comments fetched and verified. {bad} mismatched, {missing} missing.")
    if ok == len(manifest):
        print("This is the sample the paper scored.")
    elif missing:
        print("Missing identifiers usually mean the upstream corpus has been redacted since "
              "publication. The labels and all reported results are unaffected.")


if __name__ == "__main__":
    main()
