#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of pdf2png.py

import os
import sys
import argparse
import logging

import fitz

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def pdf2png(pic, zoom=4):
    try:
        pdf_doc = fitz.open(pic)
        mat = fitz.Matrix(zoom, zoom)
        pix = pdf_doc[0].get_pixmap(matrix=mat)
        png = os.path.splitext(pic)[0] + '.png'
        pix.save(png)
        log.info('转换 %s -> %s', pic, png)
    except fitz.fitz.EmptyFileError:
        log.warning('无法打开空 PDF: %s', pic)
    except Exception as e:
        log.error('转换 %s 失败: %s', pic, e)


def changefile(path, zoom=4):
    for dirpath, _dirnames, filenames in os.walk(path):
        for file_name in filenames:
            if not file_name.lower().endswith('.pdf'):
                continue
            file_path = os.path.join(dirpath, file_name)
            pdf2png(file_path, zoom)


def main():
    parser = argparse.ArgumentParser(description='Convert PDF first page to PNG (update version)')
    parser.add_argument('-resDir', '--res-dir', type=str, required=True, help='directory to recursively convert')
    parser.add_argument('--zoom', type=int, default=4, help='render zoom factor')
    args = parser.parse_args()

    res_dir = os.path.abspath(args.res_dir)
    if not os.path.isdir(res_dir):
        log.error('目录不存在: %s', res_dir)
        sys.exit(1)

    try:
        changefile(res_dir, args.zoom)
        log.info('pdf2png 完成')
    except Exception as e:
        log.error('pdf2png 失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
