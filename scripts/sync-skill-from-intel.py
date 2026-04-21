#!/usr/bin/env python3
"""
Sync designated sections of skills/chef/SKILL.md from intel/chef.md.

Called by package.sh before bundling so the Cowork .skill can't drift from the
canonical persona doctrine. Single source of truth is intel/chef.md — edit
there, rebuild, SKILL.md regenerates automatically.

Synced sections (matched by H2 heading, "The " prefix tolerated):
  - Core Principle
  - Heavy Lifting Standard
  - Boards Chef Actively Manages
  - Protocol Boards (Reference Only)

SKILL.md's H2 heading line is preserved as-is; only the body is replaced, so
section naming in the skill can differ from intel if needed (e.g. intel's
"The Heavy Lifting Standard" maps to skill's "Heavy Lifting Standard").
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INTEL = REPO_ROOT / "intel" / "chef.md"
SKILL = REPO_ROOT / "skills" / "chef" / "SKILL.md"

SYNCED_SECTIONS = [
    "Core Principle",
    "Heavy Lifting Standard",
    "Boards Chef Actively Manages",
    "Protocol Boards (Reference Only)",
]

H2_RE = re.compile(r"^## (.+?)\s*$")


def canonical(title):
    if title is None:
        return None
    t = title.strip()
    for s in SYNCED_SECTIONS:
        if t == s or t == f"The {s}":
            return s
    return None


def parse_sections(text):
    """Return list of (title, block). Block includes the H2 line plus body up
    to (but not including) the next H2. Preamble has title=None."""
    sections = []
    title = None
    buf = []
    for line in text.splitlines(keepends=True):
        m = H2_RE.match(line)
        if m:
            if buf:
                sections.append((title, "".join(buf)))
            title = m.group(1).strip()
            buf = [line]
        else:
            buf.append(line)
    if buf:
        sections.append((title, "".join(buf)))
    return sections


def main():
    intel_sections = parse_sections(INTEL.read_text())
    skill_sections = parse_sections(SKILL.read_text())

    intel_by_canon = {}
    for title, block in intel_sections:
        c = canonical(title)
        if c:
            intel_by_canon[c] = block

    missing_in_intel = [s for s in SYNCED_SECTIONS if s not in intel_by_canon]
    if missing_in_intel:
        print(
            f"ERROR: intel/chef.md missing sections required by sync: "
            f"{missing_in_intel}",
            file=sys.stderr,
        )
        sys.exit(1)

    replaced = []
    out_parts = []
    for title, block in skill_sections:
        c = canonical(title)
        if c:
            intel_block = intel_by_canon[c]
            skill_head = block.splitlines(keepends=True)[0]
            intel_body = "".join(intel_block.splitlines(keepends=True)[1:])
            out_parts.append(skill_head + intel_body)
            replaced.append(c)
        else:
            out_parts.append(block)

    missing_in_skill = [s for s in SYNCED_SECTIONS if s not in replaced]
    if missing_in_skill:
        first = missing_in_skill[0]
        print(
            f"ERROR: skills/chef/SKILL.md missing sections expected by sync: "
            f"{missing_in_skill}. Add a '## {first}' heading (may be empty) "
            f"so the sync can populate it.",
            file=sys.stderr,
        )
        sys.exit(1)

    SKILL.write_text("".join(out_parts))
    rel_intel = INTEL.relative_to(REPO_ROOT)
    rel_skill = SKILL.relative_to(REPO_ROOT)
    print(
        f"sync-skill-from-intel: synced {len(replaced)} section(s) "
        f"from {rel_intel} -> {rel_skill}"
    )


if __name__ == "__main__":
    main()
