#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
metacyc_parse_pathways.py

Parse MetaCyc flat file `pathways.dat` and extract basic pathway information:
- UNIQUE-ID (pathway ID)
- COMMON-NAME (pathway name)
- TAXONOMIC-RANGE (taxonomic range)
- REACTION-LIST (reaction IDs in the pathway)
- PATHWAY-LINKS (linked pathways)

Usage:
    python metacyc_parse_pathways.py pathways.dat pathways_summary.tsv

Output TSV columns:
    pathway_id | pathway_name | taxonomic_range | reactions | linked_pathways
"""

import sys
import re
import csv


def parse_pathways_dat(path):
    """Parse MetaCyc pathways.dat into a list of pathway records."""
    records = []
    current = {}
    current_field = None

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')

            # End of a record
            if line == '//':
                if current:
                    records.append(current)
                    current = {}
                current_field = None
                continue

            # Continuation line (starts with spaces or tabs)
            if line.startswith(' ') or line.startswith('\t'):
                if current_field is not None:
                    value = line.strip()
                    if value:
                        current[current_field].append(value)
                continue

            # New field line: FIELD-NAME - value
            match = re.match(r'^([A-Z][A-Z0-9_-]*)\s+-\s+(.*)$', line)
            if match:
                field_name = match.group(1)
                value = match.group(2).strip()
                if field_name not in current:
                    current[field_name] = []
                current[field_name].append(value)
                current_field = field_name

    return records


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    input_dat = sys.argv[1]
    output_tsv = sys.argv[2]

    records = parse_pathways_dat(input_dat)

    with open(output_tsv, 'w', encoding='utf-8', newline='') as out:
        writer = csv.writer(out, delimiter='\t')
        writer.writerow([
            'pathway_id',
            'pathway_name',
            'taxonomic_range',
            'reactions',
            'linked_pathways'
        ])

        for rec in records:
            pw_id = rec.get('UNIQUE-ID', [''])[0]
            pw_name = rec.get('COMMON-NAME', [''])[0]
            tax_range = ';'.join(rec.get('TAXONOMIC-RANGE', []))
            reactions = ';'.join(rec.get('REACTION-LIST', []))
            links = ';'.join(rec.get('PATHWAY-LINKS', []))

            writer.writerow([pw_id, pw_name, tax_range, reactions, links])

    print(f"[INFO] Parsed {len(records)} pathways -> {output_tsv}")


if __name__ == '__main__':
    main()
