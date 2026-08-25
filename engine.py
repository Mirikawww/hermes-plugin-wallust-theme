"""Run wallust against the current wallpaper and write a Hermes skin.

Uses the local ``wallust`` binary (same algorithm as
https://codeberg.org/explosion-mental/wallust) so the palette matches
kitty / other wallust templates already on this machine.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

try:
    from .colors import ansi_terminal, map_palette, normalize_hex, parse_scheme_lines
except ImportError:  # dashboard plugin_api loads this as a loose module
    from colors import ansi_terminal, map_palette, normalize_hex, parse_scheme_lines

PLUGIN_ID = "wallust-theme"
SKIN_DEFAULT = "wallust"
WALLUST_BIN_CANDIDATES = (
    os.path.expanduser("~/.local/bin/wallust"),
    "wallust",
)

# Match the user's existing wallust-from-gnome-wallpaper fallbacks.
_PALETTE_FALLBACKS = ("", "kmeans", "ansi")


def _plugin_dir() -> Path:
    return Path(__file__).resolve().parent


def hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def data_dir() -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir

        return plugin_data_dir(PLUGIN_ID)
    except Exception:
        root = hermes_home() / "plugin-data" / PLUGIN_ID
        root.mkdir(parents=True, exist_ok=True)
        return root


def wallust_bin() -> str:
    for candidate in WALLUST_BIN_CANDIDATES:
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        found = shutil.which(candidate)
        if found:
            return found
    raise FileNotFoundError(
        "wallust not found. Install it from https://codeberg.org/explosion-mental/wallust "
        "or put the binary on PATH / ~/.local/bin/wallust."
    )


def _gsettings(schema: str, key: str) -> str:
    try:
        r = subprocess.run(
            ["gsettings", "get", schema, key],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if r.returncode != 0:
        return ""
    raw = (r.stdout or "").strip()
    if raw.startswith("'") and raw.endswith("'"):
        raw = raw[1:-1]
    elif raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    return raw


def gnome_style() -> str:
    scheme = _gsettings("org.gnome.desktop.interface", "color-scheme")
    return "light" if scheme == "prefer-light" else "dark"


def wallpaper_path() -> str:
    scheme = _gsettings("org.gnome.desktop.interface", "color-scheme")
    primary = "picture-uri-dark" if scheme == "prefer-dark" else "picture-uri"
    uri = _gsettings("org.gnome.desktop.background", primary) or _gsettings(
        "org.gnome.desktop.background", "picture-uri"
    )
    if not uri:
        fallback = Path.home() / ".config" / "background"
        if fallback.is_file():
            return str(fallback)
        raise FileNotFoundError("no GNOME wallpaper URI")
    if uri.startswith("file://"):
        path = unquote(urlparse(uri).path)
    else:
        path = uri
    if not os.path.isfile(path):
        raise FileNotFoundError(f"wallpaper file missing: {path}")
    return path


def resolve_style(requested: str | None) -> str:
    req = (requested or "auto").strip().lower()
    if req in {"dark", "light"}:
        return req
    return gnome_style()


def run_wallust(
    image: str,
    style: str,
    *,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    binary = wallust_bin()
    extra = list(extra_args or [])
    env = os.environ.copy()
    env.setdefault("HOME", str(Path.home()))
    last_err = ""
    last_rc = 1
    for palette in _PALETTE_FALLBACKS:
        cmd = [binary, "run", "-S", style, "--print-scheme", "-s", "-T", "--no-hooks"]
        if palette:
            cmd.extend(["-p", palette])
        cmd.extend(extra)
        cmd.append(image)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            check=False,
        )
        last_rc = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        colors = parse_scheme_lines(stdout)
        if proc.returncode == 0 and len(colors) >= 8:
            return {
                "ok": True,
                "colors16": colors,
                "command": cmd,
                "palette": palette or "config",
                "stdout": stdout,
                "stderr": stderr,
            }
        last_err = (stderr or stdout or f"wallust exit {proc.returncode}").strip()
    raise RuntimeError(f"wallust failed (rc={last_rc}): {last_err[:500]}")


def _read_wallust_json_cache() -> dict[str, str]:
    """Best-effort named colors from the latest wallust cache JSON."""
    cache = Path.home() / ".cache" / "wallust"
    if not cache.is_dir():
        return {}
    newest: tuple[float, Path] | None = None
    try:
        for child in cache.iterdir():
            if not child.is_dir():
                continue
            for f in child.iterdir():
                if f.suffix.lower() == ".json" or f.name.endswith(".json"):
                    m = f.stat().st_mtime
                    if newest is None or m > newest[0]:
                        newest = (m, f)
    except OSError:
        return {}
    if newest is None:
        # Some wallust versions dump a JSON blob as the last file in the cache dir.
        return {}
    try:
        data = json.loads(newest[1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("background", "foreground", "cursor"):
        val = normalize_hex(str(data.get(key) or ""))
        if val:
            out[key] = val
    return out


def build_skin_document(
    colors16: list[str],
    *,
    style: str,
    wallpaper: str,
    named: dict[str, str] | None = None,
    skin_name: str = SKIN_DEFAULT,
) -> dict[str, Any]:
    named = named or {}
    mapped = map_palette(
        colors16,
        background=named.get("background"),
        foreground=named.get("foreground"),
        cursor=named.get("cursor"),
        style=style,
    )
    terminal = ansi_terminal(
        colors16,
        foreground=mapped["ui_text"],
        cursor=named.get("cursor") or mapped["ui_text"],
    )
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    rel = wallpaper
    try:
        rel = str(Path(wallpaper))
    except Exception:
        pass
    return {
        "name": skin_name,
        "description": f"Wallust palette from {Path(rel).name} ({style}, {stamp})",
        "colors": mapped,
        "branding": {
            "agent_name": "Hermes Agent",
            "prompt_symbol": "❯",
            "help_header": "(^_^)? Commands",
        },
        "tool_prefix": "┊",
        "meta": {
            "generator": PLUGIN_ID,
            "wallpaper": wallpaper,
            "style": style,
            "colors16": colors16,
            "terminal": terminal,
            "generated_at": stamp,
        },
    }


def write_skin(doc: dict[str, Any], *, skin_name: str) -> Path:
    from utils import atomic_yaml_write

    path = hermes_home() / "skins" / f"{skin_name}.yaml"
    # Drop runtime-only meta from the YAML Hermes actually loads; keep a
    # comment-free sidecar JSON next to plugin-data for the desktop pane.
    yaml_doc = {
        "name": doc["name"],
        "description": doc["description"],
        "colors": doc["colors"],
        "branding": doc.get("branding") or {},
        "tool_prefix": doc.get("tool_prefix", "┊"),
    }
    atomic_yaml_write(path, yaml_doc, sort_keys=False)
    sidecar = data_dir() / "last.json"
    sidecar.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path


def activate_skin(skin_name: str) -> None:
    from hermes_cli.config import config_command
    import argparse

    config_command(
        argparse.Namespace(
            config_command="set",
            key="display.skin",
            value=skin_name,
            force=True,
        )
    )


def apply(
    *,
    image: str | None = None,
    style: str | None = None,
    skin_name: str | None = None,
    activate: bool = True,
) -> dict[str, Any]:
    wallpaper = image or wallpaper_path()
    resolved_style = resolve_style(style)
    name = (skin_name or SKIN_DEFAULT).strip() or SKIN_DEFAULT
    result = run_wallust(wallpaper, resolved_style)
    named = _read_wallust_json_cache()
    if "background" not in named and result["colors16"]:
        named["background"] = result["colors16"][0]
    if "foreground" not in named and len(result["colors16"]) > 7:
        named["foreground"] = result["colors16"][7]
    doc = build_skin_document(
        result["colors16"],
        style=resolved_style,
        wallpaper=wallpaper,
        named=named,
        skin_name=name,
    )
    path = write_skin(doc, skin_name=name)
    if activate:
        activate_skin(name)
    return {
        "ok": True,
        "skin": name,
        "path": str(path),
        "wallpaper": wallpaper,
        "style": resolved_style,
        "palette": result.get("palette"),
        "colors": doc["colors"],
        "colors16": result["colors16"],
        "description": doc["description"],
        "activated": activate,
    }


def last_status() -> dict[str, Any]:
    sidecar = data_dir() / "last.json"
    payload: dict[str, Any] = {
        "ok": True,
        "wallpaper": None,
        "style": None,
        "skin": SKIN_DEFAULT,
        "colors": None,
        "colors16": None,
        "description": None,
        "generated_at": None,
        "wallust": None,
        "watching": _watcher_alive(),
    }
    try:
        payload["wallpaper"] = wallpaper_path()
    except Exception as exc:
        payload["wallpaper_error"] = str(exc)
    try:
        payload["style"] = gnome_style()
    except Exception:
        payload["style"] = "dark"
    try:
        payload["wallust"] = wallust_bin()
    except Exception as exc:
        payload["wallust"] = None
        payload["wallust_error"] = str(exc)
    if sidecar.is_file():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            payload["skin"] = data.get("name") or SKIN_DEFAULT
            payload["colors"] = data.get("colors")
            payload["colors16"] = (data.get("meta") or {}).get("colors16")
            payload["description"] = data.get("description")
            payload["generated_at"] = (data.get("meta") or {}).get("generated_at")
            payload["last_wallpaper"] = (data.get("meta") or {}).get("wallpaper")
            payload["last_style"] = (data.get("meta") or {}).get("style")
        except (OSError, json.JSONDecodeError):
            pass
    return payload


# ---------------------------------------------------------------------------
# In-process GNOME wallpaper watcher (complements the user's systemd service)
# ---------------------------------------------------------------------------

_watch_lock = threading.Lock()
_watch_thread: threading.Thread | None = None
_watch_stop = threading.Event()
_last_identity: tuple[str, str] | None = None


def _watcher_alive() -> bool:
    t = _watch_thread
    return bool(t and t.is_alive())


def wallpaper_identity() -> tuple[str, str]:
    scheme = _gsettings("org.gnome.desktop.interface", "color-scheme")
    key = "picture-uri-dark" if scheme == "prefer-dark" else "picture-uri"
    uri = _gsettings("org.gnome.desktop.background", key) or _gsettings(
        "org.gnome.desktop.background", "picture-uri"
    )
    return scheme, uri


def _watch_loop(style: str | None, skin_name: str) -> None:
    global _last_identity
    # Poll gsettings. Cheap, no gi/GLib required inside Hermes' venv.
    while not _watch_stop.wait(1.5):
        try:
            ident = wallpaper_identity()
        except Exception:
            continue
        if ident == _last_identity:
            continue
        _last_identity = ident
        try:
            apply(style=style, skin_name=skin_name, activate=True)
        except Exception:
            # Watcher must never kill the agent process.
            continue


def start_watcher(*, style: str | None = "auto", skin_name: str = SKIN_DEFAULT) -> bool:
    global _watch_thread, _last_identity
    with _watch_lock:
        if _watcher_alive():
            return False
        _watch_stop.clear()
        try:
            _last_identity = wallpaper_identity()
        except Exception:
            pass
        t = threading.Thread(
            target=_watch_loop,
            args=(style, skin_name),
            name="wallust-theme-watch",
            daemon=True,
        )
        _watch_thread = t
        t.start()
        return True


def stop_watcher() -> None:
    _watch_stop.set()
