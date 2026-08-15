# Applying the method to your own taxonomy

Four steps. Steps 1 and 2 are done once per dataset; steps 3 and 4 run on every instance, and
only step 3 costs model calls.

## 1. Decompose

Express your label as a hierarchy of granularities, or as sub-properties from which it is
composed. `rules/adcc_checkability.json` shows a conjunctive decomposition — seven properties
judged on separate axes, composing into a verdict. `rules/goemotions.json` shows a functional
coarsening — one level a function of the other.

## 2. Declare

Write the relations as a rule file. **The relations must be stipulated by your codebook, not
inferred by you.** This is a precondition, not a style preference. A stipulated rule is truth
preserving: the label *is* the composition, so a mismatch between an elicited value and a
derived one is a genuine contradiction. A rule you invent is a hypothesis about the labels, and
testing an annotation against a hypothesis is not verification. If your codebook declares no
composition, the method reduces to a single structured pass with no check, and you should stop
at step 3.

`verify.py --rules <file>` reports how many **independent** constraints your rule set yields. A
chain of granularities yields one however deep it is, because each coarse-to-coarse relation is
entailed by the others; sub-elements on separate axes yield one each. This is decidable before
you annotate anything, and it predicts whether the check will repay its calls.

## 3. Elicit blind

Obtain each granularity in a call that cannot see the others. This is what makes the rules
informative. Granularities requested in a single response are reconciled by the model itself —
measured at 100% self-consistency on GoEmotions — so the rules would fire on nothing. The
prompts in `prompts/` are the ones used in the paper; the codebook-specific content is what you
replace.

## 4. Apply

```bash
python verify.py --rules rules/goemotions.json --input your_elicitations.csv --out labelled.csv
```

`your_elicitations.csv` needs an `id` column plus one column per granularity. The verifier does
three things, in order:

- **compose** — derive coarser granularities from finer ones by the declared conjunctions;
- **propagate** — where a mapping's inverse image is a singleton, the coarse value *entails* the
  finer label, so the finer label is overwritten. These determining values are computed by
  inverting your mapping, not declared by hand;
- **detect** — flag any remaining contradiction between an elicited value and a derived one.

Propagation resolves; detection refers. On GoEmotions propagation repairs 19.3% of labels and
cuts the review queue from 22.7% to 3.3%.

## Worked example

`example/goemotions_elicitations.csv` holds the paper's actual GoEmotions elicitations. Running
the command above reproduces the reported queue exactly:

```
300 instances | 58 repaired by propagation (19.3%) | 10 flagged for review (3.3%)
independent constraints in this rule set: 1
  fine_to_ekman: determining values {'disgust': 'disgust', 'neutral': 'neutral'}
```
