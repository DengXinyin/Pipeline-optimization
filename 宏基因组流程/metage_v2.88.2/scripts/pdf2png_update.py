#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of pdf2png.py

import os
import sys
import argparse
import logging
from multiprocessing import Pool, cpu_count

import fitz

try:
    from PIL import Image
except ImportError:  # Pillow 不是所有旧镜像的必选依赖
    Image = None

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def pdf2png(args):
    pic, dpi = args
    try:
        pdf_doc = fitz.open(pic)
        # PDF 的默认 CSS 分辨率为 72 dpi。直接使用 dpi 参数不仅控制像素数，
        # 也会在支持该参数的 PyMuPDF 版本中写入 PNG 的分辨率元数据。
        page = pdf_doc[0]
        try:
            pix = page.get_pixmap(dpi=dpi)
        except (AttributeError, TypeError):
            # 兼容旧版 PyMuPDF：用等价缩放矩阵生成约定分辨率的像素。
            scale = float(dpi) / 72.0
            matrix = fitz.Matrix(scale, scale)
            if hasattr(page, 'get_pixmap'):
                pix = page.get_pixmap(matrix=matrix)
            else:
                pix = page.getPixmap(matrix=matrix)
        # 旧版 PyMuPDF 只有缩放矩阵时不会自动写 DPI 元数据，显式设置，
        # 确保像素尺寸和文件标注都统一为 300 dpi。
        if hasattr(pix, 'set_dpi'):
            pix.set_dpi(int(round(dpi)), int(round(dpi)))
        elif hasattr(pix, 'setResolution'):
            pix.setResolution(int(round(dpi)), int(round(dpi)))
        png = os.path.splitext(pic)[0] + '.png'
        if hasattr(pix, 'save'):
            pix.save(png)
        else:
            pix.writePNG(png)
        # 旧版 Pixmap.writePNG 不写入分辨率元数据，用 Pillow 补写；
        # 即使 Pillow 不存在，像素尺寸仍按 300 dpi 生成。
        if Image is not None:
            with Image.open(png) as image:
                image.save(png, dpi=(int(round(dpi)), int(round(dpi))))
        return ('ok', pic, png)
    except Exception as e:
        # 不同 PyMuPDF 版本对空 PDF 的异常类位置不同，避免直接引用不存在的
        # fitz.fitz.EmptyFileError 导致异常处理本身再次报错。
        if e.__class__.__name__ == 'EmptyFileError':
            return ('empty', pic, None)
        return ('error', pic, str(e))


def changefile(path, dpi=300, workers=None):
    if workers is None:
        workers = min(8, cpu_count())

    pdf_files = []
    for dirpath, _dirnames, filenames in os.walk(path):
        for file_name in filenames:
            if not file_name.lower().endswith('.pdf'):
                continue
            pdf_files.append((os.path.join(dirpath, file_name), dpi))

    if not pdf_files:
        log.warning('未找到 PDF 文件: %s', path)
        return

    log.info('发现 %d 个 PDF 文件，使用 %d 进程并行转换', len(pdf_files), workers)

    ok = empty = error = 0
    with Pool(processes=workers) as pool:
        for status, pic, info in pool.imap_unordered(pdf2png, pdf_files, chunksize=1):
            if status == 'ok':
                ok += 1
                log.info('转换 %s -> %s', pic, info)
            elif status == 'empty':
                empty += 1
                log.warning('无法打开空 PDF: %s', pic)
            else:
                error += 1
                log.error('转换 %s 失败: %s', pic, info)

    log.info('PDF 转换统计: 成功 %d, 空文件 %d, 失败 %d', ok, empty, error)


def main():
    parser = argparse.ArgumentParser(description='Convert PDF first page to PNG (update version)')
    parser.add_argument('-resDir', '--res-dir', type=str, required=True, help='directory to recursively convert')
    parser.add_argument('--dpi', type=float, default=300,
                        help='PNG 输出分辨率（默认 300 dpi）')
    parser.add_argument('--zoom', type=float, default=None,
                        help='兼容旧参数：缩放倍数，优先级低于 --dpi（zoom=4 约等于 288 dpi）')
    parser.add_argument('-j', '--jobs', type=int, default=None, help='number of parallel workers (default: min(8, cpu_count))')
    args = parser.parse_args()

    res_dir = os.path.abspath(args.res_dir)
    if not os.path.isdir(res_dir):
        log.error('目录不存在: %s', res_dir)
        sys.exit(1)

    try:
        dpi = args.dpi if args.zoom is None else args.zoom * 72.0
        changefile(res_dir, dpi, args.jobs)
        log.info('pdf2png 完成')
    except Exception as e:
        log.error('pdf2png 失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
