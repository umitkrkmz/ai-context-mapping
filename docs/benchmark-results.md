# Benchmark Results: A/B Test on a Localized Regression

An empirical comparison of two agents fixing the same bug in the same project, one with the
framework and one without. **Read the summary before the tables: the result does not match the
simple story that a project map always saves tokens.**

Run date: 2026-09-20. One trial per arm. See [Threats to validity](#6-threats-to-validity)
before quoting any number.

## 1. Summary

| Question                                          | Result                                                      |
| ------------------------------------------------- | ----------------------------------------------------------- |
| Did both agents fix the bug correctly?            | **Yes.** Identical one-character fix; 8 of 8 hidden acceptance tests pass in both arms. |
| Did both write a real regression test?            | **Yes.** Both tests fail on the unfixed code and kill 100% of mutants. |
| Did the framework arm use fewer tokens?           | **No.** It used **34% more** (85,805 vs 63,951) on this small project. |
| Was the framework arm faster?                     | **No.** 66.1 s vs 48.4 s (**37% slower**).                  |
| Did the baseline agent read many irrelevant files?| **No.** It read 11 files, 5 of them outside the bug's path, about 1,600 tokens in total. |
| What did the framework arm buy?                   | Machine-checked evidence: mutation score, invariant check, map check, dependency audit. It did not buy a better fix. |
| Did the baseline arm miss anything?               | No. It also flagged the decoy module that the framework arm did not check. |

**Why.** The whole benchmark project is about 4,400 tokens. The framework's own instruction
files (`AGENTS.md`, `CLAUDE.md`, the map, `.agentignore`, invariants) are about 4,100 tokens, so
they are as large as the project they describe, and the framework arm also read the 7,000-token
source of the mutation guard. A map cannot save exploration that is already cheap. This is exactly the regime that
[`02-token-diet-calculator.md`](02-token-diet-calculator.md) predicts is unfavorable, and this
benchmark does **not** test the scaling claim (section 7).

## 2. Scenario

**Task given to both agents** (verbatim):

> Customers whose cart subtotal (after discounts) is exactly $50.00 are being charged shipping.
> Company policy says free shipping applies at $50.00 or more.
> Find the root cause, fix it, and add a regression test. Keep the change minimal.

**Project.** `benchmarks/shipdesk/`: a small checkout library with 17 modules, 10 test modules
plus a `conftest.py` (27 passing tests), a business-rules document, and a changelog. 31 files,
about 4,400 tokens. Money is integer cents.

**The planted bug.** `shipdesk/shipping.py::qualifies_for_free_shipping` compares with `>`
instead of `>=`. No existing test touches the boundary, so all 27 tests pass on the buggy code.

**Distractor.** `shipdesk/legacy_shipping.py::free_shipping` has the same `> 5000` pattern. It is
deprecated and, according to the changelog, used only by an old importer. Whether it should also
be fixed is a genuine question for the maintainers.

**Framework layer (Agent B only).** A hand-written `maps/project-map.md` with one row per file,
`invariants/negative-invariants.md` with two invariants (NI-101: `to_cents` keeps `Decimal`;
NI-102: money is integer cents, no `float()`), `AGENTS.md` and `CLAUDE.md` from the Python
template, and copies of `scripts/`, `mcp/`, `.agentignore`, and `tests/test_maps.py`. Before the
run, Agent B's project passed its own map check (51 of 51 paths), its invariant check, and 34
tests.

## 3. Method

| Item              | Agent A (baseline)                              | Agent B (context mapping)                            |
| ----------------- | ----------------------------------------------- | ---------------------------------------------------- |
| Project           | `benchmarks/shipdesk/`, unmodified              | Same, plus the framework layer above                 |
| Prompt            | Identical, including "follow any contributor instructions the project contains" | Identical |
| Agent             | Fresh general-purpose sub-agent, no prior context | Fresh general-purpose sub-agent, no prior context   |
| Model             | Same for both (session default; the harness does not record the exact ID) | Same |
| Order             | Run first, sequentially                         | Run second, sequentially (no contention)             |
| Isolation         | Separate directory; told not to read outside it | Same                                                 |

**Measurements**

| Metric                     | Source                                                         | Kind          |
| -------------------------- | -------------------------------------------------------------- | ------------- |
| Total tokens               | `subagent_tokens` reported by the agent harness                | Tool-reported (total, not split into input/output) |
| Tool calls, latency        | `tool_uses` and `duration_ms` reported by the harness          | Tool-reported |
| Files inspected            | The agent's own list of every file it opened                   | **Self-reported**; consistent with the tool-call counts |
| Read size                  | Character count of each listed file divided by 4               | Estimate      |
| Correctness                | 8 hidden acceptance tests (`benchmarks/acceptance_check.py`)   | Objective     |
| Mutation kill rate         | `scripts/mutation_guard.py` run by us on each agent's result   | Objective     |

Agent A has no mutation guard in its project, so it could not check its own tests that way. We
ran the same guard against both arms afterwards, with identical settings.

## 4. Results

### 4.1 Comparison matrix

| Metric                                  | Agent A (baseline) | Agent B (context mapping) | B relative to A |
| --------------------------------------- | -----------------: | ------------------------: | --------------: |
| **Total tokens** (harness-reported)     |             63,951 |                    85,805 |           +34%  |
| **Files inspected**                     |                 11 |                        12 |           +1    |
| - of which project files                |                 11 |                         6 |           -5    |
| - of which framework files              |                  0 |                         6 |           +6    |
| Estimated size of files read (tokens)   |             ~1,583 |                   ~12,291 |         ~7.8x   |
| - project files / framework files       |         1,583 / 0  |            1,149 / 11,142 |                 |
| **Tool calls**                          |                 17 |                        18 |           +1    |
| **Latency**                             |             48.4 s |                    66.1 s |           +37%  |
| Hidden acceptance tests passed          |                8/8 |                       8/8 |          equal  |
| Files changed                           | 3 (1 source, 2 tests) |  3 (1 source, 2 tests) |          equal  |
| Regression tests added                  |                  2 |                         3 |           +1    |
| **Mutation kill rate** (agent's new tests) |       4/4 (100%) |                  4/4 (100%) |          equal  |
| Mutation kill rate (whole suite)        |            4/4 (100%) |                4/4 (100%) |          equal  |

Files read by Agent B that were framework files: `CLAUDE.md`, `AGENTS.md` (the same content
twice, about 1,000 tokens each), `maps/project-map.md` (~1,035), `.agentignore` (~650),
`invariants/negative-invariants.md` (~365), and `scripts/mutation_guard.py` (~7,060). It read
`shipping.py`, `config.py`, `checkout.py`, the pricing policy, and the two relevant test files,
and went straight to them from the map.

### 4.2 Mutation testing

Target: `shipdesk/shipping.py::qualifies_for_free_shipping` (the fixed function). All runs use
`--max-mutants 0` (every mutant) and the whole `tests/` directory unless noted.

| Test suite scored                                        | v1.0.0 operators | v1.0.1 operators (adds `boundary`) |
| -------------------------------------------------------- | ---------------: | ---------------------------------: |
| Agent A: only its new regression tests                   |      3/3 (100%)  |                        4/4 (100%)  |
| Agent B: only its new regression tests                   |      3/3 (100%)  |                        4/4 (100%)  |
| Agent A: whole suite                                     |      3/3 (100%)  |                        4/4 (100%)  |
| Agent B: whole suite                                     |      3/3 (100%)  |                        4/4 (100%)  |
| **Control:** original suite, no regression test          |  **3/3 (100%)**  |                    **3/4 (75%)**   |

The control row is the reason this release adds `boundary` operators to `mutation_guard.py`.
The original suite contains no test at the boundary, yet the v1.0.0 operators score it 100%:
they only turn `>=` into `<`, which any test on a value far from 50.00 already detects. The
new operator turns `>=` into `>`, which is the bug itself; the original suite lets it survive
(`line 31: >= -> > (boundary shift)`), and both agents' new tests kill it. A mutation score is
only as sharp as its operators.

## 5. Interpretation

**What the data supports**

1. **Both arms produced a correct, minimal, well-tested fix.** Correctness and test strength
   were equal. On a small, well-documented project, an unconstrained agent is already good.
2. **The framework cost more than it saved here.** Agent B's reads were dominated by framework
   files (11,142 of 12,291 tokens read), not by project files (1,149 vs Agent A's 1,583).
   The map did its job: Agent B opened 6 project files, Agent A opened 11. But saving five small
   files (about 430 tokens) cannot repay ~11,000 tokens of framework reading.
3. **The extra tokens and time bought verification, not a better fix.** `AGENTS.md` Rule 2 sent
   Agent B through the mutation guard, the invariant check, the dependency audit, and the map
   check. That is the framework working as designed. On this task the verification confirmed a
   fix that was already right.
4. **Agent A was more thorough about the decoy.** It noticed the identical comparison in
   `legacy_shipping.py`, left it alone, and asked whether to fix it. Agent B relied on the map
   ("not used by checkout"), did not check it, and said so. Neither changed it, which is the
   safe choice.
5. **Rule 5 (do not invent project knowledge) showed a small tension.** Agent B inferred the
   `TEE-02` price from an existing test instead of opening `catalog.py`. It guarded the
   assumption with an assertion on the subtotal, but the price was not verified from a source.

**What the data does not support**

- The claim that the baseline agent reads "10+ irrelevant files" or bloats its context. It did
  not, because the project is small enough to navigate by name.
- The claim that the baseline test is weaker or mocked. It was not.
- Any claim about tokens saved at scale (section 7).

**Improvements this suggests (not implemented in v1.0.1)**

- Agents should not read a script's source to use it. `--help` costs a fraction of a 7,000-token
  file. Rule 1 could say so explicitly.
- Duplicating `CLAUDE.md` and `AGENTS.md` costs ~1,000 tokens when a tool loads both. Tools that
  read `AGENTS.md` natively should not also read `CLAUDE.md`.
- A map row for a deprecated module could say *"same threshold rule; do not fix without asking"*
  so that the framework arm surfaces the decoy question as reliably as the baseline did.

## 6. Threats to validity

- **One trial per arm.** LLM runs vary. A second run could move every number in the matrix.
  Treat differences under roughly 20% as noise; the token and latency gaps here are larger, but
  one run is still one run.
- **We wrote the fixture, the framework layer, and the acceptance tests.** We knew the bug. The
  hand-written map and invariants are a best case for Agent B.
- **The fixture is tiny** (about 4,400 tokens across 31 files). It is the worst case for a
  routing map, and the only regime tested.
- **Token accounting.** `subagent_tokens` is a harness total whose exact composition (cached
  input, repeated context, output) is not documented. Read it as a relative measure between the
  two runs, not an absolute cost.
- **Files inspected is self-reported.** The counts agree with the tool-call totals but were not
  independently audited.
- **Agents used file reads, not the MCP protocol.** Sub-agents did not have the MCP server
  configured, so Agent B read `maps/project-map.md` as a file. The server's tools return the
  same content.
- **Operators changed before the runs.** The `boundary` operators were added before either agent
  ran and were applied identically to both arms, but their addition is a choice we made after
  designing the scenario. Both operator sets are reported.
- **Sequential runs.** Latency was not distorted by contention, but API load may differ between
  the two minutes in which the runs happened.

## 7. What this benchmark does not test

The token-diet claim is about *scale*: a map lets an agent skip files, and the saving grows with
the repository while the map grows much more slowly. At 4,400 tokens the framework's
instructions (~4,100 tokens) are as large as the project. The break-even is a hypothesis to test, not
a result:

- run the same protocol on a fixture of 50,000 tokens or more, with the bug in one of many
  similar modules,
- repeat each arm at least five times and report medians and ranges,
- include a distractor whose wrong fix passes a weak test, so that test quality can differ,
- measure through the real MCP server.

Until then, the honest summary is: **the framework is not free, and on a small project it does
not pay for itself in tokens. Its value on small projects is verification evidence and
guardrails; its token value is a scaling claim that remains untested.**

## 8. Reproduce

Everything needed is in the repository: the buggy project (`benchmarks/shipdesk/`), the framework
layer (`benchmarks/shipdesk-overlay/`), and the scoring check (`benchmarks/acceptance_check.py`).

```bash
WORK=/tmp/bench && mkdir -p $WORK/A $WORK/B

# Agent A: the project only
cp -r benchmarks/shipdesk/. $WORK/A/

# Agent B: the project plus the framework layer
cp -r benchmarks/shipdesk/. $WORK/B/
cp -r benchmarks/shipdesk-overlay/. $WORK/B/
cp -r scripts mcp $WORK/B/
cp .agentignore $WORK/B/
cp templates/python/tests/test_maps.py $WORK/B/tests/

# Sanity check for B: map, invariants, tests
(cd $WORK/B && python scripts/init_mapping.py --check && python scripts/verify_invariants.py && python -m pytest -q)
```

Give each agent the prompt in section 2 in a fresh session, pointing it at its own directory, and
record tokens, tool calls, and latency from your agent tool. Then score each result:

```bash
# Correctness (must pass 8/8)
BENCH_PROJECT=$WORK/A python -m pytest benchmarks/acceptance_check.py -q

# Test strength, from inside the agent's directory
cd $WORK/A
python /path/to/repo/scripts/mutation_guard.py --test tests \
  --target shipdesk/shipping.py:qualifies_for_free_shipping \
  --max-mutants 0 --min-score 0
# v1.0.0 operator set for comparison:
#   --operators compare,arith,bool,not,if,return,const
```

`benchmarks/acceptance_check.py` is deliberately not named `test_*.py`, so a plain `pytest` run
from the repository root does not collect it (it fails on the unfixed fixture by design).
