from __future__ import annotations

from fastapi import APIRouter

from app.schemas import ScaleConfigIn, ScaleConfigOut
from app.services.scales import load_scales, save_scales

router = APIRouter(prefix="/api/scales", tags=["scales"])


@router.get("", response_model=ScaleConfigOut)
def get_scale_config() -> ScaleConfigOut:
    return ScaleConfigOut(scales=load_scales())


@router.put("", response_model=ScaleConfigOut)
def update_scale_config(payload: ScaleConfigIn) -> ScaleConfigOut:
    save_scales(payload.scales)
    return ScaleConfigOut(scales=payload.scales)
