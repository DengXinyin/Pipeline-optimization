#!/bin/bash
# 用法：在 tmux 会话中执行
#   sudo bash /home/xydeng/Metagenomics/scripts_dxy/Script/run_12_anno_update_docker.sh 2>&1 | tee /home/xydeng/Metagenomics/scripts_dxy/logs/12_anno_update_runtime.log

cd /home/xydeng/Metagenomics || exit 1
rm -rf /home/xydeng/Metagenomics/anno_update
mkdir -p /home/xydeng/Metagenomics/scripts_dxy/logs

docker run --network=host --rm --cpus=24 --memory="512g" \
    -v /data/data2/metagenome-DB:/metagenome-DB \
    -v /home/xydeng/Metagenomics/scripts_dxy/Script:/root/microbiome/microbiome/metage_megahit \
    -v /home/xydeng/Metagenomics:/home/xydeng/Metagenomics \
    192.168.30.202:23099/metage_megahit/metage:v2.87 \
    bash /root/microbiome/microbiome/metage_megahit/run_12_anno_update.sh
