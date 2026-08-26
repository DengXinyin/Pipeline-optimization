"""Shared, language-neutral plot-style adapter for Python/matplotlib."""

import json
import os
from copy import deepcopy
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "plot_style.default.json"
FONT_DIRS = (
    Path("/usr/share/fonts/msttcore"),
    Path("/usr/local/share/fonts"),
)


def _deep_merge(base, override):
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _read_config(path):
    with Path(path).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"plot style must be a JSON object: {path}")
    return value


def load_plot_style(task_name=None, config_path=None):
    """Load the merged plot configuration and apply a task override."""
    selected = config_path or os.environ.get("METAGE_PLOT_CONFIG", "")
    config = _read_config(selected) if selected else _read_config(DEFAULT_CONFIG)

    task = task_name or os.environ.get("METAGE_PLOT_TASK", "")
    if task:
        task_override = config.get("tasks", {}).get(task, {})
        config = _deep_merge(config, task_override)

    # Compatibility with the earlier single environment-variable design.
    legacy_font = os.environ.get("METAGE_PLOT_FONT", "").strip()
    if legacy_font:
        config.setdefault("global", {})["font_family"] = legacy_font
    return config


# Backward-compatible export for older Python plotting scripts. Unlike the
# former fixed constant, it now follows the generated workflow configuration.
METAGE_PLOT_FONT = load_plot_style().get("global", {}).get(
    "font_family", "Times New Roman"
)


def register_matplotlib_fonts():
    """Register mounted fonts without relying on a stale matplotlib cache."""
    from matplotlib import font_manager

    for font_dir in FONT_DIRS:
        if not font_dir.is_dir():
            continue
        for pattern in ("*.ttf", "*.ttc", "*.otf"):
            for font_file in font_dir.glob(pattern):
                try:
                    font_manager.fontManager.addfont(str(font_file))
                except (OSError, RuntimeError):
                    continue


def _text_style(config, element):
    global_style = config.get("global", {})
    style = config.get("text", {}).get(element, {})
    family = style.get("font_family") or global_style.get("font_family", "Times New Roman")
    align = style.get("align", "center")
    return {
        "fontfamily": family,
        "fontsize": style.get("size", 16),
        "fontweight": "bold" if style.get("bold", False) else "normal",
        "fontstyle": "italic" if style.get("italic", False) else "normal",
        "ha": {"left": "left", "center": "center", "right": "right"}[align],
    }


def text_is_visible(config, element):
    return bool(config.get("text", {}).get(element, {}).get("show", True))


def get_text_kwargs(config, element):
    """Return matplotlib text keyword arguments for one semantic element."""
    return _text_style(config, element)


def group_color_map(config, groups):
    """Map unique groups to the ordered palette, preserving first appearance."""
    unique = list(dict.fromkeys(str(group) for group in groups if str(group) != ""))
    palette = config.get("group_palette", [])
    if len(unique) > len(palette):
        raise ValueError(
            f"group_palette has {len(palette)} colors but {len(unique)} groups are required"
        )
    return dict(zip(unique, palette))


def apply_matplotlib_style(plt, config=None, task_name=None):
    """Apply common typography, figure, and theme defaults to pyplot."""
    register_matplotlib_fonts()
    style = config or load_plot_style(task_name=task_name)
    global_style = style.get("global", {})
    title = _text_style(style, "title")
    axis_title = _text_style(style, "axis_title")
    axis_text = _text_style(style, "axis_text")
    legend_title = _text_style(style, "legend_title")
    legend_text = _text_style(style, "legend_text")

    plt.rcParams.update({
        "font.family": global_style.get("font_family", "Times New Roman"),
        "font.sans-serif": [
            global_style.get("font_family", "Times New Roman"),
            "Arial",
            "SimSun",
            "DejaVu Sans",
        ],
        "figure.figsize": (
            global_style.get("figure_width", 10),
            global_style.get("figure_height", 8),
        ),
        "figure.dpi": global_style.get("dpi", 300),
        "savefig.dpi": global_style.get("dpi", 300),
        "axes.titlesize": title["fontsize"],
        "axes.titleweight": title["fontweight"],
        "axes.labelsize": axis_title["fontsize"],
        "axes.labelweight": axis_title["fontweight"],
        "xtick.labelsize": axis_text["fontsize"],
        "ytick.labelsize": axis_text["fontsize"],
        "legend.fontsize": legend_text["fontsize"],
        "legend.title_fontsize": legend_title["fontsize"],
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })
    return style


def legend_kwargs(config):
    legend = config.get("legend", {})
    positions = {
        "right": "center left",
        "left": "center right",
        "top": "lower center",
        "bottom": "upper center",
    }
    position = legend.get("position", "right")
    return {
        "frameon": bool(legend.get("frame", False)),
        "loc": positions.get(position, "best"),
    }


def plotly_text_style(config, element):
    """Return a Plotly-compatible font dictionary for a semantic text element."""
    style = _text_style(config, element)
    return {
        "family": style["fontfamily"],
        "size": style["fontsize"],
        "color": "black",
    }


def plotly_layout(config):
    """Return shared Plotly layout fields matching the matplotlib adapter."""
    global_style = config.get("global", {})
    legend = config.get("legend", {})
    legend_positions = {
        "right": {"x": 1.02, "y": 0.5, "xanchor": "left", "yanchor": "middle"},
        "left": {"x": -0.02, "y": 0.5, "xanchor": "right", "yanchor": "middle"},
        "top": {"x": 0.5, "y": 1.02, "xanchor": "center", "yanchor": "bottom"},
        "bottom": {"x": 0.5, "y": -0.12, "xanchor": "center", "yanchor": "top"},
    }
    position = legend.get("position", "right")
    result = {
        "font": {
            "family": global_style.get("font_family", "Times New Roman"),
            "size": config.get("text", {}).get("axis_text", {}).get("size", 18),
        },
        "width": int(float(global_style.get("figure_width", 10)) * 100),
        "height": int(float(global_style.get("figure_height", 8)) * 100),
        "showlegend": bool(legend.get("show", True)) and position != "none",
        "legend": {
            **legend_positions.get(position, legend_positions["right"]),
            "font": plotly_text_style(config, "legend_text"),
            "borderwidth": 1 if legend.get("frame", False) else 0,
        },
    }
    return result
