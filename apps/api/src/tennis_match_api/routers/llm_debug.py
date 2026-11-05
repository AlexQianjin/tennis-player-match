"""Internal score routes. Registered only when LLM_DEBUG_API_ENABLED=true."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock, get_clock
from tennis_match_api.config import Settings, get_settings
from tennis_match_api.deps import get_session
from tennis_match_api.errors import BizError
from tennis_match_api.response import ApiResponse
from tennis_match_api.services.llm.client import LLMClient, get_llm_client
from tennis_match_api.services.llm.scoring import debug_score

router = APIRouter(prefix="/api/v1/llm/match", tags=["llm"])


class PersonInfo(BaseModel):
    ntrp: float | None = None
    style: list[str] | None = None
    bio: str | None = None
    expectedNtrpMin: float | None = None
    expectedNtrpMax: float | None = None
    genderPref: str | None = None


class ScoreIn(BaseModel):
    publisherId: str
    candidateId: str
    requestId: str | None = None
    publisherInfo: PersonInfo | None = None
    candidateInfo: PersonInfo | None = None
    useCache: bool = True


class CandidateIn(BaseModel):
    candidateId: str
    candidateInfo: PersonInfo | None = None


class BatchScoreIn(BaseModel):
    publisherId: str
    publisherInfo: PersonInfo | None = None
    candidates: list[CandidateIn] = Field(min_length=1, max_length=20)
    requestId: str | None = None
    useCache: bool = True


def _require_token(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.internal_api_token.get_secret_value() if settings.internal_api_token else ""
    if not expected or x_internal_token != expected:
        raise BizError(401, "缺少或不可信的内部凭证")


@router.post("/score", response_model=ApiResponse[dict])
async def score(
    payload: ScoreIn,
    _: Annotated[None, Depends(_require_token)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    llm: Annotated[LLMClient | None, Depends(get_llm_client)],
) -> ApiResponse[dict]:
    data = await debug_score(
        session,
        settings,
        clock,
        llm,
        publisher_id=payload.publisherId,
        candidate_ids=[payload.candidateId],
        request_id=payload.requestId,
        use_cache=payload.useCache,
    )
    first = data["results"][0] if isinstance(data["results"], list) and data["results"] else {}
    return ApiResponse(data=first if isinstance(first, dict) else {})


@router.post("/batch-score", response_model=ApiResponse[dict])
async def batch_score(
    payload: BatchScoreIn,
    _: Annotated[None, Depends(_require_token)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    llm: Annotated[LLMClient | None, Depends(get_llm_client)],
) -> ApiResponse[dict]:
    data = await debug_score(
        session,
        settings,
        clock,
        llm,
        publisher_id=payload.publisherId,
        candidate_ids=[item.candidateId for item in payload.candidates],
        request_id=payload.requestId,
        use_cache=payload.useCache,
    )
    return ApiResponse(data=data)
