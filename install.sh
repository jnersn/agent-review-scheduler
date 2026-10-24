#!/bin/sh
# Link review-next into ~/.local/bin (must be on PATH).
set -eu
here=$(cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$HOME/.local/bin"
ln -sfn "$here/review-next" "$HOME/.local/bin/review-next"
echo "linked ~/.local/bin/review-next -> $here/review-next"
