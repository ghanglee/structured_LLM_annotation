# Structured evaluation with rule-based verification — data and code

Companion release for *Structured evaluation with rule-based verification for verifiable and review-efficient LLM annotation of gold-standard datasets*.

The repository is split by what you want to do. The two halves are independent.

| Folder | For | Needs |
|:---|:---|:---|
| **`method/`** | applying the method to your own taxonomy | Python 3.9+, nothing else |
| **`reproduction/`** | recomputing every table in the paper | Python 3.9+, pandas, scipy |

**Neither half calls a model or needs an API key**, with one clearly marked exception:
`reproduction/baselines/rerun/` re-executes a baseline against a live model and is not needed to
reproduce any table. The elicitations the paper reports are
shipped as data, so all results recompute offline and at no cost. This matters more than
convenience: the models are named by version alias rather than by dated snapshot and cannot be
reproduced identically once they are retired, so the stored outputs are the only durable record
of what was measured.

## Quick start

```bash
# apply the method to your own elicitations
cd method
python verify.py --rules rules/goemotions.json \
                 --input example/goemotions_elicitations.csv \
                 --out labelled.csv

# recompute the paper's tables
cd reproduction/scripts
python reproduce_acc.py
python reproduce_goemotions.py
python reproduce_annollm_rerun.py
```

## Licence

Code is MIT. Labels, annotations and model outputs produced by this study are CC BY 4.0.
Provision text is not redistributed and remains under its original terms. GoEmotions is
Google's, under its own licence.
