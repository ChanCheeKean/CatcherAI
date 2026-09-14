#!/usr/bin/env bash
set -Eeuo pipefail

OBS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$OBS_ROOT/scripts/dev.sh" "$@"
