#!/usr/bin/env bash

set -x
set -e

MM_TOOLS="$(dirname "$(readlink "$BASH_SOURCE")")"
cd "$(dirname "$0")"
"$MM_TOOLS/mark.sh" missing *
"$MM_TOOLS/populate-assist.py" .
"$MM_TOOLS/grab.py" .
"$MM_TOOLS/mkreflection.py" .
