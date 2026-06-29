#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of xlsx_trans.py

import os
import sys
import argparse
import logging

import openpyxl
from openpyxl.styles import Font, Border, Side, Alignment

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def xlsx_trans(resdir, font_name='宋体'):
    for dirpath, _dirnames, filenames in os.walk(resdir):
        for file in filenames:
            if not file.endswith('.xlsx'):
                continue
            file_dir = os.path.join(dirpath, file)
            try:
                wb = openpyxl.load_workbook(file_dir)
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
                wb.save(file_dir)
                log.info('格式化: %s', file_dir)
            except Exception as e:
                log.error('无法格式化文件 %s: %s', file_dir, e)


def main():
    parser = argparse.ArgumentParser(description='Format xlsx files (update version)')
    parser.add_argument('--res', type=str, default='Result', help='the dir of res')
    parser.add_argument('--font', type=str, default=os.environ.get('METAGE_FONT', '宋体'), help='font name')
    args = parser.parse_args()

    resdir = os.path.abspath(args.res)
    if not os.path.isdir(resdir):
        log.error('目录不存在: %s', resdir)
        sys.exit(1)

    try:
        xlsx_trans(resdir, args.font)
        log.info('xlsx_trans 完成')
    except Exception as e:
        log.error('xlsx_trans 失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
