"""wallust-theme plugin — wallpaper → Hermes skin via wallust.

Uses the local ``wallust`` binary (k-means / salience / ANSI palettes, same
algorithm as https://codeberg.org/explosion-mental/wallust) to extract a
16-color scheme from the current GNOME wallpaper (or any image), maps it
onto a Hermes skin YAML, and activates it so CLI / TUI / desktop repaint
live.

Complements the user's existing ``wallust-wallpaper-watch`` systemd unit
(which already restyles kitty): this plugin is the Hermes-side consumer.
"""

from __future__ import annotations

import logging

from .cli import register_cli, wallust_theme_command
from .engine import apply, start_watcher
from .schemas import APPLY, STATUS
from .tools import wallust_theme_apply, wallust_theme_status

logger = logging.getLogger(__name__)


def _setting(ctx, key: str, default):
    try:
        value = ctx.get_config(key, default=default)
    except Exception:
        return default
    return default if value is None else value


def register(ctx) -> None:
    ctx.register_tool(
        name="wallust_theme_apply",
        toolset="wallust_theme",
        schema=APPLY,
        handler=wallust_theme_apply,
    )
    ctx.register_tool(
        name="wallust_theme_status",
        toolset="wallust_theme",
        schema=STATUS,
        handler=wallust_theme_status,
    )
    ctx.register_command(
        "wallust-theme",
        handler=_handle_slash,
        description="Apply a wallust palette from the wallpaper to Hermes.",
        args_hint="[apply|status] [image]",
    )
    ctx.register_cli_command(
        name="wallust-theme",
        help="Generate a Hermes skin from the wallpaper via wallust",
        setup_fn=register_cli,
        handler_fn=wallust_theme_command,
        description=(
            "Extract a 16-color palette from an image with wallust and write "
            "it as a Hermes skin (CLI + TUI + desktop)."
        ),
    )

    # Wallpaper changes already restyle Hermes via the wallust hook
    # (`hermes_skin` in ~/.config/wallust/wallust.toml). Do not extract on
    # every plugin load — that would re-apply during `hermes wallust-theme
    # status`, doctor, etc. auto_watch is opt-in for machines without the
    # systemd wallpaper unit.
    auto_watch = bool(_setting(ctx, "auto_watch", False))
    style = str(_setting(ctx, "style", "auto") or "auto")
    skin_name = str(_setting(ctx, "skin_name", "wallust") or "wallust")

    if auto_watch:
        start_watcher(style=style, skin_name=skin_name)


def _handle_slash(raw_args: str) -> str:
    parts = (raw_args or "").strip().split()
    sub = parts[0].lower() if parts else "apply"
    if sub in {"status", "show"}:
        from .engine import last_status

        s = last_status()
        lines = [
            f"wallpaper: {s.get('wallpaper') or s.get('wallpaper_error')}",
            f"style:     {s.get('style')}",
            f"skin:      {s.get('skin')}",
            f"watching:  {s.get('watching')}",
        ]
        if s.get("generated_at"):
            lines.append(f"last:      {s['generated_at']}")
            if s.get("description"):
                lines.append(s["description"])
        return "\n".join(lines)
    if sub in {"apply", "run", "refresh"}:
        image = " ".join(parts[1:]).strip() or None
        try:
            result = apply(image=image, activate=True)
        except Exception as exc:
            return f"wallust-theme failed: {exc}"
        return (
            f"Applied {result['skin']} from {result['wallpaper']} "
            f"({result['style']}, palette {result.get('palette')})."
        )
    return "Usage: /wallust-theme [apply|status] [image]"
