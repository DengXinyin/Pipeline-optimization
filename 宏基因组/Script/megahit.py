#!/usr/bin/env python
# -*- coding: utf-8 -*-
# By: Wang Li 2024

import os
import shutil
import argparse
from get_scriptspath import scripts_path


# 		cmd = '''
# awk 'NR!=1 {print}' %s/sample.txt|while read id;do
#     sample=`echo ${id}|cut -d " " -f 2`
#     echo %s/${sample}_clean_1.fastq.gz >> %s/sample1.txt
# 	echo %s/${sample}_clean_2.fastq.gz >> %s/sample2.txt
# 	echo ${sample} >> %s/samplename.txt
# done
# parallel -j 3 --memfree 50G --xapply \
# 	'megahit -t 32 -1 {1} -2 {2} -o %s/{1/.}' \
# 	:::: %s/sample1.txt :::: %s/sample2.txt
# awk 'NR!=1 {print}' %s/sample.txt|while read id;do
#     sample=`echo ${id}|cut -d " " -f 2`
#     sam_file=${sample}_clean_1.fastq
#     awk '$0 ~ /^>/ {$0=">${sample}" (NR+1)/2}1' %s/${sam_file}/final.contigs.fa > %s/${sam_file}/otus.fasta
# done
# ''' % (datadir, cleandir, tmpdir, cleandir, tmpdir,
# 	   tmpdir, tmpdir, tmpdir, datadir, tmpdir, tmpdir)
def megahit(host, cleandir, host_dir, datadir, tmpdir):
    if not os.path.exists(os.path.join(tmpdir, 'length')):
        os.mkdir(os.path.join(tmpdir, 'length'))
    if host == 'none':
        cmd = '''
bash {0}/megahit.sh {1} {2} {3} 'none'
'''.format(scripts_path, datadir, cleandir, tmpdir)
    else:
        cmd = '''
        bash {0}/megahit.sh {1} {2} {3} 'host'
        '''.format(scripts_path, datadir, host_dir, tmpdir)
    os.system(cmd)


def main():
    parser = argparse.ArgumentParser(description='This script will assemble sequence through megahit')
    parser.add_argument('-I', '--i_datadir', type=str, required=True,default='data', help='the dir of sample.txt')
    parser.add_argument('--megahit', type=str,default='megahit', help='the res of megahit')
    parser.add_argument('--host_dir', type=str,default='de_host', help='the dir of dehost_data')
    parser.add_argument('--cleandir', type=str, default='cleandata', help='the dir of clean_data')
    parser.add_argument('--host', type=str, required=True, nargs='*', help='the host of metagenome')
    # parser.add_argument('--host', type=str, default='none', choices=['none', 'human', 'mouse'],
    # 					help='the host of metagenome')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    megahit_dir = os.path.abspath(args.megahit)
    cleandadir = os.path.abspath(args.cleandir)
    host_dir = os.path.abspath(args.host_dir)
    host = args.host[0]
    if not os.path.exists(megahit_dir):
        os.mkdir(megahit_dir)
    else:
        shutil.rmtree(megahit_dir, ignore_errors=True)
        os.mkdir(megahit_dir)

    megahit(host, cleandadir, host_dir, datadir, megahit_dir)


if __name__ == '__main__':
    main()
