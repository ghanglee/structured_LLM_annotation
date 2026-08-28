# -*- coding: utf-8 -*-
"""Prompt surgery for the three experimental arms.

as-run       prompts exactly as reimplemented and reported in the manuscript
generic      the seven property definitions AND their conjunction removed
definitions  generic, plus ADCC_definitions_only_v11.md appended
             (per-property definitions and litmus tests; no composition rule,
              no evaluation order, no decision sequence)

Every removal is asserted. If a source prompt changes, this fails loudly rather
than silently shipping the wrong condition.
"""
import re

# The definitions-plus-conjunction block, verbatim, in the three list-style prompts.
_CONJ = re.compile(
    r"\nA requirement is BIM-checkable only when.*?independently pass or fail\.\n"
    r"(\nComplex calculation over model geometry does not disqualify a requirement\.\n)?",
    re.S)

# DREAM states the same relation negatively, inside the evidence paragraph.
_DREAM_PRO = (
    "the sentence plainly cannot be\nchecked — it is a fragment, a definition or permission, "
    "it depends on a cited table, external\ndata, a physical test or a person's judgment, or it "
    "packs several independent criteria — then\nsay so and return \"No\".",
    "the sentence plainly cannot be\nchecked, then say so and return \"No\".")
_DREAM_CON = (
    "the sentence plainly can be\nchecked — it is a whole obligation, fully specified in itself, "
    "decidable from a standard BIM\nmodel, and states a single criterion — then say so and return "
    "\"Yes\". Note that complex\ncalculation over model geometry is not a defect.",
    "the sentence plainly can be\nchecked, then say so and return \"Yes\".")

_APPEND = (
    "\n\n## Annotation standard\n\n"
    "The definitions below fix what each term means and how to test for it. They are "
    "definitions of individual properties only. How the properties combine into the final "
    "verdict is not given; decide the verdict yourself.\n\n")

# Words that must not survive into the generic or definitions arms.
_RELATION = re.compile(
    r"all of the following|only when|conjunction|composition|Verdict\s*=|∧|"
    r"short-circuit|and all three|Completeness\s*=|Self-Sufficiency\s*=", re.I)


def apply(path, text, arm, codebook=None):
    if arm == "as-run":
        return text
    if path.endswith(("prompt_annollm_holistic.md", "prompt_annollm_explain.md")):
        return text          # written holistic from the start; nothing to remove
    if path.endswith("prompt_annollm.md"):
        raise SystemExit("the faithful arm must load prompt_annollm_holistic.md")
    name = path.replace("\\", "/").split("/")[-1]
    if name in ("prompt_annollm.md", "prompt_coannotating.md", "prompt_tavakoli.md"):
        out, n = _CONJ.subn("\n", text)
        assert n == 1, "definitions block not found in %s" % name
    elif name == "prompt_dream_pro.md":
        old, new = _DREAM_PRO
        assert old in text, "DREAM pro clause not found"
        out = text.replace(old, new)
    elif name == "prompt_dream_con.md":
        old, new = _DREAM_CON
        assert old in text, "DREAM con clause not found"
        out = text.replace(old, new)
    else:
        raise SystemExit("unknown prompt file: " + name)

    leak = _RELATION.search(out)
    assert not leak, "relation language survives in %s: %r" % (name, leak.group(0))

    if arm == "definitions":
        assert codebook, "--codebook is required for the definitions arm"
        out = out.rstrip() + _APPEND + codebook.strip() + "\n"
    return out
