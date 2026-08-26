#!/usr/bin/env python3
"""Generate one Graphviz DOT table page per WDL task category."""

import argparse
import html
from pathlib import Path

import WDL


GROUPS = [
    ("规划、复用与增量合并", {"deal_parameter", "merge_upstream_results", "check_input_no_raw", "check_input_with_raw", "apply_registry"}),
    ("核心上游", {"kneaddata_no", "megahit_no", "prodig_no", "bwa_no", "tax_anno", "func_anno"}),
    ("完整集合注释", {"anno", "VCA_anno", "MBQ_anno", "COG_anno", "MetaCyc_anno"}),
    ("基础统计与差异分析", {"tax_base", "func_base", "tax_diff", "func_diff", "tax_unifrac", "func_unifrac"}),
    ("可选上游模块", {"kraken2_anno", "kraken2_tax_base", "kraken2_tax_diff", "bins", "bins_drep", "quant_classify", "bins_stats", "ref_assembly", "ref_mapping", "snp_calling"}),
    ("结果汇总与交付", {"coll_res_ana", "coll_res_ana_bins", "coll_res_NOana", "res2json", "resFile", "update_registry"}),
]


def esc(value):
    return html.escape(str(value), quote=True)


def declaration_lines(declarations, output=False):
    lines = []
    for decl in declarations:
        line = f'<FONT FACE="Noto Sans Mono CJK SC" COLOR="#0F3B66"><B>{esc(decl.name)}</B></FONT>  '
        line += f'<FONT COLOR="#075985">[{esc(decl.type)}]</FONT>'
        expr = getattr(decl, "expr", None)
        if expr is not None:
            label = "输出" if output else "默认"
            line += f'<BR ALIGN="LEFT"/><FONT POINT-SIZE="8" COLOR="#64748B">{label}: {esc(expr)}</FONT>'
        lines.append(line)
    return '<BR ALIGN="LEFT"/>'.join(lines) if lines else '<FONT COLOR="#94A3B8">无显式声明</FONT>'


def make_dot(title, tasks, start_number, total_tasks, source_name):
    rows = []
    number = start_number
    for task in tasks:
        input_text = declaration_lines(task.inputs)
        output_text = declaration_lines(task.outputs, output=True)
        shade = "#FFFFFF" if number % 2 else "#F8FAFC"
        rows.append(
            f'<TR><TD BGCOLOR="{shade}" WIDTH="34"><FONT COLOR="#64748B">{number}</FONT></TD>'
            f'<TD BGCOLOR="{shade}" WIDTH="132"><FONT FACE="Noto Sans Mono CJK SC" COLOR="#17365D"><B>{esc(task.name)}</B></FONT></TD>'
            f'<TD BGCOLOR="{shade}" WIDTH="315" ALIGN="LEFT">{input_text}</TD>'
            f'<TD BGCOLOR="{shade}" WIDTH="315" ALIGN="LEFT">{output_text}</TD></TR>'
        )
        number += 1
    table = ''.join(rows)
    return f'''digraph task_table {{
      graph [bgcolor="white", pad="0.18", size="11.25,7.55!", ratio="compress", fontname="Noto Sans CJK SC",
             fontsize=20, labelloc=t, label="增量版 WDL Task 输入/输出接口表\\n{esc(title)}"];
      node [shape=plaintext, fontname="Noto Sans CJK SC", fontsize=9.5];
      info [label=<
        <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" WIDTH="796">
          <TR><TD ALIGN="LEFT"><FONT COLOR="#53627A">自动提取自 {esc(source_name)}｜共 {total_tasks} 个 task｜? 表示可选类型</FONT></TD></TR>
        </TABLE>
      >];
      table [label=<
        <TABLE BORDER="1" COLOR="#8CA9C9" CELLBORDER="1" CELLSPACING="0" CELLPADDING="6">
          <TR>
            <TD BGCOLOR="#DBEAFE" WIDTH="34"><B>#</B></TD>
            <TD BGCOLOR="#DBEAFE" WIDTH="132"><B>Task</B></TD>
            <TD BGCOLOR="#DBEAFE" WIDTH="315"><B>输入名称与 WDL 类型</B></TD>
            <TD BGCOLOR="#DBEAFE" WIDTH="315"><B>输出名称、WDL 类型与表达式</B></TD>
          </TR>
          {table}
        </TABLE>
      >];
      info -> table [style=invis];
    }}''', number


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wdl", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    document = WDL.load(args.wdl)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    grouped = set().union(*(names for _, names in GROUPS))
    extra = {task.name for task in document.tasks} - grouped
    groups = list(GROUPS) + ([('其他 task', extra)] if extra else [])
    number = 1
    page = 1
    for title, names in groups:
        tasks = [task for task in document.tasks if task.name in names]
        if not tasks:
            continue
        dot, number = make_dot(title, tasks, number, len(document.tasks), Path(args.wdl).name)
        (output_dir / f"task_table_{page:02d}.dot").write_text(dot, encoding="utf-8")
        page += 1


if __name__ == "__main__":
    main()
