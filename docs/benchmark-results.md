# Benchmark Results: Does the Framework Pay for Itself?

Two A/B experiments on the same bug, in the same project at two sizes: **4,400 tokens** (v1.0.1) and
**55,600 tokens** (v1.0.2). In each, one agent works with the framework and one without.

**The short version: the results do not support the claim that a project map saves tokens.** The
framework did not make agents fix the bug better or cheaper in either experiment. It did produce
machine-checked evidence, at a small cost. Read section 1 before quoting any number, and section 8 for
the limits of these experiments.

Run dates: 2026-09-20 (both). Experiment 1 has one trial per arm; experiment 2 has three.

## 1. Summary

| Question                                                        | Result |
| --------------------------------------------------------------- | ------ |
| Did every agent fix the bug correctly?                          | **Yes, 8 of 8.** The identical one-character fix; 8 of 8 hidden acceptance tests pass every time. |
| Were the regression tests strong?                               | **Yes, 8 of 8.** Every agent's tests kill 100% of mutants, including the `>=` to `>` boundary shift. |
| Did the framework arm cost fewer tokens?                        | **No.** Price-weighted cost was **+8%** at 4.4k tokens and a **+2% median** (+23% mean) at 55.6k tokens. |
| Did the baseline's cost grow with project size?                 | **No.** It was flat: 148.7k at 4.4k tokens, **150.9k median at 55.6k** (12.7x larger). |
| Did the baseline agent scan the whole repository?               | **No.** All 8 agents listed the tree, then grepped (experiment 2) or opened files by name (experiment 1). None read more than 12 files. |
| Did the framework agents follow Rule 1 (read the map first)?    | **No, 0 of 3.** All three grepped first; two read the map afterwards; one never opened it. |
| What did the framework arm buy?                                 | Mutation-verified tests, invariant, dependency, and map checks. It did not buy a better fix. |
| What did it cost?                                               | About 7,000-12,000 extra tokens of instruction and script reading per task, and one hung command. |

**What this means for the earlier claims.** The token-diet model in
[`02-token-diet-calculator.md`](02-token-diet-calculator.md) compares a map-guided read against an agent
that reads the whole repository. No agent here did that. Agents navigate with `Glob` and `grep`, whose
cost depends on how many files *match*, not on how large the repository is. The model is a worst case
for an unguided agent, not a prediction, and this benchmark found no savings from the map at 55,600
tokens.

## 2. What we measured, and how

**Task given to every agent** (verbatim):

> Customers whose cart subtotal (after discounts) is exactly $50.00 are being charged shipping.
> Company policy says free shipping applies at $50.00 or more.
> Find the root cause, fix it, and add a regression test. Keep the change minimal.

**The planted bug.** `shipdesk/shipping.py::qualifies_for_free_shipping` compares with `>` instead of
`>=`. No existing test touches the boundary, so every existing test passes on the buggy code.

**Arms.** Agent A gets the project only. Agent B gets the same project plus a framework layer: `AGENTS.md`
and `CLAUDE.md` (the Python template with all five rules), a hand-written `maps/project-map.md`,
`invariants/negative-invariants.md`, copies of `scripts/` and `mcp/`, `.agentignore`, and
`tests/test_maps.py`. Before each run, B's project passed its own map check, invariant check, and tests.
Prompts were identical, including "follow any contributor instructions the project itself contains".
Each trial used a fresh sub-agent with no prior context, its own copy of the project, and the same
model. Runs were sequential.

**Measurements.** Everything below is derived from the agents' **transcripts** with
[`benchmarks/analyze_transcripts.py`](../benchmarks/analyze_transcripts.py), not from self-reports.

| Metric                      | Definition |
| --------------------------- | ---------- |
| **Weighted cost** (primary) | `input x 1 + cache write x 1.25 + cache read x 0.1 + output x 5`, in input-token units. The weights are typical published price ratios and are an assumption. The primary metric was fixed before the large-scale runs. |
| New tokens                  | Input + output + cache-write tokens: text the model saw or wrote for the first time. |
| Cache reads                 | Context re-read on each turn. Cheap per token, large in volume. |
| All-in tokens               | New tokens + cache reads. |
| Harness total               | The `subagent_tokens` figure the agent tool prints. Its composition is undocumented and it **could not be reproduced** from the transcripts. Reported for reference only. |
| Files read, tool calls      | Counted from the transcript. `Read` calls only; a `cat` inside a shell command is not counted. |
| Correctness                 | 8 hidden acceptance tests (`benchmarks/acceptance_check.py`). |
| Mutation kill rate          | `scripts/mutation_guard.py`, all mutants, whole test suite, run by us after each trial. |

## 3. Experiment 1: small project (4,400 tokens, 31 files), one trial per arm

`benchmarks/shipdesk/`: 17 modules, 10 test modules plus a `conftest.py` (27 passing tests), a
pricing-policy document, and a changelog. A decoy, `legacy_shipping.py`, repeats the `> 5000` pattern.

| Metric (transcript-derived)             | Agent A |  Agent B | B vs A |
| --------------------------------------- | ------: | -------: | -----: |
| **Weighted cost** (primary)             | 148,721 |  160,450 |    +8% |
| New tokens                              |  67,722 |   53,674 |   -21% |
| Cache reads                             | 465,197 |  727,565 |   +56% |
| All-in tokens                           | 532,919 |  781,239 |   +47% |
| *Harness total (not reproducible)*      |  63,951 |   85,805 |   +34% |
| Tool calls                              |      17 |       18 |     +1 |
| Latency                                 |  48.4 s |   66.1 s |   +37% |
| Files read (`Read` tool)                |      11 |       12 |     +1 |
| Project / framework tokens read         | 1,583 / 0 | 1,149 / 11,142 |    |
| Acceptance tests / mutation kill rate   | 8/8, 4/4 | 8/8, 4/4 |  equal |

**Mutation testing, by operator set** (target `qualifies_for_free_shipping`, whole suite):

| Suite scored                                        | v1.0.0 operators | v1.0.1 operators (adds `boundary`) |
| --------------------------------------------------- | ---------------: | ---------------------------------: |
| Agent A's tests                                     |      3/3 (100%)  |                        4/4 (100%)  |
| Agent B's tests                                     |      3/3 (100%)  |                        4/4 (100%)  |
| **Control:** original suite, no regression test     |  **3/3 (100%)**  |                    **3/4 (75%)**   |

The control row is why v1.0.1 added `boundary` operators to `mutation_guard.py`. The original suite has no
test at the boundary, yet the v1.0.0 operators scored it 100%: they only turn `>=` into `<`, which any
test far from 50.00 already catches. The new operator turns `>=` into `>`, which is the bug itself.

**Correction to v1.0.1.** The first version of this document led with the harness total (+34% tokens).
The transcripts show that figure was the least informative one available: depending on the accounting,
Agent B used 21% *fewer* new tokens, 8% more weighted cost, or 47% more all-in tokens. The agents'
self-reported file lists were checked against the transcripts and were **exactly right**.

## 4. Experiment 2: large project (55,600 tokens, 224 files), three trials per arm

`benchmarks/shipdesk-large/` is the small project with everything around it grown: 8 carrier adapters,
10 tier tables, 6 exporters, 8 region helpers, notification templates, repositories, analytics, services,
tax tables for 27 EU states and 50 US states, currency formatting, delivery-zone and holiday tables,
integrations, an audit log, search, seed data and three sample data sets, six ADRs, and 32 more
documents. **271 tests pass on the buggy code.** The bug, its function, and the bug report are
identical to experiment 1, so the only variable is scale.

It is built to have realistic decoys. A case-insensitive search for `free shipping` matches 18 files. A
promotion banner (`services/promotions.py`) and the free-shipping analytics also deal with the threshold.
Five tier tables and the audit retention rule deliberately use a **strict** `>` that is correct under
their documented business rules; five other tier tables use `>=`. `legacy_shipping.py` repeats the bug and is frozen by ADR 0005.

Agent B's map has 147 rows and ~3,700 tokens (the framework's own `--stats` warns that this exceeds its
3,000-token guidance). Trials ran in the order A1, B1, B2, A2, A3, B3.

### 4.1 Per-trial results

| Trial | Weighted cost | New tokens | Cache reads | Harness total | Latency | Tool calls | Files read | Project / framework tokens read | Map read? |
| ----- | ------------: | ---------: | ----------: | ------------: | ------: | ---------: | ---------: | ------------------------------: | --------- |
| A1    |       158,703 |     80,615 |     401,625 |        76,988 |  45.5 s |         19 |         11 |                     1,692 / 0   | n/a |
| A2    |       136,997 |     49,784 |     584,027 |        82,636 |  44.0 s |         18 |         12 |                     1,818 / 0   | n/a |
| A3    |       150,887 |     50,166 |     683,547 |        81,993 |  57.2 s |         20 |         10 |                     1,890 / 0   | n/a |
| B1    |       149,836 |     55,544 |     632,318 |        88,391 |  47.5 s |         17 |         10 |                 1,127 / 6,943    | after a grep |
| B2    |   **245,991** |     73,205 |   1,229,508 |       102,629 | **219.7 s** |     24 |         10 |                1,302 / 11,981    | after a grep |
| B3    |       154,071 |     59,045 |     625,997 |        91,745 |  52.8 s |         17 |         11 |                1,244 / 10,314    | **never** |

B2 lost about three minutes to a hung shell command (a malformed heredoc that it then had to kill) and
re-read a growing context on every turn. It is a real event and stays in the data.

### 4.2 Aggregates

| Metric                                | Agent A: median (range)     | Agent B: median (range)       | B/A median | B/A mean |
| ------------------------------------- | --------------------------: | ----------------------------: | ---------: | -------: |
| **Weighted cost** (primary)           | 150,887 (136,997-158,703)   | 154,071 (149,836-245,991)     |  **1.02x** |    1.23x |
| New tokens                            |  50,166 (49,784-80,615)     |  59,045 (55,544-73,205)       |      1.18x |    1.04x |
| All-in tokens                         | 633,811 (482,240-733,713)   | 687,862 (685,042-1,302,713)   |      1.09x |    1.45x |
| *Harness total*                       |  81,993 (76,988-82,636)     |  91,745 (88,391-102,629)      |      1.12x |    1.17x |
| Latency                               |  45.5 s (44.0-57.2)         |  52.8 s (47.5-219.7)          |      1.16x |    2.18x |
| Tool calls                            |  19 (18-20)                 |  17 (17-24)                   |      0.89x |    1.02x |
| Files read                            |  11 (10-12)                 |  10 (10-11)                   |          - |        - |
| Project tokens read                   |  1,818 (1,692-1,890)        |  1,244 (1,127-1,302)          |          - |        - |

The median cost difference (+2%) is well inside the spread within each arm. With three trials per arm,
it should be read as **no measurable difference**; the mean is inflated by one hung command.

### 4.3 Quality

| Measure                                      | Agent A (3 trials) | Agent B (3 trials) |
| -------------------------------------------- | -----------------: | -----------------: |
| Identical one-character fix                  |                3/3 |                3/3 |
| Hidden acceptance tests passed               |          8/8 (x3)  |          8/8 (x3)  |
| Files changed outside the fix and its tests  |                  0 |                  0 |
| Mutation kill rate of the agent's suite      |          4/4 (x3)  |          4/4 (x3)  |
| Ran the mutation guard themselves            |    n/a (not provided) |              3/3 |
| Opened `legacy_shipping.py` and reported its sibling bug | 1/3    |                0/3 |
| Touched `legacy_shipping.py`                 |                0/3 |                0/3 |

**Control:** the original suite (no regression test) scores 3/4 (75%) against the fixed function; the
survivor is `line 31: >= -> > (boundary shift)`. The boundary operator added in v1.0.1 still tells a
boundary test from a non-boundary test at 55,600 tokens.

### 4.4 What the transcripts show about behavior

- **Every agent, in both arms, began with `Glob **/*` (the whole file list, about 1,700 tokens) and a
  targeted `grep`.** No agent read more than 12 files. The baseline read 10-12 files, about 1,700-1,900
  tokens: **3.0-3.4% of the project**, with no map.
- **Rule 1 was not followed.** B1 and B2 grepped, then read the map. B3 never opened it; the map appeared
  only in a grep result. The agents' self-reports said so honestly. Rule 1 is advisory, and here it was
  overridden by the reflex to search first.
- **Framework reading was pure overhead here.** B read `AGENTS.md` and `CLAUDE.md` (identical, about
  1,000 tokens each), the map (~3,700), `.agentignore` (~700), the invariants (~560), and, in B2 and B3,
  the 7,100-token source of `mutation_guard.py`: 6,900-12,000 tokens per trial against 1,100-1,300 tokens
  of project files.
- **The framework agents skipped the sibling bug.** Trusting the frozen-module invariant, none opened
  `legacy_shipping.py`. One baseline agent opened it and told the user it has the same off-by-one.
  That is useful information the framework arm did not surface.
- **Cost is dominated by the agent loop, not by project content.** About 45-76k tokens are written to
  the cache over a run (mostly the system prompt, tool definitions, and the files read), and every turn
  re-reads the growing context. That is why 12.7x more project barely moved the total.

## 5. Scale: 4,400 to 55,600 tokens

| Quantity (weighted cost unless noted)      | Small (n=1 each) | Large (n=3 each, median) | Change |
| ------------------------------------------ | ---------------: | -----------------------: | -----: |
| Project size (tokens / files)              |      4,369 / 31  |             55,600 / 224 | 12.7x  |
| **Agent A, weighted cost**                 |          148,721 |                  150,887 |   +1.5% |
| **Agent B, weighted cost**                 |          160,450 |                  154,071 |   -4.0% |
| B relative to A                            |            +8%   |                     +2%  |  -6 points |
| Agent A: files read / project tokens read  |     11 / 1,583   |             11 / 1,818   | flat |
| Agent B: framework tokens read             |          11,142  |                  10,314  | flat |

A 12.7x larger project moved neither arm's cost. The gap between arms shrank by six points, which is
inside the noise. **There is no sign that the map's value grows with project size over this range.**

## 6. Interpretation

**Supported by the data**

1. **Both approaches reach the same correct, well-tested fix**, at both scales, in 8 of 8 trials.
2. **A grep-capable agent does not pay for repository size.** Its navigation cost follows the number of
   matches for a distinctive symptom (`free shipping`, `qualifies_for_free_shipping`), and that stayed
   small even with 20+ matching files.
3. **The framework's fixed overhead is real and roughly constant** (7,000-12,000 tokens of reading per
   trial), so it cannot pay for itself on a task the baseline already does in ~1,800 tokens of reading.
4. **Advisory rules are followed partially.** Rule 1 was violated in 3 of 3 framework trials. The
   scripts (Rules 2 and 4, and invariants) were run in 3 of 3, presumably because `AGENTS.md` names the
   command to run.

**Not supported, and now withdrawn or qualified**

- *"A map cuts orientation cost by 95% or more."* That compares against a whole-repository read that no
  agent performed. It remains a valid statement about a worst-case agent, not about the agents tested.
- *"Token waste is a major cost of unguided agents."* Not observed at 55,600 tokens with a greppable
  symptom.
- *"The map's advantage grows with repository size."* Not observed between 4,400 and 55,600 tokens.

**What the framework did show value for**

- **Evidence, not outcomes.** B's tests were verified by an independent mutation run; A's equally strong
  tests were unverified until we ran the guard ourselves.
- **Guard rails that were not needed here.** The invariants (NI-101 to NI-104) protected against
  plausible wrong fixes such as unifying tier operators or editing the frozen module. No agent tried,
  so we cannot say whether they would have.

## 7. What would change the picture (untested)

- **A symptom that cannot be grepped.** "Wrong total for some German orders" has no distinctive string.
  There the baseline must explore, and a map might route it. This benchmark's bug was chosen to be
  typical, and it is greppable.
- **Repositories 10x to 100x larger**, where even matches are numerous and `Glob **/*` itself is
  expensive (here: ~1,700 tokens; at 5,000 files it would be tens of thousands).
- **Enforcing Rule 1 rather than requesting it.** A Claude Code `PreToolUse` hook could deny `Glob` and
  `Grep` until the map has been read. That is consistent with the framework's own design principle
  (advisory rules need a script behind them), and it is untested.
- **Trimming the overhead:** an agent should run a script with `--help`, not read its source;
  `CLAUDE.md` and `AGENTS.md` should not both be read; the map should stay under ~3,000 tokens.
- **More trials and more bug types.** Three trials per arm and one bug do not support statistics.

## 8. Threats to validity

- **Three trials per arm (one in experiment 1).** LLM runs vary; B2 shows how far one run can move a
  mean. Differences under about 20% are noise here.
- **One bug, one kind (an off-by-one), one language, one model.** The model is the session default; the
  harness does not record its exact ID.
- **We wrote everything:** the fixtures, the map, the invariants, the decoys, and the acceptance tests.
  The framework layer is a best case. The large fixture is partly template-generated, so many modules
  are structurally similar, which may make grep results easier to read than in real code.
- **Cost weights are assumptions.** With other prices, the ranking of B and A by weighted cost could
  change, though the conclusion "no large difference" is stable across the four accountings we report.
- **`Read` calls only.** A `cat` inside a shell command is not counted as a file read (A2 read two small
  files that way; B2 read `CLAUDE.md`, `AGENTS.md`, and the README).
- **Sequential runs at different moments.** API load may differ between trials, which affects latency.
- **Agents used file reads, not the MCP protocol.** The server returns the same content.
- **The boundary operators were added before the runs** and applied identically to all arms (see the
  operator comparison in section 3).

## 9. Reproduce

Everything is in the repository. The fixtures (`benchmarks/shipdesk/`, `benchmarks/shipdesk-large/`) are
listed in `.agentignore` because they contain deliberate bugs; `benchmarks/conftest.py` keeps `pytest`
from collecting them.

```bash
WORK=/tmp/bench && mkdir -p $WORK/A $WORK/B

# Agent A: the project only (use benchmarks/shipdesk for the small experiment)
cp -r benchmarks/shipdesk-large/. $WORK/A/

# Agent B: the project plus the framework layer
cp -r benchmarks/shipdesk-large/. $WORK/B/
cp -r benchmarks/shipdesk-large-overlay/. $WORK/B/     # or benchmarks/shipdesk-overlay for the small one
cp -r scripts mcp $WORK/B/
cp .agentignore $WORK/B/
cp templates/python/tests/test_maps.py $WORK/B/tests/

# Sanity check for B: map, invariants, tests
(cd $WORK/B && python scripts/init_mapping.py --check && python scripts/verify_invariants.py && python -m pytest -q)
```

Give each agent the prompt from section 2 in a fresh session pointed at its own directory. Then:

```bash
# Correctness (8/8 expected)
BENCH_PROJECT=$WORK/A python -m pytest benchmarks/acceptance_check.py -q

# Test strength, from inside the agent's directory
(cd $WORK/A && python /path/to/repo/scripts/mutation_guard.py --test tests \
  --target shipdesk/shipping.py:qualifies_for_free_shipping --max-mutants 0 --min-score 0)

# Tokens, tool calls, and files read, from the transcripts
python benchmarks/analyze_transcripts.py --dir <session>/subagents --sequence AGENT_ID [AGENT_ID ...]
```

`benchmarks/acceptance_check.py` is deliberately not named `test_*.py`, so it is not collected; it fails
on the unfixed fixtures by design.
