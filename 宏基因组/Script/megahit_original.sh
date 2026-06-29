#!/bin/bash
# 20260618_original: 原 megahit.sh 的精确副本，仅修复 sample.txt tab 分隔导致的 cut 解析问题，
#                    用于和优化版 megahit_update.sh 做运行时间对比。

datadir=${1}
cle_hodir=${2}
tmpdir=${3}
type=${4}

mkdir -p ${tmpdir}/length

awk 'NR!=1 {print}' ${datadir}/sample.txt|while read id;do
  sample=`echo ${id}|cut -f 2|tr -d '\n\r'`
  if [ "${type}" = 'none' ];then
    echo "${cle_hodir}/${sample}_clean_1.fastq.gz" >> ${tmpdir}/sample1.txt
    echo "${cle_hodir}/${sample}_clean_2.fastq.gz" >> ${tmpdir}/sample2.txt
  else
    echo "${cle_hodir}/${sample}_dehost_1.fastq.gz" >> ${tmpdir}/sample1.txt
    echo "${cle_hodir}/${sample}_dehost_2.fastq.gz" >> ${tmpdir}/sample2.txt
  fi
  echo "${tmpdir}/${sample}" >> ${tmpdir}/sample.name.txt
done

# 原代码参数：-j 7 -t 12
parallel --verbose -j 7 --memfree 30G --xapply \
	'megahit -t 12 -1 {1} -2 {2} -o {3}' \
	:::: ${tmpdir}/sample1.txt :::: ${tmpdir}/sample2.txt :::: ${tmpdir}/sample.name.txt

awk 'NR!=1 {print}' ${datadir}/sample.txt|while read id;do
    sample=`echo ${id}|cut -f 2|tr -d '\n\r'`
    seqkit seq -m 500 ${tmpdir}/${sample}/final.contigs.fa > ${tmpdir}/${sample}/final.contigs.fa.tmp
    awk -v sample="${sample}" '$0 ~ /^>/ {count++; $0=">seq_" sample "." count}1' ${tmpdir}/${sample}/final.contigs.fa.tmp > ${tmpdir}/${sample}/final.contigs.fa
    seqkit fx2tab -j 36 -l -n -i -H ${tmpdir}/${sample}/final.contigs.fa  > ${tmpdir}/length/${sample}_length.txt
    assembly-stats -t ${tmpdir}/${sample}/final.contigs.fa > ${tmpdir}/length/${sample}_stats.txt
done
