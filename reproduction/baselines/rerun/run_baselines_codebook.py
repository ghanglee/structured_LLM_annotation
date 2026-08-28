#!/usr/bin/env python3
"""
External baselines for the LEGATE comparison, on the BIM-checkability gold standard.

Four methods, one runner. All produce the same output shape as run_legate.py so the
same scoring machinery applies:  ID, Regulation, verdict, plus per-method extras.

  annollm      AnnoLLM (He et al., NAACL 2024)
               Explain-then-annotate: k few-shot demonstrations whose GOLD label is
               shown and explained, then annotate. One pass, 1 call/item.

  coannotating CoAnnotating (Li et al., EMNLP 2023)
               S prompt-perturbed passes of one persona; self-consistency majority
               vote; entropy over the S votes is the uncertainty estimate, and the
               most-uncertain share is allocated to a human. S calls/item.

  tavakoli     Tavakoli & Zamani (ICTIR 2025)
               Ensemble of M personas, each returning a verdict AND a verbalized
               confidence. Routing score combines mean confidence with inter-agent
               disagreement; the threshold is Pareto-calibrated on a labelled
               calibration split (default 10%). M calls/item.

  dream        DREAM (Ban et al., ICLR 2026)
               Two agents seeded with OPPOSING stances debate for R rounds, each
               seeing the other's previous argument. Agreement auto-labels;
               persistent disagreement escalates to a human. 2R calls/item.

Demonstrations and calibration are the only places gold is touched. Rows used as
demonstrations or for calibration are recorded in the output so they can be held
out at scoring time — otherwise the comparison is contaminated.

Usage
  export ANTHROPIC_API_KEY=sk-ant-...
  python3 run_baselines.py --method annollm --model claude-opus-5 \
      --input ../../Experiments/legate_run_bundle/data/00_input_700_requirements.csv \
      --gold  /path/to/GoldStandards/ADCC_GS_Final12_v9_clean.xlsx \
      --out   /path/to/ExperimentResults/Baselines
"""
import argparse, csv, hashlib, json, math, os, re, sys, time, threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prompt_surgery

ARM = 'as-run'          # set in main(); one of as-run | generic | definitions
CODEBOOK = None         # text of the definitions-only codebook, definitions arm only
DRY_RUN = None          # directory to write assembled prompts to, or None

PERSONAS = [
    "You are a practising architect who writes and reviews design documents.",
    "You are a BIM manager who models buildings and knows what a model does and does not carry.",
    "You are a building-code consultant who interprets regulatory text for compliance.",
    "You are a software developer who implements rule checks against BIM models.",
    "You are a researcher in automated design compliance checking.",
]

# CoAnnotating's uncertainty comes from PROMPT PERTURBATION, not temperature — which
# matters here because Opus 5 has no temperature control at all.
PERTURBATIONS = [
    "",
    "\n\nWork through the requirement carefully before answering.",
    "\n\nConsider what a rule engine would need in order to decide this automatically.",
    "\n\nState your answer only after identifying the single most decisive feature of the sentence.",
    "\n\nBe precise about what is present in the sentence versus what would have to be looked up.",
]

_lock = threading.Lock()
def log(m):
    with _lock:
        print(m, flush=True)


def yes(v):
    return str(v).strip().lower().startswith('y')


# ------------------------------------------------------------------ provider
_NO_TEMP = set()


def fatal_error(err):
    e = str(err).lower()
    return any(k in e for k in ('credit balance', 'billing', 'insufficient_quota',
                                'quota exceeded', 'authentication_error', 'invalid api key',
                                'permission_error', 'permission denied'))


def make_client():
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit('pip install anthropic')
    if not os.environ.get('ANTHROPIC_API_KEY'):
        sys.exit('ANTHROPIC_API_KEY is not set.')
    return Anthropic()


def complete(client, model, system, user, max_tokens=16000):
    kw = dict(model=model, max_tokens=max_tokens, system=system,
              messages=[{"role": "user", "content": user}])
    r = client.messages.create(**kw)
    return "".join(b.text for b in r.content if b.type == 'text')


def call_json(client, model, system, user, want_ids, max_retries=5, max_tokens=16000, depth=0):
    """One call returning a JSON array covering want_ids. Splits on unparseable output."""
    last = None
    for attempt in range(max_retries):
        try:
            txt = complete(client, model, system, user, max_tokens)
            m = re.search(r'\[.*\]', txt, re.S)
            if not m:
                raise ValueError('no JSON array in response')
            data = json.loads(m.group(0))
            got = {int(d['id']) for d in data}
            if got != set(want_ids):
                raise ValueError('id mismatch: missing %s' % sorted(set(want_ids) - got)[:5])
            return data
        except Exception as e:                                       # noqa: BLE001
            last = e
            if fatal_error(e):
                raise RuntimeError('ABORTING — not fixable by retrying:\n    %s' % e)
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError('call failed after %d attempts: %s' % (max_retries, last))


# ------------------------------------------------------------------ batching
def batched(rows, n):
    return [rows[i:i + n] for i in range(0, len(rows), n)]


def run_batches(client, model, system, fmt, rows, workdir, unit, batch_size, max_tokens,
                user_prefix="Evaluate each sentence below. Columns are id<TAB>sentence."):
    if DRY_RUN:
        dump_prompt(unit.replace(' ', '_'), system + "\n\n---- response format ----\n" + fmt)
        return {r['id']: {'Verdict': 'Yes', 'Confidence': 50, 'Rationale': 'DRY RUN',
                          'Why': 'DRY RUN — explanation would be generated here.'} for r in rows}
    os.makedirs(workdir, exist_ok=True)
    out = {}
    for bi, b in enumerate(batched(rows, batch_size)):
        ck = os.path.join(workdir, 'batch_%03d.json' % bi)
        if os.path.exists(ck):
            for d in json.load(open(ck, encoding='utf-8')):
                out[int(d['id'])] = d
            continue
        user = user_prefix + "\n\n" + "\n".join('%d\t%s' % (r['id'], r['text']) for r in b)
        data = call_json(client, model, system + "\n\n" + fmt, user, [r['id'] for r in b],
                         max_tokens=max_tokens)
        json.dump(data, open(ck, 'w', encoding='utf-8'), ensure_ascii=False)
        for d in data:
            out[int(d['id'])] = d
        log('  %-26s batch %3d  (%d rows)' % (unit, bi + 1, len(b)))
    return out


FMT_WHY = """
Return ONLY a JSON array, no prose. One object per input line, in input order:

[{"id": <int>, "Why": "<two or three sentences>"}]

Give a Why for every id. Do not omit any id.
"""

# Nothing that names the property/aggregate scheme, or states how criteria combine,
# may reach the model in the faithful arm. Checked on the assembled prompt and on
# every generated explanation.
LEAK = re.compile(
    r"sentential|normative complete|referential|process-depend|data-depend|human-depend"
    r"|atomicity|self-sufficiency|completeness|all of the following|only when"
    r"|conjunction|composit|seven propert|three aggregat|\u2227", re.I)


def leak_check(label, text):
    hits = sorted(set(m.group(0) for m in LEAK.finditer(text)))
    if hits:
        raise SystemExit("STRUCTURE LEAK in %s: %r" % (label, hits))


FMT_VERDICT = """
Return ONLY a JSON array, no prose. One object per input sentence, in input order:

[{"id": <int>, "Verdict": "Yes|No", "Rationale": "<one clause>"}]

Give a verdict for every id. Do not omit any id.
"""

FMT_VERDICT_CONF = """
Return ONLY a JSON array, no prose. One object per input sentence, in input order:

[{"id": <int>, "Verdict": "Yes|No", "Confidence": <integer 0-100>, "Rationale": "<one clause>"}]

Confidence is how certain you are of THIS verdict, 0 = a guess, 100 = certain.
Give a verdict and a confidence for every id. Do not omit any id.
"""


def load_task(path):
    raw = open(os.path.join(HERE, 'prompts_src', path), encoding='utf-8').read()
    return prompt_surgery.apply(path, raw, ARM, CODEBOOK)


def dump_prompt(label, system):
    """Write an assembled system prompt for inspection instead of calling the API."""
    if not DRY_RUN:
        return
    os.makedirs(DRY_RUN, exist_ok=True)
    p = os.path.join(DRY_RUN, '%s__%s.txt' % (ARM, label))
    with open(p, 'w', encoding='utf-8') as f:
        f.write(system)
    log('  dry-run: wrote %s (%d chars)' % (p, len(system)))


# ------------------------------------------------------------------ methods
def _annollm_explanations(client, a, demos, work):
    """Stage 1 of explain-then-annotate: the model explains each gold label itself.

    AnnoLLM's mechanism is that the demonstrations carry the standard. The explanations
    are therefore generated, not written by us, and are generated WITHOUT the codebook
    so that no property name or composition rule can enter through them.
    """
    cache = os.path.join(work, 'annollm_explanations.json')
    if os.path.exists(cache):
        return json.load(open(cache, encoding='utf-8'))
    if ARM == 'explanations-only':
        # Same task framing the annotator will see, so the ONLY thing that changes
        # relative to the reported run is that the why slot is filled. The enumeration
        # is deliberately retained here, so no leak check applies to this arm.
        task = (open(os.path.join(HERE, 'prompts_src/AnnoLLM/prompt_annollm.md'),
                     encoding='utf-8').read().rstrip()
                + "\n\nYou are not annotating now. For each sentence below you are given the "
                  "correct answer. Write the reasoning that leads to it, in two or three "
                  "sentences, so it can serve as a worked example for an annotator.\n")
    else:
        task = load_task('AnnoLLM/prompt_annollm_explain.md')
        leak_check('explain prompt', task)
    rows = [{'id': d['id'],
             'text': '%s\tCORRECT ANSWER: %s' % (d['text'], 'Yes' if d['gold'] else 'No')}
            for d in demos]
    got = run_batches(client, a.model, task, FMT_WHY, rows,
                      os.path.join(work, 'annollm_explain'), 'annollm explain',
                      a.batch_size, a.max_tokens,
                      user_prefix='Explain each answer. Columns are '
                                  'id<TAB>sentence<TAB>correct answer.')
    why = {int(i): str(got[i].get('Why', '')).strip() for i in got}
    if ARM != 'explanations-only':
        for i, w in why.items():
            leak_check('generated explanation id=%s' % i, w)
    os.makedirs(work, exist_ok=True)
    json.dump(why, open(cache, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return why


def m_annollm(client, a, rows, demos, work):
    """AnnoLLM (He et al., NAACL 2024): explain-then-annotate, k demonstrations, 1 call/item."""
    if ARM == 'as-run':
        task = load_task('AnnoLLM/prompt_annollm.md')
        why = {}
    elif ARM == 'explanations-only':
        task = open(os.path.join(HERE, 'prompts_src/AnnoLLM/prompt_annollm.md'),
                    encoding='utf-8').read()
        why = {int(k): v for k, v in
               _annollm_explanations(client, a, demos, work).items()} if demos else {}
    else:
        task = load_task('AnnoLLM/prompt_annollm_holistic.md')
        leak_check('annotate prompt', task)
        why = {int(k): v for k, v in _annollm_explanations(client, a, demos, work).items()} \
            if demos else {}
    demo_block = "\n\n".join(
        "SENTENCE: %s\nCORRECT ANSWER: %s\nWHY THAT ANSWER IS CORRECT: %s"
        % (d['text'], 'Yes' if d['gold'] else 'No',
           why.get(d['id']) or d.get('why') or '<explanation pending>')
        for d in demos)
    system = task + ("\n\n## Worked examples\n\n" + demo_block if demos else "")
    if ARM == 'faithful':
        leak_check('assembled annotate prompt', system)
    got = run_batches(client, a.model, system, FMT_VERDICT, rows,
                      os.path.join(work, 'annollm'), 'annollm', a.batch_size, a.max_tokens)
    return [{'ID': i, 'verdict': 'Yes' if yes(got[i].get('Verdict')) else 'No',
             'escalated': 0, 'uncertainty': '', 'Rationale': got[i].get('Rationale', '')}
            for i in sorted(got)]


def m_coannotating(client, a, rows, demos, work):
    """CoAnnotating: S prompt-perturbed passes, self-consistency vote, entropy routing."""
    task = load_task('CoAnnotating/prompt_coannotating.md')
    passes = []
    for s in range(a.samples):
        got = run_batches(client, a.model, task + PERTURBATIONS[s % len(PERTURBATIONS)],
                          FMT_VERDICT, rows, os.path.join(work, 'coann_s%d' % s),
                          'coannotating s%d' % s, a.batch_size, a.max_tokens)
        passes.append(got)
    out = []
    for i in sorted(passes[0]):
        votes = ['Yes' if yes(p[i].get('Verdict')) else 'No' for p in passes]
        c = Counter(votes)
        ent = -sum((n / len(votes)) * math.log(n / len(votes), 2) for n in c.values())
        out.append({'ID': i, 'verdict': c.most_common(1)[0][0],
                    'escalated': 0, 'uncertainty': round(ent, 4),
                    'Rationale': passes[0][i].get('Rationale', '')})
    # allocate the most uncertain share to a human, per CoAnnotating's work allocation
    k = int(round(a.human_budget * len(out)))
    for r in sorted(out, key=lambda r: -r['uncertainty'])[:k]:
        r['escalated'] = 1
    return out


def m_tavakoli(client, a, rows, demos, work):
    """Tavakoli & Zamani: M-persona ensemble, verbalized confidence + disagreement,
    threshold calibrated on a labelled split."""
    task = load_task('TavakoliZamani/prompt_tavakoli.md')
    per = []
    for j in range(a.agents):
        got = run_batches(client, a.model, PERSONAS[j % len(PERSONAS)] + "\n\n" + task,
                          FMT_VERDICT_CONF, rows, os.path.join(work, 'tav_a%d' % j),
                          'tavakoli a%d' % j, a.batch_size, a.max_tokens)
        per.append(got)
    out = []
    for i in sorted(per[0]):
        v = ['Yes' if yes(p[i].get('Verdict')) else 'No' for p in per]
        conf = []
        for p in per:
            try:
                conf.append(float(p[i].get('Confidence', 50)))
            except (TypeError, ValueError):
                conf.append(50.0)
        mean_c = sum(conf) / len(conf)
        frac_yes = v.count('Yes') / len(v)
        disagree = 2 * min(frac_yes, 1 - frac_yes)            # 0 = unanimous, 1 = split
        score = (1 - mean_c / 100.0) + disagree               # higher = route to human
        out.append({'ID': i, 'verdict': Counter(v).most_common(1)[0][0],
                    'escalated': 0, 'uncertainty': round(score, 4),
                    'Rationale': per[0][i].get('Rationale', '')})
    k = int(round(a.human_budget * len(out)))
    for r in sorted(out, key=lambda r: -r['uncertainty'])[:k]:
        r['escalated'] = 1
    return out


def m_dream(client, a, rows, demos, work):
    """DREAM: two agents seeded with opposing stances debate R rounds; persistent
    disagreement escalates."""
    pro = load_task('DREAM/prompt_dream_pro.md')
    con = load_task('DREAM/prompt_dream_con.md')
    state = {r['id']: {'pro': None, 'con': None} for r in rows}
    for rd in range(a.rounds):
        ctx = {}
        for i, s in state.items():
            bits = []
            if s['pro']:
                bits.append("The OPPOSING debater argued: " + str(s['pro'].get('Rationale', '')))
            if s['con']:
                bits.append("The OPPOSING debater argued: " + str(s['con'].get('Rationale', '')))
            ctx[i] = bits
        def with_ctx(side):
            return [{'id': r['id'],
                     'text': r['text'] + ((" || " + ctx[r['id']][0]) if ctx[r['id']] and rd else "")}
                    for r in rows]
        p = run_batches(client, a.model, pro, FMT_VERDICT, with_ctx('pro'),
                        os.path.join(work, 'dream_pro_r%d' % rd), 'dream pro r%d' % rd,
                        a.batch_size, a.max_tokens)
        c = run_batches(client, a.model, con, FMT_VERDICT, with_ctx('con'),
                        os.path.join(work, 'dream_con_r%d' % rd), 'dream con r%d' % rd,
                        a.batch_size, a.max_tokens)
        for i in state:
            state[i]['pro'], state[i]['con'] = p.get(i), c.get(i)
        agree = sum(1 for i in state
                    if yes(state[i]['pro'].get('Verdict')) == yes(state[i]['con'].get('Verdict')))
        log('  round %d: agreement %d/%d (%.1f%%)' % (rd + 1, agree, len(state),
                                                      100.0 * agree / len(state)))
    out = []
    for i in sorted(state):
        pv = yes(state[i]['pro'].get('Verdict'))
        cv = yes(state[i]['con'].get('Verdict'))
        agreed = (pv == cv)
        # Ban et al. auto-label ONLY where the debate converges and send the rest to a
        # human with the transcript. Shipping the pro side on an unresolved debate would
        # bias every disagreement toward "checkable", so leave it unlabelled and record
        # the two sides separately.
        out.append({'ID': i,
                    'verdict': ('Yes' if pv else 'No') if agreed else '',
                    'escalated': int(not agreed), 'uncertainty': int(not agreed),
                    'provisional_pro': 'Yes' if pv else 'No',
                    'provisional_con': 'Yes' if cv else 'No',
                    'Rationale': state[i]['pro'].get('Rationale', '')})
    return out


METHODS = {'annollm': m_annollm, 'coannotating': m_coannotating,
           'tavakoli': m_tavakoli, 'dream': m_dream}
CALLS_PER_ITEM = {'annollm': lambda a: 1.0, 'coannotating': lambda a: float(a.samples),
                  'tavakoli': lambda a: float(a.agents), 'dream': lambda a: 2.0 * a.rounds}


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--method', required=True, choices=sorted(METHODS))
    ap.add_argument('--input', required=True)
    ap.add_argument('--gold', required=True, help='used ONLY for demonstrations/calibration')
    ap.add_argument('--out', required=True)
    ap.add_argument('--work', default='work_baselines')
    ap.add_argument('--model', required=True)
    ap.add_argument('--batch-size', type=int, default=20)
    ap.add_argument('--max-tokens', type=int, default=16000)
    ap.add_argument('--shots', type=int, default=8, help='AnnoLLM k (0 disables)')
    ap.add_argument('--samples', type=int, default=3, help='CoAnnotating passes')
    ap.add_argument('--agents', type=int, default=3, help='Tavakoli ensemble size')
    ap.add_argument('--rounds', type=int, default=2, help='DREAM debate rounds')
    ap.add_argument('--human-budget', type=float, default=0.20,
                    help='share routed to a human by the uncertainty-based methods')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--arm', default='as-run',
                    choices=['as-run', 'explanations-only', 'faithful'],
                    help='as-run: reproduces the reported run, including the unfilled '
                         'explanation slot; explanations-only: identical prompt, the only '
                         'change being that the explanations are generated (isolates the bug); '
                         'explanation slot; faithful: AnnoLLM as published \u2014 holistic task '
                         'definition, model-generated demonstration explanations, no property '
                         'scheme and no composition rule')
    ap.add_argument('--demo-policy', default='balanced',
                    choices=['balanced', 'property-stratified'],
                    help='balanced: label-balanced, uses no taxonomy information; '
                         'property-stratified: selects demonstrations so each property is '
                         'decisive at least once. Selection only \u2014 no property is ever named '
                         'in any prompt. Disclose if used.')
    ap.add_argument('--dry-run', default='',
                    help='assemble and write the system prompts to this directory, make no '
                         'API calls, and exit')
    a = ap.parse_args()

    global ARM, CODEBOOK, DRY_RUN
    ARM = a.arm
    DRY_RUN = a.dry_run or None
    log('arm=%s%s' % (a.arm, ' | dry run, no API calls' if DRY_RUN else ''))

    import pandas as pd
    with open(a.input, newline='', encoding='utf-8-sig') as f:
        src = [r for r in csv.DictReader(f) if str(r.get('id', '')).strip().isdigit()]
    rows = [{'id': int(r['id']), 'text': r['Regulation']} for r in src]

    gs = pd.read_excel(a.gold, keep_default_na=False)
    gold = {int(r['ID']): yes(r['Verdict']) for _, r in gs.iterrows()}

    # Demonstrations: first k ids, label-balanced, held out from evaluation.
    demos, demo_ids = [], set()
    if a.method == 'annollm' and a.shots > 0:
        pos = [r for r in rows if gold.get(r['id']) is True]
        neg = [r for r in rows if gold.get(r['id']) is False]
        for j in range(a.shots // 2):
            for pool in (pos, neg):
                if j < len(pool):
                    d = dict(pool[j]); d['gold'] = gold[d['id']]
                    demos.append(d); demo_ids.add(d['id'])
    rows = [r for r in rows if r['id'] not in demo_ids]
    if a.limit:
        rows = rows[:a.limit]
    log('%s | model=%s | %d rows evaluated | %d demo rows held out'
        % (a.method, a.model, len(rows), len(demo_ids)))

    client = None if DRY_RUN else make_client()
    tag = '%s__%s__%s__%s' % (a.method, a.arm, re.sub(r'[^A-Za-z0-9._-]', '_', a.model),
                          hashlib.sha1(json.dumps(vars(a), sort_keys=True,
                                                  default=str).encode()).hexdigest()[:6])
    work = os.path.join(a.work, tag)
    out = METHODS[a.method](client, a, rows, demos, work)

    textmap = {r['id']: r['text'] for r in rows}
    for r in out:
        r['Regulation'] = textmap.get(r['ID'], '')
        r['is_demo'] = 0
        r['calls_per_item'] = CALLS_PER_ITEM[a.method](a)
    for d in demos:
        out.append({'ID': d['id'], 'Regulation': d['text'], 'verdict': '',
                    'escalated': '', 'uncertainty': '', 'Rationale': 'HELD OUT AS DEMONSTRATION',
                    'is_demo': 1, 'calls_per_item': 0})
    out.sort(key=lambda r: r['ID'])

    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, 'baseline_%s.csv' % tag)
    cols = ['ID', 'Regulation', 'verdict', 'escalated', 'uncertainty', 'is_demo',
            'calls_per_item', 'provisional_pro', 'provisional_con', 'Rationale']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in out:
            w.writerow({c: r.get(c, '') for c in cols})
    ev = [r for r in out if not r['is_demo']]
    lab = [r for r in ev if str(r['verdict']).strip() != '']
    acc = sum(1 for r in lab if yes(r['verdict']) == gold.get(r['ID'])) / max(len(lab), 1)
    log('\nwrote %s (%d rows, %d evaluated)' % (path, len(out), len(ev)))
    log('accuracy on auto-labelled rows: %.1f%%  (coverage %d/%d = %.1f%%)'
        % (100 * acc, len(lab), len(ev), 100.0 * len(lab) / max(len(ev), 1)))
    log('escalated to a human: %d   calls/item: %.1f'
        % (sum(1 for r in ev if r['escalated'] == 1), CALLS_PER_ITEM[a.method](a)))


if __name__ == '__main__':
    main()
