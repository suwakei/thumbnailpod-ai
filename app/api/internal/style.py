from fastapi import APIRouter, Depends

from app.core.security import verify_internal_secret
from app.schemas.style import (
    StyleAnalyzeRequest,
    StyleAnalyzeResponse,
    StyleTrainRequest,
    StyleTrainResponse,
)
from app.services.style.analyzer import StyleAnalyzer
from app.services.style.trainer import StyleTrainer

router = APIRouter(dependencies=[Depends(verify_internal_secret)])

_analyzer = StyleAnalyzer()
_trainer = StyleTrainer()


@router.post("/analyze", response_model=StyleAnalyzeResponse)
async def analyze_style(req: StyleAnalyzeRequest) -> StyleAnalyzeResponse:
    return await _analyzer.analyze(req)


@router.post("/train", response_model=StyleTrainResponse)
async def train_style(req: StyleTrainRequest) -> StyleTrainResponse:
    """Enqueues a LoRA / style-ref training job via SQS."""
    return await _trainer.enqueue(req)
