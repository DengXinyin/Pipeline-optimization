#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build a project-pruned, unit-branch NCBI taxonomy tree for UniFrac."""

import csv
import os
import re

import pandas as pd
from Bio.Phylo.Newick import Clade, Tree


def _clean_name(value):
    value = str(value).strip()
    return value[3:] if value.startswith('s__') else value


class NCBITaxonomy:
    """Resolve abundance labels to TaxIDs and construct a pruned taxonomy tree.

    NCBI taxonomy does not publish evolutionary branch lengths.  Every
    parent-child taxonomy edge therefore receives length 1.0; outputs must be
    described as taxonomy-weighted/unweighted UniFrac.
    """

    def __init__(self, taxonomy_dir):
        self.taxonomy_dir = os.path.abspath(taxonomy_dir)
        required = ('nodes.dmp', 'names.dmp', 'merged.dmp')
        missing = [x for x in required
                   if not os.path.isfile(os.path.join(self.taxonomy_dir, x))]
        if missing:
            raise FileNotFoundError('NCBI taxonomy 缺少: ' + ', '.join(missing))
        self.parents = self._read_parents()
        self.merged = self._read_merged()

    @staticmethod
    def _fields(line):
        return [x.strip() for x in line.rstrip('\n').split('|')]

    def _read_parents(self):
        parents = {}
        with open(os.path.join(self.taxonomy_dir, 'nodes.dmp'),
                  encoding='utf-8', errors='replace') as handle:
            for line in handle:
                fields = self._fields(line)
                if len(fields) >= 2:
                    parents[fields[0]] = fields[1]
        if '1' not in parents:
            raise ValueError('nodes.dmp 缺少根 TaxID 1')
        return parents

    def _read_merged(self):
        merged = {}
        with open(os.path.join(self.taxonomy_dir, 'merged.dmp'),
                  encoding='utf-8', errors='replace') as handle:
            for line in handle:
                fields = self._fields(line)
                if len(fields) >= 2:
                    merged[fields[0]] = fields[1]
        return merged

    def current_taxid(self, taxid):
        taxid = str(taxid).strip()
        visited = set()
        while taxid in self.merged and taxid not in visited:
            visited.add(taxid)
            taxid = self.merged[taxid]
        return taxid if taxid in self.parents else None

    def _result_taxid_map(self, search_root, wanted_features):
        """Use Kraken's gene_<TaxID> table when it is present."""
        result = {}
        kraken_root = os.path.join(os.path.abspath(search_root), 'kraken2_taxonomy')
        path = os.path.join(kraken_root, 'gene.taxonomy.csv')
        if not os.path.isfile(path):
            return result
        frame = pd.read_csv(path, usecols=lambda x: x in ('GeneID', 'species'), dtype=str)
        if not {'GeneID', 'species'}.issubset(frame.columns):
            return result
        for gene_id, species in frame[['GeneID', 'species']].itertuples(index=False, name=None):
            match = re.fullmatch(r'gene_(\d+)', str(gene_id).strip())
            feature = str(species).strip()
            if not match or feature not in wanted_features:
                continue
            taxid = self.current_taxid(match.group(1))
            if taxid:
                result[feature] = taxid
        return result

    def resolve_features(self, features, result_root=None):
        features = [str(x).strip() for x in features]
        wanted = set(features)
        resolved = self._result_taxid_map(result_root, wanted) if result_root else {}
        unresolved_names = {_clean_name(x) for x in features if x not in resolved}
        scientific, aliases = {}, {}
        with open(os.path.join(self.taxonomy_dir, 'names.dmp'),
                  encoding='utf-8', errors='replace') as handle:
            for line in handle:
                fields = self._fields(line)
                if len(fields) < 4 or fields[1] not in unresolved_names:
                    continue
                taxid = self.current_taxid(fields[0])
                if not taxid:
                    continue
                aliases.setdefault(fields[1], set()).add(taxid)
                if fields[3] == 'scientific name':
                    scientific.setdefault(fields[1], set()).add(taxid)
        ambiguous = {}
        for feature in features:
            if feature in resolved:
                continue
            name = _clean_name(feature)
            candidates = scientific.get(name) or aliases.get(name) or set()
            if len(candidates) == 1:
                resolved[feature] = next(iter(candidates))
            elif len(candidates) > 1:
                ambiguous[feature] = sorted(candidates, key=lambda x: int(x))
        return resolved, sorted(wanted - set(resolved)), ambiguous

    def build_tree(self, feature_to_taxid):
        reverse = {}
        for feature, taxid in feature_to_taxid.items():
            reverse.setdefault(taxid, []).append(feature)
        duplicate_taxids = {x: y for x, y in reverse.items() if len(y) > 1}
        if duplicate_taxids:
            examples = list(duplicate_taxids.items())[:5]
            raise ValueError('多个物种标签映射到同一 TaxID: %s' % examples)

        included = {'1'}
        for taxid in reverse:
            current, visited = taxid, set()
            while current and current not in visited:
                visited.add(current)
                included.add(current)
                parent = self.parents.get(current)
                if not parent or parent == current:
                    break
                current = parent

        children = {x: [] for x in included}
        for taxid in included:
            if taxid == '1':
                continue
            parent = self.parents.get(taxid)
            if parent in included:
                children[parent].append(taxid)

        def make_clade(taxid, is_root=False):
            descendants = sorted(children.get(taxid, []), key=lambda x: int(x))
            feature = reverse.get(taxid, [None])[0]
            if feature is not None and not descendants:
                name = feature
            else:
                name = None if is_root else 'taxid_' + taxid
            clade = Clade(name=name, branch_length=None if is_root else 1.0)
            clade.clades = [make_clade(x) for x in descendants]
            if feature is not None and descendants:
                clade.clades.append(Clade(name=feature, branch_length=1.0))
            return clade

        return Tree(root=make_clade('1', is_root=True), rooted=True)


def write_mapping(path, features, resolved, unmapped, ambiguous):
    rows = []
    for feature in features:
        if feature in resolved:
            rows.append((feature, resolved[feature], 'matched'))
        elif feature in ambiguous:
            rows.append((feature, ','.join(ambiguous[feature]), 'ambiguous'))
        else:
            rows.append((feature, '', 'unmapped'))
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(('feature_id', 'ncbi_taxid', 'status'))
        writer.writerows(rows)
