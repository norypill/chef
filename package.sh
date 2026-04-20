#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
rm -f chef.skill
(cd skills/chef && zip -r ../../chef.skill . -x ".DS_Store")
echo "Built chef.skill from skills/chef/ — drag into Cowork to install/update."
