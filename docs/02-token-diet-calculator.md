# Token Diet Calculator

How much context, latency, and money does a project map save? This page gives the arithmetic,
a reference benchmark, a scaling model, and a script to measure your own repository.

> **Read this first.** Section 2 is a *model*: stated assumptions in, arithmetic out. Section 5
> is a *measurement* of this repository. Neither is a live trial of a particular agent, whose
> exploration strategy varies. Token counts use the common approximation **1 token ~ 4
> characters**, which is typically within roughly 15-25% of a real tokenizer for source code
> and prose. Use the script in section 7 with your own repository and your own model's price.

## 1. Headline

| Approach                              | Tokens read to orient and locate the code | Relative |
| ------------------------------------- | ----------------------------------------: | -------: |
| Naive: scan the whole repository      |                                    ~65,000 |     1.0x |
| Map-guided: read the map, then the file |                                    ~1,200 |   ~0.018x |
| **Reduction**                         |                        **98.2%** (54x fewer) |          |

The reduction stays above **95%** as long as the guided read costs at most **3,250 tokens**
(5% of 65,000).

## 2. The model

### Definitions

| Symbol | Meaning                                                              |
| ------ | -------------------------------------------------------------------- |
| `F`    | Number of readable (non-ignored) files in the repository            |
| `S`    | Average tokens per file                                              |
| `N`    | Whole-repository tokens: `N = F x S`                                 |
| `R`    | Number of rows in the project map (directories and groups included)  |
| `r`    | Average tokens per map row                                           |
| `M`    | Map tokens: `M = r x R` (plus a small header)                        |
| `k`    | Number of files the agent must open after consulting the map         |
| `G`    | Map-guided tokens: `G = M + k x S`                                   |

Naive cost is `N`. Guided cost is `G`. The saving is:

```text
reduction = 1 - G / N = 1 - (M + k x S) / N
```

### Reference scenario

| Assumption                                         | Value          |
| -------------------------------------------------- | -------------- |
| Repository size                                    | ~260 KB of text |
| Whole-repository tokens `N`                        | 65,000         |
| Files `F` / average tokens per file `S`            | ~120 / ~540    |
| Map rows `R` (large folders collapsed to `dir/**`) | ~45            |
| Tokens per compact map row `r`                     | ~15            |
| Map tokens `M`                                     | ~700           |
| Files opened after the map `k`                     | 1 (about 2 KB, ~500 tokens) |

### Breakdown

| Step                                           | Naive (tokens) | Map-guided (tokens) |
| ---------------------------------------------- | -------------: | ------------------: |
| Discover the layout                            |          ~1,000 (`ls -R`, `tree`) |   0 (in the map) |
| Find which file owns the behavior              |    ~64,000 (read or grep everything) |   ~700 (read the map) |
| Read the file to change                        |            (included above) |   ~500 (one targeted read) |
| **Total**                                      |     **~65,000** |         **~1,200** |
| Reduction                                      |                |     **98.2%**        |

With the MCP server the routing step can be even cheaper: `get_file_purpose("path")` returns one
row, roughly 60-150 tokens, instead of the whole map.

## 3. Cost

Cost per task is `tokens x price / 1,000,000`. Prices vary by model and change over time, so the
table uses three *illustrative* input prices; substitute your own.

| Input price (per 1M tokens) | Naive (65,000) | Guided (1,200) | Saved per task | Saved per 1,000 tasks |
| --------------------------: | -------------: | -------------: | -------------: | --------------------: |
| $1                          |        $0.0650 |        $0.0012 |        $0.0638 |                 $63.80 |
| $3                          |        $0.1950 |        $0.0036 |        $0.1914 |                $191.40 |
| $15                         |        $0.9750 |        $0.0180 |        $0.9570 |                $957.00 |

Two effects make the real picture more favorable to the map than the table suggests:

- **Repeated turns.** Tokens read early stay in the context and are re-sent on later turns.
  Prompt caching reduces the *price* of that repetition but not the window space it occupies or
  the attention it competes for.
- **Failed orientation.** A naive scan that misses the right file leads to a second scan.

## 4. Sensitivity: how much can the guided read grow?

With `N = 65,000`:

| Guided tokens `G` | Reduction | Comment                                          |
| ----------------: | --------: | ------------------------------------------------ |
|             1,200 |     98.2% | Reference scenario                               |
|             2,500 |     96.2% | Verbose map plus one larger file                 |
|             3,250 | **95.0%** | The break-even for the 95% claim                 |
|             5,000 |     92.3% | Several reads per task                           |
|            10,000 |     84.6% | A bloated map; group more directories            |

How many targeted reads fit inside the 95% budget? With `M = 700` and `S = 540`:

```text
k <= (3,250 - 700) / 540 = 4.7   ->   up to 4 targeted reads keep the reduction above 95%
```

| Files read after the map `k` | Guided tokens | Reduction |
| ---------------------------: | ------------: | --------: |
|                            1 |         1,240 |     98.1% |
|                            2 |         1,780 |     97.3% |
|                            3 |         2,320 |     96.4% |
|                            4 |         2,860 |     95.6% |
|                            5 |         3,400 |     94.8% |

## 5. Measured on this repository

Measured with the script in section 7 (`1 token ~ 4 characters`, files ignored by `.agentignore`
excluded). These are point-in-time figures; rerun the script after the repository changes.

| Quantity                                        |         Value |
| ----------------------------------------------- | ------------: |
| Readable files                                  |            43 |
| Whole-repository tokens `N`                     |        83,023 |
| Map rows / map tokens `M`                       |    67 / 2,324 |
| Median file / largest file (tokens)             | 1,081 / 10,638 |
| Guided cost: map + one median-size file         |         3,405 |
| **Reduction: map + one median-size file**       |     **95.9%** |
| Guided cost: map + the largest file             |        12,962 |
| Reduction: map + the largest file               |         84.4% |

What the numbers say:

- **The typical case clears 95%.** Orienting with the map and opening one ordinary file costs
  about 4% of the repository.
- **One huge file dominates the worst case.** The largest file here (`scripts/init_mapping.py`)
  is about 13% of the whole repository, so a session that must open it spends roughly ten times
  what a median-file session spends on the file itself. The map cannot shrink a file you
  genuinely need to read. Keep modules small, and consider
  splitting anything much larger than a few thousand tokens.
- **This map is verbose.** Every row has a full-sentence purpose, and the map carries a legend
  and a route table. Its 2,324 tokens are more than three times the ~700-token compact map of the
  reference scenario. A leaner map moves the typical case toward the 98% of section 2.

## 6. Scaling: the map grows slower than the repository

The whole repository grows with the number of files. The map grows with the number of
*documented groups*, because `init_mapping.py` collapses folders with many sibling files into a
single `dir/**` row and `.agentignore` removes generated files entirely.

Illustrative model (`S = 540`, `r = 22` tokens per row, `k = 2` targeted reads):

| Files `F` | Whole repo `N` | Map rows `R` | Map `M` | Guided `G = M + 2S` | Reduction | Fits a 200k window? |
| --------: | -------------: | -----------: | ------: | ------------------: | --------: | :-----------------: |
|       120 |          64.8k |           45 |    1.0k |                2.1k |     96.8% |         yes         |
|       500 |           270k |           90 |    2.0k |                3.1k |     98.9% |         **no**      |
|     2,000 |          1.08M |          180 |    4.0k |                5.0k |     99.5% |         **no**      |
|     8,000 |          4.32M |          300 |    6.6k |                7.7k |     99.8% |         **no**      |

The last column is the practical point: past a few hundred files a naive agent *cannot* read
everything. It must sample, and sampling is where context drift comes from. A map turns a
search problem into a lookup problem.

## 7. Measure your own repository

The quickest way is the built-in report (in Claude Code, run `/diet-check`):

```bash
python scripts/init_mapping.py --stats
```

It is read-only and prints the whole-repository size, the map size, the median and largest file,
the guided cost with and without the largest file, and the line count of every agent
instruction file. The snippet below does the same arithmetic in the open, so you can adapt it.

Run it from the repository root. It reuses the ignore logic of `scripts/init_mapping.py`, so the
count matches what the map covers, and it needs nothing beyond the standard library.

```bash
python - <<'EOF'
import statistics, sys
from pathlib import Path
sys.path.insert(0, "scripts")
import init_mapping as im

root = Path(".").resolve()
entries = im.scan_tree(root, im.IgnoreMatcher.from_root(root))
sizes = []
for entry in entries:
    if entry.is_dir:
        continue
    text = im.read_text_limited(root / entry.path)
    if text is not None:
        sizes.append(len(text) // 4)

map_text = (root / "maps" / "project-map.md").read_text(encoding="utf-8")
whole, map_tokens = sum(sizes), len(map_text) // 4
median, largest = int(statistics.median(sizes)), max(sizes)
for label, reads in (("map + 1 median file", median), ("map + largest file", largest)):
    guided = map_tokens + reads
    print(f"{label:<22} {guided:>7,} tokens  ->  {100 * (1 - guided / whole):.1f}% reduction")
print(f"files={len(sizes)}  whole repo={whole:,}  map={map_tokens:,}  median={median:,}  largest={largest:,}")
EOF
```

For exact counts, replace `len(text) // 4` with your model provider's token-counting tool.

## 8. Keeping the diet effective

1. **Group aggressively.** Lower `--collapse-threshold` so fixtures, migrations, and generated
   assets are one row each.
2. **Be terse.** One line per row; put long explanations in the file itself.
3. **Ignore generously.** Lockfiles, build output, logs, and bulk data belong in `.agentignore`.
4. **Route with the MCP server.** `get_file_purpose` answers about a specific file in a fraction
   of the map's cost.
5. **Re-measure after big changes.** If `M` passes ~3,000 tokens, the map has become a
   repository of its own; split the detail into per-directory notes and keep the top-level
   map as an index.
6. **Track it.** Record tokens per task before and after adopting the framework. That number,
   not this model, is the one to quote.

## 9. Bloated instruction files vs. two-tier navigation

Sections 1-8 compare *searching* with *looking up*. There is a second, quieter way to waste
context: putting the whole project into the always-loaded instruction file.

### The anti-pattern

A widely repeated rule of thumb in Claude Code practice is that **CLAUDE.md files exceeding
500 lines cause context bloat and missed instructions.** Treat 500 as a heuristic, not a
measured threshold, but the mechanism is real:

- **The cost is paid every session.** The file is loaded before the task is known, so it is
  billed against the window whether or not the task touches any of it.
- **Rules compete with prose.** Ten important rules buried in four hundred lines of
  architecture tour, file catalog, and history are the ones most likely to be skipped.
- **Prose rots silently.** A paragraph saying "the payment code lives in `billing/`" stays
  in the file after the directory is renamed, and the agent trusts it. Nothing fails.

### The alternative: short rules plus two-tier navigation

```text
  Always loaded      AGENTS.md / CLAUDE.md      the rules only: about 90 lines
        |
        v
  Tier 1  (on demand)   maps/project-map.md     one row per path; enforced by a test
        |                   or get_file_purpose   one row at a time through MCP
        v
  Tier 2  (targeted)    the one or two files    plus the invariant or decision the row names
                        the task actually needs
```

The rules file answers "how must I behave?". The map answers "where is it?". Targeted reading
answers "what does it say?". Each question is answered by the smallest artifact that can
answer it, and only when asked.

| Property                     | One bloated instruction file                 | Two-tier navigation                                   |
| ---------------------------- | -------------------------------------------- | ----------------------------------------------------- |
| Loaded at every session start | Everything: rules, tour, catalog, history    | Rules only (~1.2k tokens here)                        |
| Where file knowledge lives   | Prose paragraphs                             | Map rows, one per path                                |
| Stays true because           | Someone remembers to edit it                 | `tests/test_maps.py` fails when a row is missing/stale |
| Cost of looking up a file    | Already paid, whether needed or not          | Paid only when needed: ~2.3k (map) or ~0.1k (one row) |
| Depth available              | Whatever fits in 500 lines                   | Unlimited: invariants, decisions, docs, read on demand |
| Rule visibility              | Diluted by surrounding text                  | Rules are the whole file                              |

### The arithmetic

Measured on this repository: `AGENTS.md` is **97 lines and about 1,211 tokens**, roughly 12.5
tokens per line. Applying the same density to a file at the 500-line threshold:

| Always-loaded cost                                   |    Tokens | Versus a 500-line file |
| ---------------------------------------------------- | --------: | ---------------------: |
| Bloated `CLAUDE.md`, 500 lines x ~12.5               |    ~6,200 |                      - |
| Two-tier: rules file only                            |    ~1,210 |                   -81% |
| Two-tier: rules file + the whole map, when needed    |    ~3,530 |                   -43% |
| Two-tier: rules file + one `get_file_purpose` answer |    ~1,340 |                   -78% |

Even in the worst case, where the agent reads the entire map, two-tier navigation loads about
57% of what the bloated file loads on every session, and it loads the map only when the task
needs it. Over 100 sessions the fixed cost is roughly 620k tokens versus 121k for the rules
alone. The gap is larger still in the failure that matters most: with two-tier navigation, a
stale description fails a test instead of misleading the agent.

### Keep it that way

- Run `/diet-check` (or `python scripts/init_mapping.py --stats`). It lists the line and token
  count of `AGENTS.md`, `CLAUDE.md`, the Copilot instructions, and every Cursor rule, and flags
  any file over 500 lines.
- When a rules file grows, move the detail out: file descriptions go in the map, "never
  remove this guard" goes in `invariants/negative-invariants.md`, and rationale goes in
  `decisions/` or `docs/`. Leave a one-line pointer behind.
- Keep in the rules file only what must be true in every session.
