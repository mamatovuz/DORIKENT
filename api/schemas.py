"""Pydantic sxemalar — kirish/chiqish validatsiyasi (2-bot bilan API contract)."""
from typing import Optional

from pydantic import BaseModel, Field


# ---------- Health ----------
class HealthResponse(BaseModel):
    success: bool = True
    service: str = "dorikent-test-bot"
    status: str = "ok"


# ---------- Tests ----------
class TestInfo(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    question_count: int
    passing_score: int
    time_per_question: int
    active: bool = True


class TestsResponse(BaseModel):
    success: bool = True
    tests: list[TestInfo]


# ---------- Assign ----------
class AssignRequest(BaseModel):
    candidate_id: int = Field(..., ge=1)
    telegram_id: int = Field(..., ge=1)
    vacancy_id: Optional[int] = Field(default=None, ge=1)
    test_id: int = Field(..., ge=1)
    external_application_id: Optional[int] = Field(default=None, ge=1)


class AssignResponse(BaseModel):
    success: bool = True
    assignment_id: int
    test_id: int
    status: str = "assigned"
    # 2-bot deep-link xabarida ishlatadi (title cache, savollar soni).
    test_title: Optional[str] = None
    question_count: Optional[int] = None
    # Qulaylik uchun — BOT_USERNAME sozlangan bo'lsa tayyor deep link.
    deep_link: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
