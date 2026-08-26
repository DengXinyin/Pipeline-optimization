#!/usr/bin/env python3
"""Merge Docker defaults, common WDL fields, and per-task plot overrides."""

import argparse
import json
from copy import deepcopy
from pathlib import Path


TEXT_ELEMENTS = (
    "title",
    "subtitle",
    "axis_title",
    "axis_text",
    "legend_title",
    "legend_text",
    "data_label",
    "facet_label",
)
TEXT_PROPERTIES = ("font_family", "size", "bold", "italic", "align", "show")


def deep_merge(base, override):
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def parse_bool(value, field):
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    raise ValueError(f"{field} must be true/false, got: {value!r}")


def parse_number(value, field, integer=False):
    try:
        number = int(value) if integer else float(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be numeric, got: {value!r}") from exc
    if number <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return number


def load_json_object(path, allow_empty=False):
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text and allow_empty:
        return {}
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def common_overrides(args):
    override = {"global": {}, "text": {}, "legend": {}}

    global_types = {
        "font_family": str,
        "theme": str,
        "dpi": lambda value: parse_number(value, "dpi", integer=True),
        "figure_width": lambda value: parse_number(value, "figure_width"),
        "figure_height": lambda value: parse_number(value, "figure_height"),
    }
    for key, parser in global_types.items():
        value = getattr(args, f"global_{key}")
        if value != "":
            override["global"][key] = parser(value)

    for element in TEXT_ELEMENTS:
        element_override = {}
        for prop in TEXT_PROPERTIES:
            value = getattr(args, f"{element}_{prop}")
            if value == "":
                continue
            field = f"{element}.{prop}"
            if prop == "size":
                parsed = parse_number(value, field)
            elif prop in {"bold", "italic", "show"}:
                parsed = parse_bool(value, field)
            else:
                parsed = value
            element_override[prop] = parsed
        if element_override:
            override["text"][element] = element_override

    if args.legend_position:
        override["legend"]["position"] = args.legend_position
    if args.legend_frame:
        override["legend"]["frame"] = parse_bool(args.legend_frame, "legend.frame")
    if args.legend_show:
        override["legend"]["show"] = parse_bool(args.legend_show, "legend.show")

    if args.group_palette:
        colors = [color.strip() for color in args.group_palette.split(",") if color.strip()]
        if not colors:
            raise ValueError("group_palette did not contain any colors")
        override["group_palette"] = colors

    return {key: value for key, value in override.items() if value}


def validate(config):
    theme = config["global"].get("theme", "bw")
    if theme not in {"bw", "classic"}:
        raise ValueError("global.theme must be 'bw' or 'classic'")

    for element, style in config.get("text", {}).items():
        align = style.get("align", "center")
        if align not in {"left", "center", "right"}:
            raise ValueError(f"text.{element}.align must be left/center/right")

    position = config.get("legend", {}).get("position", "right")
    if position not in {"left", "right", "top", "bottom", "none"}:
        raise ValueError("legend.position must be left/right/top/bottom/none")

    palette = config.get("group_palette", [])
    if not isinstance(palette, list) or not palette:
        raise ValueError("group_palette must be a non-empty JSON array")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--default-config", required=True)
    parser.add_argument("--task-overrides", required=True)
    parser.add_argument("--out", required=True)

    for key in ("font_family", "theme", "dpi", "figure_width", "figure_height"):
        parser.add_argument(f"--global-{key.replace('_', '-')}", default="")

    for element in TEXT_ELEMENTS:
        for prop in TEXT_PROPERTIES:
            parser.add_argument(
                f"--{element.replace('_', '-')}-{prop.replace('_', '-')}",
                default="",
            )

    parser.add_argument("--legend-position", default="")
    parser.add_argument("--legend-frame", default="")
    parser.add_argument("--legend-show", default="")
    parser.add_argument("--group-palette", default="")
    return parser


def main():
    args = build_parser().parse_args()
    config = load_json_object(args.default_config)
    config = deep_merge(config, common_overrides(args))

    task_overrides = load_json_object(args.task_overrides, allow_empty=True)
    if task_overrides:
        if "tasks" in task_overrides:
            config = deep_merge(config, task_overrides)
        else:
            config["tasks"] = deep_merge(config.get("tasks", {}), task_overrides)

    validate(config)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"plot style written to {output}")


if __name__ == "__main__":
    main()
