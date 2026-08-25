"""wallust-theme dashboard / desktop backend.

Mounted at /api/plugins/wallust-theme/ by the dashboard plugin system.
The desktop plugin talks to the same namespace via ctx.rest.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Engine lives one directory up from dashboard/.
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine import apply, last_status, start_watcher, stop_watcher  # noqa: E402

log = logging.getLogger(__name__)

router = APIRouter()


class ApplyBody(BaseModel):
    image: Optional[str] = Field(default=None, description="Image path; omit for current wallpaper")
    style: Optional[str] = Field(default="auto", description="auto | dark | light")
    activate: bool = True
    skin_name: Optional[str] = None


@router.get("/status")
async def status():
    try:
        return last_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/apply")
async def apply_theme(body: ApplyBody):
    try:
        return apply(
            image=(body.image or None),
            style=body.style or "auto",
            skin_name=body.skin_name or "wallust",
            activate=body.activate,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("wallust apply failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/watch")
async def watch(enable: bool = True):
    if enable:
        started = start_watcher()
        return {"ok": True, "watching": True, "started": started}
    stop_watcher()
    return {"ok": True, "watching": False}
