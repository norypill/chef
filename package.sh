#!/usr/bin/env bash
# package.sh — Build the chef.skill bundle from skills/chef/.
# Before zipping, syncs SKILL.md from intel/chef.md (single source of truth
# for Chef's persona) and validates the result.

set -e
cd "$(dirname "$0")"

SKILL_MD="skills/chef/SKILL.md"

# 1. Sync synced sections from intel/chef.md into SKILL.md
python3 scripts/sync-skill-from-intel.py

# 2. Validate SKILL.md frontmatter (must have opening/closing --- with name + description)
python3 - "$SKILL_MD" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
if not text.startswith("---\n"):
    print(f"ERROR: {path} missing opening '---' frontmatter delimiter", file=sys.stderr)
    sys.exit(1)
close = text.find("\n---\n", 4)
if close < 0:
    print(f"ERROR: {path} missing closing '---' frontmatter delimiter", file=sys.stderr)
    sys.exit(1)
fm_lines = text[4:close].splitlines()
if not any(l.startswith("name:") for l in fm_lines):
    print(f"ERROR: {path} frontmatter missing 'name:' field", file=sys.stderr)
    sys.exit(1)
if not any(l.startswith("description:") for l in fm_lines):
    print(f"ERROR: {path} frontmatter missing 'description:' field", file=sys.stderr)
    sys.exit(1)
PY

# 3. Validate SKILL.md is under 200 lines (keep the Cowork entry point concise)
LINES=$(wc -l < "$SKILL_MD" | tr -d ' ')
if [ "$LINES" -ge 200 ]; then
    echo "ERROR: $SKILL_MD is $LINES lines (>= 200). Trim intel/chef.md synced sections or restructure SKILL.md." >&2
    exit 1
fi

# 4. Build the bundle
rm -f chef.skill
(cd skills/chef && zip -r ../../chef.skill . -x "*.DS_Store" ".DS_Store")
echo "Built chef.skill from skills/chef/ ($LINES lines in SKILL.md) — drag into Cowork to install/update."
