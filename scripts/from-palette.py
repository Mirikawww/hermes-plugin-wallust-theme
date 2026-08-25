#!/usr/bin/python3
"""Consume the wallust-templated palette JSON and write a Hermes skin.

Invoked as a wallust hook after kitty (and this palette file) are rendered,
so we reuse the colors wallust already extracted — no second image parse.

Must run under system python3 (wallust hooks don't use Hermes' venv).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from colors import map_palette, normalize_hex  # noqa: E402

SKIN_NAME = "wallust"
HERMES_HOME = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def _palette_path() -> Path:
    override = os.environ.get("WALLUST_HERMES_PALETTE")
    if override:
        return Path(override).expanduser()
    return HERMES_HOME / "plugin-data" / "wallust-theme" / "palette.json"


def _yaml_escape(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _write_skin_yaml(path: Path, name: str, description: str, colors: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"name: {name}",
        f"description: {_yaml_escape(description)}",
        "colors:",
    ]
    for key, hexed in colors.items():
        lines.append(f'  {key}: "{hexed}"')
    lines.extend(
        [
            "branding:",
            '  agent_name: "Hermes Agent"',
            '  prompt_symbol: "❯"',
            '  help_header: "(^_^)? Commands"',
            'tool_prefix: "┊"',
            "",
        ]
    )
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(path)


def _write_sidecar(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _activate(name: str) -> None:
    hermes = shutil.which("hermes") or str(Path.home() / ".local" / "bin" / "hermes")
    if not os.path.isfile(hermes):
        print("wallust-theme: hermes CLI not found, skin written but not activated", file=sys.stderr)
        return
    subprocess.run(
        [hermes, "config", "set", "display.skin", name],
        check=False,
        timeout=20,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    path = _palette_path()
    if not path.is_file():
        print(f"wallust-theme: palette missing at {path}", file=sys.stderr)
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    colors16 = []
    for i in range(16):
        hexed = normalize_hex(str(data.get(f"color{i}") or ""))
        if hexed:
            colors16.append(hexed)
    if len(colors16) < 8:
        print("wallust-theme: palette too short", file=sys.stderr)
        return 1
    named: dict[str, str] = {}
    for key in ("background", "foreground", "cursor"):
        val = normalize_hex(str(data.get(key) or ""))
        if val:
            named[key] = val
    wallpaper = str(data.get("wallpaper") or "")
    mapped = map_palette(
        colors16,
        background=named.get("background"),
        foreground=named.get("foreground"),
        cursor=named.get("cursor"),
        style="dark",
    )
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    description = f"Wallust palette from {Path(wallpaper).name or 'wallpaper'} ({stamp})"
    skin_path = HERMES_HOME / "skins" / f"{SKIN_NAME}.yaml"
    _write_skin_yaml(skin_path, SKIN_NAME, description, mapped)
    sidecar = HERMES_HOME / "plugin-data" / "wallust-theme" / "last.json"
    _write_sidecar(
        sidecar,
        {
            "name": SKIN_NAME,
            "description": description,
            "colors": mapped,
            "meta": {
                "generator": "wallust-theme",
                "wallpaper": wallpaper,
                "colors16": colors16,
                "generated_at": stamp,
            },
        },
    )
    if os.environ.get("WALLUST_HERMES_NO_ACTIVATE") != "1":
        _activate(SKIN_NAME)
    print(f"wallust-theme: skin {SKIN_NAME} ← {wallpaper or path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
