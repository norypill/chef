#!/usr/bin/env bash
set -e
DEST="${CHEF_DIR:-$HOME/chef}"
if [ ! -d "$DEST/.git" ]; then
  git clone https://github.com/norypill/chef.git "$DEST"
else
  cd "$DEST" && git pull --ff-only
fi
cd "$DEST"
bash package.sh
open chef.skill
echo "Installed/updated chef skill from $DEST. Python tool is available at $DEST/src/ and $DEST/bin/ (separate install if needed)."
