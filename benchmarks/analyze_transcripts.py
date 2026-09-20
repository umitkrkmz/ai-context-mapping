#!/usr/bin/env python3
"""Measure benchmark agents objectively from their Claude Code transcripts (JSONL).

Agent self-reports and single harness totals are hard to audit. A transcript records every tool
call and the token usage of every model turn, so this tool derives the numbers instead:

* tool calls by name, the files read, and the order in which they happened,
* token usage by type (input, output, cache write, cache read),
* a price-weighted cost, so that cheap cache reads and expensive output are not lumped together.

Cost weights (in units of one uncached input token) are typical published ratios and are only
an assumption: input 1.0, cache write 1.25, cache read 0.1, output 5.0. Change them with
--weights if your price list differs.

Usage:
    python benchmarks/analyze_transcripts.py --dir <transcript-dir> AGENT_ID [AGENT_ID ...]
    python benchmarks/analyze_transcripts.py --dir <dir> --json AGENT_ID

The transcript directory is the ``subagents`` folder of a Claude Code session, for example
~/.claude/projects/<project>/<session>/subagents, holding ``agent-<id>.jsonl`` files.

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_WEIGHTS = (1.0, 1.25, 0.1, 5.0)  # input, cache write, cache read, output


def load_agent(directory: str, agent_id: str, weights: Tuple[float, float, float, float]) -> Dict[str, Any]:
    """Parse one transcript and return its metrics."""
    path = os.path.join(directory, f"agent-{agent_id}.jsonl")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    per_message: Dict[str, Dict[str, int]] = {}
    calls: List[Tuple[str, str]] = []
    seen_calls = set()
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            stamp = record.get("timestamp")
            if stamp:
                first_ts = first_ts or stamp
                last_ts = stamp
            message = record.get("message") or {}
            if record.get("type") != "assistant":
                continue
            usage = message.get("usage") or {}
            # Streamed chunks repeat the message id; the last chunk holds the final counts.
            per_message[message.get("id") or record.get("uuid") or str(len(per_message))] = {
                "input": usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
                "cache_write": usage.get("cache_creation_input_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
            }
            content = message.get("content")
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id") not in seen_calls:
                    seen_calls.add(block.get("id"))
                    tool_input = block.get("input") or {}
                    target = tool_input.get("file_path") or tool_input.get("pattern") or tool_input.get("command") or ""
                    calls.append((str(block.get("name")), str(target).replace("\n", " ")[:120]))
    totals = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    for usage in per_message.values():
        for key in totals:
            totals[key] += usage[key]
    w_in, w_write, w_read, w_out = weights
    by_tool: Dict[str, int] = {}
    for name, _target in calls:
        by_tool[name] = by_tool.get(name, 0) + 1
    return {
        "agent": agent_id,
        "turns": len(per_message),
        "tool_calls": len(calls),
        "by_tool": by_tool,
        "files_read": [target for name, target in calls if name == "Read"],
        "sequence": calls,
        "usage": totals,
        "new_tokens": totals["input"] + totals["output"] + totals["cache_write"],
        "all_in_tokens": sum(totals.values()),
        "weighted_cost": round(
            w_in * totals["input"] + w_write * totals["cache_write"] + w_read * totals["cache_read"] + w_out * totals["output"]
        ),
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analyze_transcripts.py",
        description="Derive tool-call and token metrics for benchmark agents from Claude Code transcripts.",
    )
    parser.add_argument("agents", nargs="+", metavar="AGENT_ID", help="agent ids (the part after 'agent-' in the file name)")
    parser.add_argument("--dir", required=True, help="directory that holds agent-<id>.jsonl files")
    parser.add_argument(
        "--weights", nargs=4, type=float, metavar=("IN", "WRITE", "READ", "OUT"), default=DEFAULT_WEIGHTS,
        help="cost weights for input, cache write, cache read, and output tokens (default: 1 1.25 0.1 5)",
    )
    parser.add_argument("--sequence", action="store_true", help="also print every tool call in order")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    weights = tuple(args.weights)
    results = []
    for agent_id in args.agents:
        try:
            results.append(load_agent(args.dir, agent_id, weights))  # type: ignore[arg-type]
        except FileNotFoundError as exc:
            print(f"error: transcript not found: {exc}", file=sys.stderr)
            return 2
    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    for item in results:
        usage = item["usage"]
        print(f"agent {item['agent']}: {item['turns']} turns, {item['tool_calls']} tool calls {item['by_tool']}")
        print(
            f"  tokens: new {item['new_tokens']:,} (input {usage['input']:,}, output {usage['output']:,}, "
            f"cache write {usage['cache_write']:,}) | cache read {usage['cache_read']:,} | all-in {item['all_in_tokens']:,}"
        )
        print(f"  weighted cost: {item['weighted_cost']:,} input-token units")
        print(f"  files read ({len(item['files_read'])}): {', '.join(item['files_read'])}")
        if args.sequence:
            for index, (name, target) in enumerate(item["sequence"], start=1):
                print(f"    {index:>2}. {name:<10} {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
