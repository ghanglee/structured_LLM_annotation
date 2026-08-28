# AnnoLLM fidelity rerun

**This is the only part of the repository that calls a model.** Nothing here is needed to
reproduce a table; `reproduction/scripts/reproduce_annollm_rerun.py` recomputes the result from
the shipped outputs, offline and for free.

## What it corrects

`m_annollm()` in the original runner rendered each demonstration as

```
SENTENCE: …
CORRECT ANSWER: Yes|No
WHY THAT ANSWER IS CORRECT: <explain before answering>
```

`d['why']` was never populated, so all eight demonstrations went out carrying that placeholder
while the prompt above them said the examples "show the correct answer and why it is correct."
AnnoLLM's explain-then-annotate mechanism therefore never executed.

## Arms

| `--arm` | prompt | demonstrations | changes |
|:---|:---|:---|:---|
| `as-run` | as reported | label only, placeholder | reproduces the defect |
| `explanations-only` | **identical** to as-run | label plus generated explanation | one: the defect |
| `faithful` | holistic task definition only | label plus explanation generated without the codebook | two: defect and prose |

`explanations-only` is the arm reported in Section 7.5. It changes exactly one thing, so its
result measures what the unfilled slot cost. `faithful` additionally removes the enumerated
criteria from the prompt; it is provided for completeness and is not reported.

## Running it

```bash
export ANTHROPIC_API_KEY=...
python run_baselines_codebook.py --method annollm --arm explanations-only \
    --model claude-opus-5 \
    --input  <provisions csv: id,Regulation> \
    --gold   <gold standard xlsx: ID,Verdict> \
    --out    results --work work_annollm
```

Add `--dry-run assembled_prompts` to assemble and write both prompts without calling anything.

The generated explanations are cached to `work_annollm/<tag>/annollm_explanations.json`. That
file is **not committed**: the explanations quote the provisions they explain, and provision text
is not redistributed. It regenerates in one batched call.

`prompt_surgery.py` builds each arm with hard assertions, and `leak_check()` aborts the run if a
property name, an aggregate name, or a statement of how the properties combine would reach the
model in the `faithful` arm.
