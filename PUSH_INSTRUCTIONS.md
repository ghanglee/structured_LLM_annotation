# Pushing this to GitHub

The repository is already initialised, committed on `main`, and pointed at
`https://github.com/ghanglee/structured_LLM_annotation.git`. Nothing needs preparing.

## If you have the GitHub CLI

```bash
cd structured_LLM_annotation
gh repo create ghanglee/structured_LLM_annotation --public --source=. --remote=origin --push
```

That creates the repository and pushes in one step.

## If you do not

Create an empty repository named `structured_LLM_annotation` at
<https://github.com/new> — no README, no .gitignore, no licence, since this repository already
has them — then:

```bash
cd structured_LLM_annotation
git push -u origin main
```

## Check before you push

```bash
git log --stat -1        # 38 files, no corpus text
git ls-files | wc -l     # 38
```

`.gitignore` excludes `goemotions_text.csv` and `provisions_text.csv`, so a fetched or
reconstructed corpus cannot be committed by accident later.

## Two things to settle first

1. **Rater consent.** `reproduction/data/raters.csv` holds three annotators' individual
   judgements. They are anonymised to `rater_1/2/3`, but three columns plus a unanimity flag are
   re-identifiable to anyone who knows who annotated. Confirm they agreed to individual-level
   release before the repository is public.
2. **The reference-standard caveat** in `README.md` states that accuracy may partly reflect
   agreement with a procedure rather than correctness. If you can establish that the reference was
   adjudicated independently of the litmus tests, replace that paragraph with the evidence.

## Suggested repository settings

- Description: *Data and code for call-efficient structured LLM annotation for gold-standard construction*
- Topics: `llm-annotation`, `gold-standard`, `bim`, `compliance-checking`, `goemotions`, `reproducibility`
- Enable **Zenodo** archiving before submission if the journal wants a DOI.
