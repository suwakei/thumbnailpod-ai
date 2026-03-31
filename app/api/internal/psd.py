from fastapi import APIRouter, Depends

from app.core.security import verify_internal_secret
from app.schemas.psd import PSDBuildRequest, PSDBuildResponse
from app.services.psd.builder import PSDBuilder

router = APIRouter(dependencies=[Depends(verify_internal_secret)])

_builder = PSDBuilder()


@router.post("/psd", response_model=PSDBuildResponse)
async def build_psd(req: PSDBuildRequest) -> PSDBuildResponse:
    layer_keys = [(layer.label, layer.s3_key) for layer in req.layers]
    psd_s3_key = await _builder.build_from_layers(
        job_id=req.job_id,
        user_id=req.user_id,
        layer_s3_keys=layer_keys,
        base_image_url=str(req.base_image_url),
    )
    return PSDBuildResponse(job_id=req.job_id, psd_s3_key=psd_s3_key)
