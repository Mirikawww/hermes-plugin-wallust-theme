"""Tool handlers for wallust-theme."""

from __future__ import annotations

import json

from .engine import apply, last_status


def wallust_theme_apply(args: dict, **kwargs) -> str:
    del kwargs
    image = (args.get("image") or "").strip() or None
    style = (args.get("style") or "auto").strip() or "auto"
    activate = args.get("activate")
    if activate is None:
        activate = True
    try:
        result = apply(image=image, style=style, activate=bool(activate))
        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})


def wallust_theme_status(args: dict, **kwargs) -> str:
    del args, kwargs
    try:
        return json.dumps(last_status())
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
