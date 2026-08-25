"""Map a wallust 16-color palette onto a Hermes skin.

Wallust (https://codeberg.org/explosion-mental/wallust) extracts a palette
from an image (k-means in Lab, salience histogram, or ANSI-ordered). This
module does the semantic mapping Hermes needs: background, accent, status
colors, borders, syntax — not a 1:1 dump of color0–15.
"""

from __future__ import annotations

import colorsys
import re
from typing import Iterable

_HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")

# Target hues in HSV [0, 1] for semantic roles.
_HUE_ERROR = 0.00  # red
_HUE_WARN = 0.12  # orange / yellow
_HUE_OK = 0.33  # green


def normalize_hex(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if not _HEX_RE.match(raw):
        return None
    return f"#{raw[1:].upper()}"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    h = normalize_hex(value)
    if h is None:
        raise ValueError(f"not a hex color: {value!r}")
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def _srgb_channel(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _srgb_channel(r) + 0.7152 * _srgb_channel(g) + 0.0722 * _srgb_channel(b)


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    l1, l2 = luminance(a), luminance(b)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def hsv(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def from_hsv(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(round(a[0] * (1 - t) + b[0] * t)),
        int(round(a[1] * (1 - t) + b[1] * t)),
        int(round(a[2] * (1 - t) + b[2] * t)),
    )


def hue_distance(a: float, b: float) -> float:
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d)


def ensure_contrast(
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
    minimum: float = 4.5,
) -> tuple[int, int, int]:
    """Nudge HSV value until WCAG-ish contrast clears, keeping hue/sat."""
    if contrast_ratio(fg, bg) >= minimum:
        return fg
    h, s, v = hsv(fg)
    bg_l = luminance(bg)
    direction = 1.0 if bg_l < 0.45 else -1.0
    best = fg
    best_ratio = contrast_ratio(fg, bg)
    for step in range(1, 25):
        nv = max(0.0, min(1.0, v + direction * 0.04 * step))
        candidate = from_hsv(h, s, nv)
        ratio = contrast_ratio(candidate, bg)
        if ratio > best_ratio:
            best, best_ratio = candidate, ratio
        if ratio >= minimum:
            return candidate
    # Last resort: mix toward white or black.
    target = (255, 255, 255) if bg_l < 0.45 else (16, 16, 16)
    for t in (0.35, 0.5, 0.7, 0.85, 1.0):
        candidate = mix(fg, target, t)
        if contrast_ratio(candidate, bg) >= minimum:
            return candidate
    return best


def readable_on(bg: tuple[int, int, int]) -> tuple[int, int, int]:
    return (16, 16, 16) if luminance(bg) > 0.45 else (246, 246, 246)


def parse_scheme_lines(text: str) -> list[str]:
    """Extract #rrggbb colors from ``wallust run --print-scheme`` output."""
    found: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("kitty_") or " " in line and not line.startswith("#"):
            # Ignore hook status lines like ``kitty_reload: ok!``.
            if not line.startswith("#"):
                maybe = normalize_hex(line)
                if maybe:
                    found.append(maybe)
                continue
        hexed = normalize_hex(line)
        if hexed:
            found.append(hexed)
    return found


def _unique(colors: Iterable[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    seen: set[tuple[int, int, int]] = set()
    out: list[tuple[int, int, int]] = []
    for c in colors:
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def pick_accent(
    candidates: list[tuple[int, int, int]],
    bg: tuple[int, int, int],
    fg: tuple[int, int, int],
) -> tuple[int, int, int]:
    scored: list[tuple[float, tuple[int, int, int]]] = []
    for c in candidates:
        if contrast_ratio(c, bg) < 1.35:
            continue
        h, s, v = hsv(c)
        # Skip near-gray and near-background / near-foreground.
        if s < 0.12:
            continue
        if contrast_ratio(c, bg) < 1.6 and contrast_ratio(c, fg) < 1.4:
            continue
        chroma = s * (0.35 + 0.65 * (1.0 - abs(v - 0.62)))
        contrast = min(contrast_ratio(c, bg) / 4.5, 1.35)
        scored.append((chroma * contrast, c))
    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]
    # Fall back to the most saturated color, then mix toward fg.
    if candidates:
        return max(candidates, key=lambda c: hsv(c)[1])
    return fg


def pick_by_hue(
    candidates: list[tuple[int, int, int]],
    target_hue: float,
    bg: tuple[int, int, int],
    min_sat: float = 0.18,
) -> tuple[int, int, int] | None:
    best: tuple[float, tuple[int, int, int]] | None = None
    for c in candidates:
        h, s, _v = hsv(c)
        if s < min_sat:
            continue
        if contrast_ratio(c, bg) < 1.8:
            continue
        dist = hue_distance(h, target_hue)
        if dist > 0.14:
            continue
        score = (0.14 - dist) * (0.4 + s)
        if best is None or score > best[0]:
            best = (score, c)
    return None if best is None else best[1]


def synthesize(bg: tuple[int, int, int], accent: tuple[int, int, int], target_hue: float) -> tuple[int, int, int]:
    _h, s, v = hsv(accent)
    sat = max(0.45, min(0.85, s if s > 0.25 else 0.55))
    val = max(0.45, min(0.85, v if v > 0.3 else 0.7))
    return ensure_contrast(from_hsv(target_hue, sat, val), bg, 3.5)


def map_palette(
    colors16: list[str],
    *,
    background: str | None = None,
    foreground: str | None = None,
    cursor: str | None = None,
    style: str = "dark",
) -> dict[str, str]:
    """Return a Hermes ``colors:`` mapping from a wallust scheme."""
    parsed = [normalize_hex(c) for c in colors16]
    parsed = [c for c in parsed if c]
    if len(parsed) < 8:
        raise ValueError(f"need at least 8 palette colors, got {len(parsed)}")
    while len(parsed) < 16:
        parsed.append(parsed[-1])

    rgb16 = [hex_to_rgb(c) for c in parsed]
    dark = style != "light"

    bg = hex_to_rgb(background) if background and normalize_hex(background) else rgb16[0]
    fg = hex_to_rgb(foreground) if foreground and normalize_hex(foreground) else rgb16[7]
    # If polarity is inverted relative to style, swap.
    if dark and luminance(bg) > luminance(fg):
        bg, fg = fg, bg
    elif not dark and luminance(bg) < luminance(fg):
        bg, fg = fg, bg

    cur = hex_to_rgb(cursor) if cursor and normalize_hex(cursor) else fg

    pool = _unique(rgb16 + [bg, fg, cur])
    accent = pick_accent(pool, bg, fg)
    accent = ensure_contrast(accent, bg, 4.5)

    ok = pick_by_hue(pool, _HUE_OK, bg) or synthesize(bg, accent, _HUE_OK)
    warn = pick_by_hue(pool, _HUE_WARN, bg) or synthesize(bg, accent, _HUE_WARN)
    err = pick_by_hue(pool, _HUE_ERROR, bg) or synthesize(bg, accent, _HUE_ERROR)
    ok = ensure_contrast(ok, bg, 3.5)
    warn = ensure_contrast(warn, bg, 3.5)
    err = ensure_contrast(err, bg, 3.5)

    dim = mix(fg, bg, 0.42)
    border = mix(bg, fg, 0.16 if dark else 0.18)
    status_bg = mix(bg, (0, 0, 0) if dark else (255, 255, 255), 0.12)
    title = ensure_contrast(mix(accent, fg, 0.25), bg, 4.5)
    tool = accent
    thinking = mix(dim, accent, 0.35)

    # Syntax: string←accent, number←fg, keyword←border-ish / color4, comment←dim.
    keyword = rgb16[4] if contrast_ratio(rgb16[4], bg) >= 2.5 else accent
    keyword = ensure_contrast(keyword, bg, 3.0)
    number = ensure_contrast(rgb16[3] if contrast_ratio(rgb16[3], bg) >= 2.5 else fg, bg, 3.0)
    comment = dim

    selection = mix(bg, accent, 0.28 if dark else 0.18)
    menu_bg = mix(bg, fg, 0.06 if dark else 0.04)
    menu_cur = mix(bg, accent, 0.22 if dark else 0.14)

    def hx(c: tuple[int, int, int]) -> str:
        return rgb_to_hex(c)

    return {
        "background": hx(bg),
        "banner_border": hx(border),
        "banner_title": hx(title),
        "banner_accent": hx(accent),
        "banner_dim": hx(dim),
        "banner_text": hx(fg),
        "ui_accent": hx(accent),
        "ui_label": hx(mix(accent, fg, 0.35)),
        "ui_text": hx(fg),
        "ui_ok": hx(ok),
        "ui_error": hx(err),
        "ui_warn": hx(warn),
        "ui_tool": hx(tool),
        "ui_thinking": hx(thinking),
        "ui_border": hx(border),
        "diff_added": hx(mix(bg, ok, 0.22 if dark else 0.14)),
        "diff_removed": hx(mix(bg, err, 0.22 if dark else 0.14)),
        "diff_added_word": hx(ok),
        "diff_removed_word": hx(err),
        "syntax_string": hx(accent),
        "syntax_number": hx(number),
        "syntax_keyword": hx(keyword),
        "syntax_comment": hx(comment),
        "prompt": hx(fg),
        "input_rule": hx(accent),
        "response_border": hx(title),
        "status_bar_bg": hx(status_bg),
        "status_bar_text": hx(fg),
        "status_bar_strong": hx(title),
        "status_bar_dim": hx(dim),
        "status_bar_good": hx(ok),
        "status_bar_warn": hx(warn),
        "status_bar_bad": hx(mix(warn, err, 0.4)),
        "status_bar_critical": hx(err),
        "session_label": hx(title),
        "session_border": hx(border),
        "voice_status_bg": hx(status_bg),
        "selection_bg": hx(selection),
        "completion_menu_bg": hx(menu_bg),
        "completion_menu_current_bg": hx(menu_cur),
        "completion_menu_meta_bg": hx(menu_bg),
        "completion_menu_meta_current_bg": hx(menu_cur),
    }


def ansi_terminal(colors16: list[str], foreground: str, cursor: str | None = None) -> dict[str, str]:
    """xterm-ish palette for the desktop integrated terminal (no background)."""
    parsed = [normalize_hex(c) or "#000000" for c in colors16]
    while len(parsed) < 16:
        parsed.append(parsed[-1])
    fg = normalize_hex(foreground) or parsed[7]
    cur = normalize_hex(cursor) or fg
    names = [
        "black",
        "red",
        "green",
        "yellow",
        "blue",
        "magenta",
        "cyan",
        "white",
        "brightBlack",
        "brightRed",
        "brightGreen",
        "brightYellow",
        "brightBlue",
        "brightMagenta",
        "brightCyan",
        "brightWhite",
    ]
    out = {"foreground": fg, "cursor": cur, "selectionBackground": parsed[8]}
    for name, color in zip(names, parsed):
        out[name] = color
    return out
