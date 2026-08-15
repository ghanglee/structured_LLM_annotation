# Call-efficient structured LLM annotation — data and code

Companion release for *Call-efficient and high-accuracy structured LLM annotation for
gold-standard construction*.

The repository is split by what you want to do. The two halves are independent.

| Folder | For | Needs |
|:---|:---|:---|
| **`method/`** | applying the method to your own taxonomy | Python 3.9+, nothing else |
| **`reproduction/`** | recomputing every table in the paper | Python 3.9+, pandas, scipy |

**Neither half calls a model or needs an API key.** The elicitations the paper reports are
shipped as data, so all results recompute offline and at no cost. This matters more than
convenience: the reference model is a dated snapshot and cannot be reproduced identically once
it is retired, so the stored outputs are the only durable record of what was measured.

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
```

## What is here, and what is not

**Included.** Every elicitation from every configuration and every model, for both corpora; the
published baselines' elicitations and prompts; the gold labels; the three expert raters'
labels, anonymised; the prompts; the rule sets; and the verifier.

**Not included, and why.**

- **The text of the 700 building-regulation provisions.** They are verbatim extracts from the
  International Building Code and FGI guidelines, which are copyrighted, alongside ADA and
  Approved Documents material, which is not. **Per-row source attribution was not recorded
  during dataset construction**, so it is not currently possible to separate the freely
  redistributable rows from the rest. Until that provenance is restored, this release ships
  `data/provisions_index.csv` — an identifier, a SHA-256 of the normalised text, and its length
  — which lets you confirm you are working from the right provisions without republishing them.
  Every table in the paper recomputes without the text; only re-running elicitation from
  scratch requires it.
- **The GoEmotions comment text.** The corpus is Google's, under the Apache License 2.0, which
  would permit redistribution. It is fetched rather than copied so that this package tracks the
  upstream corpus, including any later redaction — the maintainers note that personal identities
  may in some cases be discoverable from Reddit text. `data/goemotions_sample.csv` gives the 300
  identifiers, reference labels and a SHA-256 per comment;
  `scripts/fetch_goemotions.py` retrieves the text and verifies it against those hashes.
- **An invalidated experiment.** An attempt to build a seven-sub-element decomposition of
  emotion is deliberately excluded. Its composition table was invented by the authors rather
  than stipulated by the corpus and resolved by nearest-neighbour distance, which is not a
  logical rule; it is described in the paper's limitations and should not be reused.

## A caveat on the reference standard

The building-regulation reference standard was constructed by the authors using the same
codebook the model is prompted with. If it was adjudicated with the current litmus-test set in
view, then accuracy measured against it partly reflects agreement with a procedure rather than
correctness. Readers should weigh the primary-experiment figures accordingly. This is stated in
the paper and repeated here because a public release invites the check.

## Licence

Code is MIT. Labels, annotations and model outputs produced by this study are CC BY 4.0.
Provision text is not redistributed and remains under its original terms. GoEmotions is
Google's, under its own licence.
