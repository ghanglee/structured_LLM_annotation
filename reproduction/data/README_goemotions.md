# GoEmotions sample

`goemotions_sample.csv` gives the 300 sampled comments as identifiers, reference labels and a
verification hash. The comment text is **not** redistributed here.

| column | meaning |
|:---|:---|
| `sample_index` | 1–300, the key used throughout `outputs/` |
| `goemotions_id` | the identifier in the source corpus |
| `fine` | reference label, one of 28 |
| `ekman` | reference Ekman class, by the corpus's published mapping |
| `sent` | reference sentiment class, likewise |
| `text_sha256` | SHA-256 of the comment after whitespace normalisation |
| `char_len` | length of the normalised comment |

## Getting the text

```bash
pip install datasets
python ../scripts/fetch_goemotions.py --out goemotions_text.csv
```

The script joins on `goemotions_id` and checks every comment against `text_sha256`, so you learn
immediately whether you have the same sample the paper scored rather than finding out through a
silently wrong number.

**Nothing in `scripts/` needs the text.** Every reported result is computed from labels alone.
The text is required only to re-run elicitation from scratch.

## Licence and why the text is not copied here

GoEmotions is distributed by Google Research under the **Apache License 2.0**, which permits
redistribution. The text is nevertheless fetched rather than copied, for two reasons.

The corpus is Reddit text, and the maintainers note that personal identities may in some cases be
discoverable from it. Fetching means this package tracks the upstream corpus, including any
redaction or withdrawal Google makes later; a frozen copy could not. The sample here carries no
author or username field.

The usual objection to fetch-on-demand is link rot, and it is a fair one — it is exactly why this
repository ships the model outputs rather than asking you to regenerate them. It does not apply
with the same force here: GoEmotions is mirrored on Hugging Face, in TensorFlow Datasets, and in
the `google-research` repository, and the hash manifest detects any drift between them.

Cite the corpus as:

> Demszky, D., Movshovitz-Attias, D., Ko, J., Cowen, A., Nemade, G., Ravi, S. (2020).
> GoEmotions: A Dataset of Fine-Grained Emotions. *Proceedings of the 58th Annual Meeting of the
> Association for Computational Linguistics*.

Sources: <https://huggingface.co/datasets/google-research-datasets/go_emotions> ·
<https://github.com/google-research/google-research/tree/master/goemotions>
