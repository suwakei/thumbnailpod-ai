from fastapi import APIRouter, Depends

from app.core.security import verify_internal_secret
from app.schemas.generate import GenerateRequest, GenerateResponse, GenerationEngine
from app.services.generation.dalle import DalleService
from app.services.generation.stable_diffusion import StableDiffusionService

router = APIRouter(dependencies=[Depends(verify_internal_secret)])

_dalle = DalleService()
_sdxl = StableDiffusionService()


@router.post("/generate", response_model=GenerateResponse)
async def generate_thumbnail(req: GenerateRequest) -> GenerateResponse:
    if req.engine == GenerationEngine.DALLE3:
        return await _dalle.generate(req)
    return await _sdxl.generate(req)
