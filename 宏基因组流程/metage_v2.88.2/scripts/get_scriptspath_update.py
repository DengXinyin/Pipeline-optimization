# -*- coding: utf-8 -*-
import os

Rscript_j = os.environ.get('METAGE_RSCRIPT', '/root/anaconda3/envs/r/bin/Rscript')
R_libPaths = os.environ.get('METAGE_RLIB', '/root/anaconda3/envs/r/lib/R/library')
# 允许通过环境变量指定 R 脚本所在目录（例如挂载原 scripts/ 到 /scripts）
scripts_path = os.environ.get('METAGE_SCRIPTS_PATH', os.path.split(os.path.realpath(__file__))[0])
