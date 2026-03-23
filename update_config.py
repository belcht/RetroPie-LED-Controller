#!/usr/bin/env python3
"""
update_config.py — Section-aware TOML key updater.

Usage: update_config.py <file> <section> <key> <value>

Value is written as-is (caller is responsible for quoting strings).
Example:
  update_config.py ledcontrol.toml general default_animate '"kitt"'
  update_config.py ledcontrol.toml general global_brightness 0.8
"""

import re
import sys


def update_toml(filepath: str, section: str, key: str, value: str) -> None:
    with open(filepath, 'r') as f:
        content = f.read()

    # Match from [section] header to next [section] header or end of file
    section_re = re.compile(
        r'(\[' + re.escape(section) + r'\].*?)(?=\n\[|\Z)',
        re.DOTALL
    )
    key_re = re.compile(r'^' + re.escape(key) + r'\s*=.*$', re.MULTILINE)

    match = section_re.search(content)
    if match:
        section_text = match.group(1)
        if key_re.search(section_text):
            new_section = key_re.sub(f'{key} = {value}', section_text)
        else:
            new_section = section_text.rstrip('\n') + f'\n{key} = {value}'
        content = content[:match.start()] + new_section + content[match.end():]
    else:
        # Section not found — append it
        content = content.rstrip('\n') + f'\n\n[{section}]\n{key} = {value}\n'

    with open(filepath, 'w') as f:
        f.write(content)


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <file> <section> <key> <value>", file=sys.stderr)
        sys.exit(1)
    update_toml(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
