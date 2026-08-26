#!/usr/bin/env python3
"""Convert this project's WDL development syntax to legacy draft-2 syntax.

The conversion is intentionally narrow and validated against the constructs
used by the metage_v2.88.2 development WDL:

* remove the ``version development`` declaration;
* flatten workflow/task ``input { ... }`` blocks;
* represent Directory values as File values (draft-2 has no Directory type);
* convert ``~{...}`` placeholders to ``${...}``;
* preserve shell ``${VAR}`` expansions by rewriting them as ``$VAR``.

The source WDL is never modified.  Regenerate the platform upload file with:

    python3 scripts/convert_wdl_to_draft2.py \
      metage_v2.88.2.development.wdl \
      metage_v2.88.2.wdl
"""

import argparse
import re
from pathlib import Path
from typing import List, Optional


INPUT_START = re.compile(r"^(?P<indent>[ \t]*)input[ \t]*\{[ \t]*$")
VERSION_LINE = re.compile(r"^[ \t]*version[ \t]+development[ \t]*$")


def convert(source):
    lines = source.splitlines(keepends=True)
    converted = [
        "# Legacy draft-2 platform compatibility build.\n",
        "# Generated from the development-syntax incremental WDL; do not edit by hand.\n",
        "\n",
    ]
    input_indent = None  # type: Optional[str]
    in_command = False
    removed_input_blocks = 0
    removed_version = 0

    for line in lines:
        if VERSION_LINE.match(line.rstrip("\r\n")):
            removed_version += 1
            continue

        if input_indent is not None:
            stripped_newline = line.rstrip("\r\n")
            if stripped_newline == input_indent + "}":
                input_indent = None
                continue

            # Move declarations one level outward after removing input { ... }.
            child_indent = input_indent + "    "
            if line.startswith(child_indent):
                line = input_indent + line[len(child_indent) :]
        else:
            match = INPUT_START.match(line.rstrip("\r\n"))
            if match:
                input_indent = match.group("indent")
                removed_input_blocks += 1
                continue

        stripped = line.strip()
        if stripped == "command <<<":
            in_command = True
        elif stripped == ">>>":
            in_command = False

        # In draft-2, ${...} is WDL interpolation. Rewrite existing simple
        # shell variable expansions before converting modern WDL placeholders.
        if in_command and "${" in line:
            line = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", r"$\1", line)

        line = re.sub(r"\bDirectory\b", "File", line)
        line = line.replace("~{", "${")
        converted.append(line)

    if input_indent is not None:
        raise ValueError("unterminated input block")
    if removed_version != 1:
        raise ValueError(
            f"expected exactly one 'version development' line, found {removed_version}"
        )
    if removed_input_blocks == 0:
        raise ValueError("no input blocks were found")

    result = "".join(converted)
    checks = {
        "version declaration": re.search(r"(?m)^\s*version\s+", result),
        "input block": re.search(r"(?m)^\s*input\s*\{", result),
        "Directory type": re.search(r"\bDirectory\b", result),
        "modern placeholder": re.search(r"~\{", result),
    }
    remaining = [name for name, match in checks.items() if match]
    if remaining:
        raise ValueError("conversion left unsupported syntax: " + ", ".join(remaining))

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    source = args.source.read_text(encoding="utf-8")
    result = convert(source)
    args.destination.write_text(result, encoding="utf-8")
    print(f"Wrote draft-2 WDL: {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
