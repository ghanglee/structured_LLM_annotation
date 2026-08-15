# Reproducing the paper

```bash
pip install pandas scipy
cd scripts
python reproduce_acc.py           # Tables 4, 5, 6, 7, 8, 12 and error concentration
python reproduce_goemotions.py    # Tables 9, 10, 11 and the entailment result
```

No model is called. Both scripts read only `data/` and `outputs/`.

## Layout

```
data/
  provisions_index.csv     700 identifiers, text SHA-256 and length. No provision text.
  gold_labels.csv          reference verdict plus the seven properties and three aggregates
  raters.csv               three expert annotators, anonymised, with the unanimity flag
  goemotions_sample.csv    300 GoEmotions identifiers and reference labels
outputs/
  acc_opus5.csv            per-instance elicitations for every configuration, Claude Opus 5
  acc_haiku45.csv          the same for Claude Haiku 4.5
  acc_gpt56sol.csv         the same for GPT-5.6 Sol
  acc_gemini31pro.csv      the same for Gemini 3.1 Pro
  acc_baselines.csv        the four published baselines, per instance
  goemotions_proposed.csv  every GoEmotions elicitation, including the single-call condition
  goemotions_baselines.csv the four published baselines, one row per pass
baselines/prompts/         the reimplemented baselines' prompts, verbatim
scripts/
```

## Two known deviations in the baseline runs

Both are disclosed in the paper and both are visible in the shipped outputs.

- **Tavakoli and Zamani** was implemented with several personas of one model rather than an
  ensemble across providers, which is the published method's core mechanism. It is the closest
  competitor on both corpora, so the deviation understates it.
- **DREAM** on the building-regulation corpus fed the same first-round rationale to both
  second-round calls instead of crossing them. The GoEmotions run crosses them correctly.

## Held-out demonstrations

AnnoLLM holds out 8 label-diverse demonstrations, so it scores 692 of 700 provisions and 292 of
300 comments. Contrasts against it are computed on the instances both methods label, which is
why some tests report n = 692 or n = 292 rather than the full corpus.

## Restoring the provision text

`scripts/reconstruct_provisions.py` verifies a text file against the shipped hashes. Per-row
source attribution was not recorded when the dataset was built, so the script cannot fetch the
text for you; it can only confirm that a corpus you already hold is the same one the paper used.
