#!/usr/bin/env bash
# Review probes intentionally return nonzero while the reported defects remain.
set -eu
cd "$(dirname "$0")/../.."
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export MPLBACKEND=Agg
proof_cache=$(mktemp -d)
trap 'rm -rf "$proof_cache"' EXIT
export MPLCONFIGDIR="$proof_cache/matplotlib"
export NUMBA_CACHE_DIR="$proof_cache/numba"
"${PROOF_PYTHON:-python}" -m pytest review/2026-09-17/test_bug_proofs.py -q -s --tb=short "$@"
