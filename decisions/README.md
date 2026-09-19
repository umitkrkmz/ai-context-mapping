# Architecture Decisions (AI-Native ADRs)

This directory holds **machine-readable Architecture Decision Records**. A classic ADR is a
prose essay that an AI agent may skim, misread, or never open. These records are short YAML
files with fixed fields, so that agents can act on them and scripts can enforce them.

## File naming

```text
decisions/NNNN-short-kebab-title.yaml      e.g. 0001-no-database-file-store.yaml
```

`NNNN` is a zero-padded sequence number. It must match the numeric part of the `id` field
(`0001` and `ADR-0001`); `scripts/verify_invariants.py` checks this.

## Fields

| Field                 | Required | Type            | Meaning                                                              |
| --------------------- | -------- | --------------- | -------------------------------------------------------------------- |
| `id`                  | yes      | string          | Stable identifier, for example `ADR-0001`.                           |
| `decision`            | yes      | string          | The decision in one or two sentences, written as a fact.             |
| `reason`              | yes      | string          | Why this was chosen and which alternatives lose.                     |
| `forbidden_actions`   | yes      | list of strings | Concrete actions an agent must never take. Stop and ask instead.     |
| `title`               | no       | string          | Short human title.                                                   |
| `status`              | no       | string          | `proposed`, `accepted`, `deprecated`, or `superseded`.               |
| `date`                | no       | string          | ISO date, for example `2026-09-20`.                                  |
| `forbidden_imports`   | no       | list of strings | Python module names that scripts must never import; enforced by CI.  |
| `allowed_alternatives`| no       | list of strings | What an agent may do instead.                                        |
| `consequences`        | no       | string          | Known costs and the trigger for revisiting the decision.             |
| `enforcement`         | no       | list of strings | Scripts, tests, or rules that enforce the decision.                  |
| `supersedes`          | no       | string or null  | ID of the record this one replaces.                                  |

## YAML subset

The linter deliberately supports only a flat subset of YAML so it needs no third-party parser:
`key: scalar`, `key: [a, b]`, block scalars (`|` and `>`), and lists of scalars written as
`- item` lines. Nested mappings are not supported. Quote list items that contain `: `.

## How agents use these records

1. Before a task that touches storage, networking, dependencies, or module boundaries, read
   every record in this directory.
2. If the task requires an action listed in `forbidden_actions`, stop and ask the user
   (AGENTS.md Rule 3). Do not look for a clever workaround.
3. To change a decision, write a new record whose `supersedes` names the old one, and get the
   user's explicit approval before changing any code.

## How scripts use these records

`python scripts/verify_invariants.py` will:

- report records that are missing `id`, `decision`, `reason`, or `forbidden_actions`,
- turn every `forbidden_imports` list into a repository-wide import ban, including aliased,
  relative, and constant-string dynamic imports.

## Template

```yaml
id: ADR-0002
title: Short human-readable title
status: proposed
date: 2026-01-01
decision: >
  One or two sentences stating what is decided.
reason: >
  Why this option wins and which alternatives were rejected.
forbidden_actions:
  - A concrete action that must not be taken
forbidden_imports:
  - some_module
allowed_alternatives:
  - What to do instead
supersedes: null
```

## Index

| ID       | Title                                                 | Status   |
| -------- | ----------------------------------------------------- | -------- |
| ADR-0001 | Persist state in plain files; do not introduce a database | accepted |
