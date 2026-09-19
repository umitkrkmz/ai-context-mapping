#!/usr/bin/env sh
# Install the AI-guardrails git pre-commit hook.
#
# The installed hook runs, in order:
#   1. scripts/verify_invariants.py        architectural invariants (AST checks)
#   2. scripts/check_dependency_budget.py  dependency allow-list and ceiling
#   3. tests/test_maps.py                  the project map covers every file
#
# Usage: sh scripts/install_hooks.sh [--force] [--scripts-dir DIR] [--uninstall]

set -eu

MARKER="# ai-context-mapping: managed pre-commit hook"
FORCE=0
UNINSTALL=0
SCRIPTS_DIR="scripts"

usage() {
    cat <<'EOF'
Install the AI-guardrails git pre-commit hook.

Usage: sh scripts/install_hooks.sh [options]

Options:
  --force              Replace an existing pre-commit hook (a backup is saved as pre-commit.bak)
  --scripts-dir DIR    Directory that holds the guardrail scripts (default: scripts)
  --uninstall          Remove a hook installed by this script
  -h, --help           Show this help

Bypass the hook once with:                   SKIP_AI_GUARDRAILS=1 git commit ...
Make a missing pytest a hard failure with:   AI_GUARDRAILS_STRICT=1 git commit ...
EOF
}

say() { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
    case "$1" in
        --force) FORCE=1 ;;
        --uninstall) UNINSTALL=1 ;;
        --scripts-dir)
            [ $# -ge 2 ] || fail "--scripts-dir needs a value"
            SCRIPTS_DIR="$2"
            shift
            ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; fail "unknown option: $1" ;;
    esac
    shift
done

command -v git >/dev/null 2>&1 || fail "git is not installed or not on PATH"
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || fail "run this script inside a git repository"
HOOKS_DIR=$(git rev-parse --git-path hooks)
case "$HOOKS_DIR" in
    /*|[A-Za-z]:*) ;;
    *) HOOKS_DIR="$REPO_ROOT/$HOOKS_DIR" ;;
esac
HOOK_PATH="$HOOKS_DIR/pre-commit"

is_managed() { [ -f "$1" ] && grep -q "$MARKER" "$1" 2>/dev/null; }

if [ "$UNINSTALL" -eq 1 ]; then
    if is_managed "$HOOK_PATH"; then
        rm -f "$HOOK_PATH"
        say "Removed $HOOK_PATH"
        if [ -f "$HOOKS_DIR/pre-commit.bak" ]; then
            say "A previous hook is saved at $HOOKS_DIR/pre-commit.bak; restore it manually if you want it back."
        fi
    else
        say "No managed pre-commit hook found at $HOOK_PATH; nothing to do."
    fi
    exit 0
fi

[ -f "$REPO_ROOT/$SCRIPTS_DIR/verify_invariants.py" ] || fail "missing $SCRIPTS_DIR/verify_invariants.py (use --scripts-dir if your scripts live elsewhere)"

mkdir -p "$HOOKS_DIR"
if [ -e "$HOOK_PATH" ]; then
    if is_managed "$HOOK_PATH"; then
        :
    elif [ "$FORCE" -eq 1 ]; then
        cp "$HOOK_PATH" "$HOOKS_DIR/pre-commit.bak"
        say "Saved the existing hook as $HOOKS_DIR/pre-commit.bak"
    else
        fail "a pre-commit hook already exists at $HOOK_PATH. Re-run with --force to replace it (a backup is kept)."
    fi
fi

cat > "$HOOK_PATH" <<EOF
#!/usr/bin/env sh
$MARKER
# Installed by scripts/install_hooks.sh. Bypass once with SKIP_AI_GUARDRAILS=1.

if [ "\${SKIP_AI_GUARDRAILS:-0}" = "1" ]; then
    echo "[ai-guardrails] skipped (SKIP_AI_GUARDRAILS=1)"
    exit 0
fi

ROOT=\$(git rev-parse --show-toplevel) || exit 1
cd "\$ROOT" || exit 1

if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[ai-guardrails] Python 3.9+ is required to run the guardrails." >&2
    exit 1
fi

STATUS=0
run_step() {
    label=\$1
    shift
    if "\$@"; then
        echo "[ai-guardrails] ok:   \$label"
    else
        echo "[ai-guardrails] FAIL: \$label" >&2
        STATUS=1
    fi
}

run_step "architectural invariants" "\$PY" "$SCRIPTS_DIR/verify_invariants.py" --no-color
if [ -f "$SCRIPTS_DIR/check_dependency_budget.py" ]; then
    run_step "dependency budget" "\$PY" "$SCRIPTS_DIR/check_dependency_budget.py" --no-color
fi
if [ -f tests/test_maps.py ]; then
    if "\$PY" -c "import pytest" >/dev/null 2>&1; then
        run_step "project map coverage" "\$PY" -m pytest -q tests/test_maps.py
    elif [ "\${AI_GUARDRAILS_STRICT:-0}" = "1" ]; then
        echo "[ai-guardrails] FAIL: pytest is not installed (AI_GUARDRAILS_STRICT=1)" >&2
        STATUS=1
    else
        echo "[ai-guardrails] warn: pytest is not installed; skipping the map coverage test" >&2
    fi
fi

if [ "\$STATUS" -ne 0 ]; then
    echo "[ai-guardrails] Commit blocked. Fix the failures above, or bypass once with SKIP_AI_GUARDRAILS=1." >&2
fi
exit \$STATUS
EOF
chmod +x "$HOOK_PATH"

say "Installed $HOOK_PATH"
say "Guardrails now run on every commit. Bypass once with: SKIP_AI_GUARDRAILS=1 git commit ..."
