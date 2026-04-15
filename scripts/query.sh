#!/usr/bin/env bash
set -euo pipefail
QUERY=${1:-sample question}
make query q="$QUERY"
