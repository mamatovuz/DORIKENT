"""API endpointlar (/api/v1/...). Barcha yozuv/o'qish db qatlamidan (parameterized)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from .auth import require_api_key
from .schemas import (
    AssignRequest, AssignResponse, HealthResponse, TestInfo, TestsResponse,
)
from . import service

log = logging.getLogger("api.routes")

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Server ishlayotganini tekshirish (auth talab qilinmaydi)."""
    return HealthResponse()


@router.get("/tests", response_model=TestsResponse,
            dependencies=[Depends(require_api_key)])
async def list_tests() -> TestsResponse:
    """Faqat aktiv testlar — 2-bot vakansiyaga test tanlashi uchun."""
    tests = await service.list_active_tests()
    return TestsResponse(tests=[TestInfo(**t) for t in tests])


@router.post("/test/assign", response_model=AssignResponse,
             dependencies=[Depends(require_api_key)])
async def assign_test(payload: AssignRequest) -> AssignResponse:
    """Nomzodga test tayinlaydi va assignment_id qaytaradi."""
    result = await service.assign_test(
        candidate_id=payload.candidate_id,
        telegram_id=payload.telegram_id,
        vacancy_id=payload.vacancy_id,
        test_id=payload.test_id,
        external_application_id=payload.external_application_id,
    )
    if not result["ok"]:
        code = (status.HTTP_404_NOT_FOUND
                if result["error"] == "test_not_found"
                else status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=code, detail=result["error"])
    return AssignResponse(
        assignment_id=result["assignment_id"],
        test_id=result["test_id"],
        status=result["status"],
        test_title=result["test_title"],
        question_count=result["question_count"],
        deep_link=result["deep_link"],
    )
