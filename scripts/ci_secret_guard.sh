#!/usr/bin/env bash
# Fail if secret-like paths appear in the git diff (PR / push range).
set -euo pipefail

RANGE="${1:-}"
if [[ -z "${RANGE}" ]]; then
  if [[ -n "${GITHUB_BASE_REF:-}" ]]; then
    git fetch origin "${GITHUB_BASE_REF}" --depth=1 >/dev/null 2>&1 || true
    RANGE="origin/${GITHUB_BASE_REF}...HEAD"
  else
    RANGE="HEAD~1...HEAD"
  fi
fi

echo "ci_secret_guard: scanning ${RANGE}"

# Paths that must never land in a commit/PR.
PATTERN='(\.env($|\.)|\.env\.|^\.pip_index$|\.pem$|\.key$|id_rsa|credentials\.json|secrets\.ya?ml)'

mapfile -t FILES < <(git diff --name-only --diff-filter=ACMRT "${RANGE}" 2>/dev/null || true)
if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "ci_secret_guard: no changed files"
  exit 0
fi

BAD=()
for f in "${FILES[@]}"; do
  base="$(basename "$f")"
  if [[ "$f" =~ $PATTERN || "$base" =~ $PATTERN ]]; then
    BAD+=("$f")
  fi
done

if [[ ${#BAD[@]} -gt 0 ]]; then
  echo "ci_secret_guard: blocked secret-like paths:" >&2
  printf '  - %s\n' "${BAD[@]}" >&2
  exit 1
fi

echo "ci_secret_guard: ok (${#FILES[@]} files)"
