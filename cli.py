"""CLI: ``hermes wallust-theme apply|status``."""

from __future__ import annotations

import argparse
import json
import sys


def register_cli(subparser: argparse.ArgumentParser) -> None:
    subs = subparser.add_subparsers(dest="wallust_theme_action")

    apply_p = subs.add_parser("apply", help="Generate a Hermes skin from an image / current wallpaper")
    apply_p.add_argument("image", nargs="?", default="", help="Image path (default: current GNOME wallpaper)")
    apply_p.add_argument(
        "--style",
        choices=["auto", "dark", "light"],
        default="auto",
        help="Palette polarity (default: follow GNOME)",
    )
    apply_p.add_argument(
        "--no-activate",
        action="store_true",
        help="Write the skin YAML but do not switch display.skin",
    )
    apply_p.add_argument("--skin-name", default="wallust", help="Skin name (default: wallust)")
    apply_p.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    status_p = subs.add_parser("status", help="Show the last generated wallust skin")
    status_p.add_argument("--json", action="store_true", help="Print machine-readable JSON")


def wallust_theme_command(args: argparse.Namespace) -> None:
    from .engine import apply, last_status

    action = getattr(args, "wallust_theme_action", None) or "status"
    as_json = bool(getattr(args, "json", False))

    if action == "apply":
        image = (getattr(args, "image", "") or "").strip() or None
        try:
            result = apply(
                image=image,
                style=getattr(args, "style", "auto"),
                skin_name=getattr(args, "skin_name", "wallust"),
                activate=not getattr(args, "no_activate", False),
            )
        except Exception as exc:
            if as_json:
                print(json.dumps({"ok": False, "error": str(exc)}))
            else:
                print(f"✗ {exc}", file=sys.stderr)
            sys.exit(1)
        if as_json:
            print(json.dumps(result, indent=2))
            return
        print(f"✓ skin {result['skin']} ← {result['wallpaper']}")
        print(f"  style {result['style']}  palette {result.get('palette')}")
        print(f"  wrote {result['path']}")
        if result.get("activated"):
            print("  activated (live within ~1s)")
        return

    status = last_status()
    if as_json:
        print(json.dumps(status, indent=2))
        return
    print(f"wallpaper: {status.get('wallpaper') or status.get('wallpaper_error')}")
    print(f"style:     {status.get('style')}")
    print(f"skin:      {status.get('skin')}")
    print(f"wallust:   {status.get('wallust') or status.get('wallust_error')}")
    print(f"watching:  {status.get('watching')}")
    if status.get("generated_at"):
        print(f"last:      {status['generated_at']}  {status.get('description')}")
