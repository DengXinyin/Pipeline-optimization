#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ec_to_metacyc_pathways.py

Map EC numbers (from eggNOG-mapper or other annotation) to MetaCyc pathways
using MetaCyc flat files: reactions.dat and pathways.dat.

Usage:
    python ec_to_metacyc_pathways.py \
        --reactions reactions.dat \
        --pathways pathways.dat \
        --ec-list gene_ec.tsv \
        --output gene_metacyc_pathways.tsv

Expected input (gene_ec.tsv):
    gene_id    EC_number
    gene_1     1.1.1.1
    gene_2     2.7.1.40
    (supports multiple ECs separated by ';' or ',')

Output (gene_metacyc_pathways.tsv):
    gene_id | ec_number | reaction_id | pathway_id | pathway_name
"""

import argparse
import csv
import re
import sys


def parse_dat_file(path):
    """Generic parser for MetaCyc attribute-value .dat files."""
    records = []
    current = {}
    current_field = None

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')

            if line == '//':
                if current:
                    records.append(current)
                    current = {}
                current_field = None
                continue

            if line.startswith(' ') or line.startswith('\t'):
                if current_field is not None:
                    value = line.strip()
                    if value:
                        current[current_field].append(value)
                continue

            match = re.match(r'^([A-Z][A-Z0-9_-]*)\s+-\s+(.*)$', line)
            if match:
                field_name = match.group(1)
                value = match.group(2).strip()
                if field_name not in current:
                    current[field_name] = []
                current[field_name].append(value)
                current_field = field_name

    return records


def build_ec_to_reactions(reactions_dat):
    """Build EC -> set(reaction_id) mapping."""
    ec_to_rxn = {}
    for rec in parse_dat_file(reactions_dat):
        rxn_id = rec.get('UNIQUE-ID', [''])[0]
        ec_numbers = rec.get('EC-NUMBER', [])
        for ec in ec_numbers:
            ec = ec.strip()
            if not ec:
                continue
            ec_to_rxn.setdefault(ec, set()).add(rxn_id)
    return ec_to_rxn


def build_reaction_to_pathways(pathways_dat):
    """Build reaction_id -> list[(pathway_id, pathway_name)] mapping."""
    rxn_to_pw = {}
    for rec in parse_dat_file(pathways_dat):
        pw_id = rec.get('UNIQUE-ID', [''])[0]
        pw_name = rec.get('COMMON-NAME', [''])[0]
        rxn_list = rec.get('REACTION-LIST', [])
        for rxn in rxn_list:
            rxn = rxn.strip()
            if not rxn:
                continue
            rxn_to_pw.setdefault(rxn, []).append((pw_id, pw_name))
    return rxn_to_pw


def parse_ec_list(path):
    """Parse gene-to-EC TSV."""
    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            gene_id = row.get('gene_id', '').strip()
            ec_field = row.get('EC_number', '').strip()
            if not gene_id or not ec_field:
                continue
            ecs = re.split(r'[,;\s]+', ec_field)
            for ec in ecs:
                ec = ec.strip()
                if ec:
                    rows.append((gene_id, ec))
    return rows


def main():
    parser = argparse.ArgumentParser(
        description='Map EC numbers to MetaCyc pathways'
    )
    parser.add_argument('--reactions', required=True,
                        help='MetaCyc reactions.dat')
    parser.add_argument('--pathways', required=True,
                        help='MetaCyc pathways.dat')
    parser.add_argument('--ec-list', required=True,
                        help='TSV with gene_id and EC_number columns')
    parser.add_argument('--output', required=True,
                        help='Output TSV')
    args = parser.parse_args()

    print('[INFO] Building EC -> Reaction mapping...')
    ec_to_rxn = build_ec_to_reactions(args.reactions)
    print(f'[INFO] {len(ec_to_rxn)} EC numbers mapped to reactions')

    print('[INFO] Building Reaction -> Pathway mapping...')
    rxn_to_pw = build_reaction_to_pathways(args.pathways)
    print(f'[INFO] {len(rxn_to_pw)} reactions mapped to pathways')

    print('[INFO] Parsing gene EC list...')
    gene_ec_rows = parse_ec_list(args.ec_list)
    print(f'[INFO] {len(gene_ec_rows)} gene-EC pairs')

    total_mappings = 0
    with open(args.output, 'w', encoding='utf-8', newline='') as out:
        writer = csv.writer(out, delimiter='\t')
        writer.writerow(['gene_id', 'ec_number', 'reaction_id',
                         'pathway_id', 'pathway_name'])

        for gene_id, ec in gene_ec_rows:
            rxns = ec_to_rxn.get(ec, set())
            for rxn in rxns:
                pathways = rxn_to_pw.get(rxn, [])
                if not pathways:
                    writer.writerow([gene_id, ec, rxn, '', ''])
                    total_mappings += 1
                for pw_id, pw_name in pathways:
                    writer.writerow([gene_id, ec, rxn, pw_id, pw_name])
                    total_mappings += 1

    print(f'[INFO] Wrote {total_mappings} mappings to {args.output}')


if __name__ == '__main__':
    main()
