#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of xlsx_trans.py

import os
import sys
import argparse
import logging
import posixpath
import shutil
import tempfile
import zipfile
from multiprocessing import Pool, cpu_count
from xml.etree import ElementTree

import openpyxl
from openpyxl.styles import Font, Border, Side, Alignment

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
DRAWING_REL_TYPES = {
    'http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing',
    'http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing',
}


def _relationship_target(rel_path, target):
    """Return the ZIP member referenced by an internal OOXML relationship."""
    if posixpath.basename(rel_path) == '.rels':
        source_dir = ''
    else:
        source_dir = posixpath.dirname(posixpath.dirname(rel_path))
    return posixpath.normpath(posixpath.join(source_dir, target.lstrip('/')))


def _repair_missing_drawing_relationships(file_dir):
    """Create a repaired temporary copy when drawing relationships are dangling.

    Some R-generated workbooks retain drawing/vmlDrawing relationships after the
    corresponding ZIP members have been removed.  Excel may silently repair such
    files, but openpyxl raises KeyError while loading them.  Only relationships
    whose target is actually absent are removed; valid drawings are preserved.

    Returns ``(temporary_path, removed_targets)``.  ``temporary_path`` is None
    when no repair is needed.
    """
    replacements = {}
    removed_targets = []

    with zipfile.ZipFile(file_dir, 'r') as archive:
        members = set(archive.namelist())
        for rel_path in sorted(members):
            if not rel_path.endswith('.rels'):
                continue
            try:
                root = ElementTree.fromstring(archive.read(rel_path))
            except ElementTree.ParseError:
                continue

            changed = False
            for rel in list(root):
                if rel.get('Type') not in DRAWING_REL_TYPES:
                    continue
                if rel.get('TargetMode', '').lower() == 'external':
                    continue
                target = rel.get('Target')
                if not target:
                    continue
                resolved_target = _relationship_target(rel_path, target)
                if resolved_target in members:
                    continue
                root.remove(rel)
                removed_targets.append(resolved_target)
                changed = True

            if changed:
                ElementTree.register_namespace('', REL_NS)
                replacements[rel_path] = (
                    b"<?xml version='1.0' encoding='utf-8'?>\n"
                    + ElementTree.tostring(root, encoding='utf-8')
                )

        if not replacements:
            return None, []

        tmp = tempfile.NamedTemporaryFile(
            prefix='.xlsx_repair_', suffix='.xlsx',
            dir=os.path.dirname(file_dir), delete=False
        )
        tmp_path = tmp.name
        tmp.close()
        try:
            with zipfile.ZipFile(tmp_path, 'w') as repaired:
                for info in archive.infolist():
                    data = replacements.get(info.filename)
                    if data is None:
                        data = archive.read(info)
                    repaired.writestr(info, data)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    return tmp_path, removed_targets


def _format_xlsx(args):
    file_dir, font_name = args
    repaired_path = None
    output_path = None
    wb = None
    try:
        repaired_path, removed_targets = _repair_missing_drawing_relationships(file_dir)
        load_path = repaired_path or file_dir
        wb = openpyxl.load_workbook(load_path)
        ws = wb.active
        font = Font(color='000000', bold=False, name=font_name)
        thin_border = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000')
        )
        alignment = Alignment(horizontal='center', vertical='center')
        for row in ws.iter_rows():
            for cell in row:
                cell.font = font
                cell.border = thin_border
                cell.alignment = alignment
        output = tempfile.NamedTemporaryFile(
            prefix='.xlsx_format_', suffix='.xlsx',
            dir=os.path.dirname(file_dir), delete=False
        )
        output_path = output.name
        output.close()
        wb.save(output_path)
        wb.close()
        wb = None

        # Keep the original permissions and replace only after a complete save.
        shutil.copystat(file_dir, output_path)
        os.replace(output_path, file_dir)
        output_path = None
        return ('repaired' if removed_targets else 'ok', file_dir, removed_targets)
    except Exception as e:
        return ('error', file_dir, str(e))
    finally:
        if wb is not None:
            wb.close()
        for tmp_path in (repaired_path, output_path):
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)


def xlsx_trans(resdir, font_name='Times New Roman', workers=None):
    if workers is None:
        workers = min(8, cpu_count())

    xlsx_files = []
    for dirpath, _dirnames, filenames in os.walk(resdir):
        for file in filenames:
            if not file.endswith('.xlsx'):
                continue
            xlsx_files.append((os.path.join(dirpath, file), font_name))

    if not xlsx_files:
        log.warning('未找到 xlsx 文件: %s', resdir)
        return

    log.info('发现 %d 个 xlsx 文件，使用 %d 进程并行格式化', len(xlsx_files), workers)

    ok = repaired = error = 0
    with Pool(processes=workers) as pool:
        for status, file_dir, detail in pool.imap_unordered(_format_xlsx, xlsx_files, chunksize=1):
            if status == 'ok':
                ok += 1
                log.info('格式化: %s', file_dir)
            elif status == 'repaired':
                repaired += 1
                ok += 1
                log.warning(
                    '修复 %d 个缺失的 Drawing 引用并完成格式化: %s (%s)',
                    len(detail), file_dir, ', '.join(detail)
                )
            else:
                error += 1
                log.error('无法格式化文件 %s: %s', file_dir, detail)

    log.info('xlsx 格式化统计: 成功 %d (其中修复 %d), 失败 %d', ok, repaired, error)


def main():
    parser = argparse.ArgumentParser(description='Format xlsx files (update version)')
    parser.add_argument('--res', type=str, default='Result', help='the dir of res')
    parser.add_argument('--font', type=str, default=os.environ.get('METAGE_FONT', 'Times New Roman'), help='font name')
    parser.add_argument('-j', '--jobs', type=int, default=None, help='number of parallel workers (default: min(8, cpu_count))')
    args = parser.parse_args()

    resdir = os.path.abspath(args.res)
    if not os.path.isdir(resdir):
        log.error('目录不存在: %s', resdir)
        sys.exit(1)

    try:
        xlsx_trans(resdir, args.font, args.jobs)
        log.info('xlsx_trans 完成')
    except Exception as e:
        log.error('xlsx_trans 失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
