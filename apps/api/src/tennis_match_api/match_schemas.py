from datetime import date
from typing import Literal

from pydantic import Field, field_validator

from tennis_match_api.ntrp import parse_ntrp
from tennis_match_api.schemas import CamelModel, CourtOut, UserPublic

GenderName = Literal["male", "female"]
GenderPrefName = Literal["any", "male", "female"]
MatchTypeName = Literal["singles", "doubles"]
MatchStatusName = Literal["pending", "matched", "completed", "cancelled"]
ApplicationStatusName = Literal["pending", "agreed", "rejected", "cancelled"]
RoleName = Literal["publisher", "partner", "applicant", "none"]
ActionName = Literal[
    "apply",
    "withdraw",
    "viewApplications",
    "agree",
    "reject",
    "cancel",
    "arrive",
    "rate",
]


class UserBrief(CamelModel):
    id: str
    nickname: str | None = None
    avatar: str | None = None
    ntrp: float | None = None
    gender: str | None = None
    credit_score: int = 0
    avg_rating: float | None = None
    rating_count: int = 0


class PublishIn(CamelModel):
    date: date
    time_slot: str
    court_id: str
    match_type: MatchTypeName
    slots_needed: int | None = None
    expected_ntrp_min: float | None = None
    expected_ntrp_max: float | None = None
    gender_pref: GenderPrefName = "any"

    @field_validator("expected_ntrp_min", "expected_ntrp_max")
    @classmethod
    def _ntrp(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return float(parse_ntrp(value))

    @field_validator("time_slot")
    @classmethod
    def _slot(cls, value: str) -> str:
        return value.strip()


class ApplyIn(CamelModel):
    request_id: str


class WithdrawIn(CamelModel):
    application_id: str


class HandleIn(CamelModel):
    application_id: str
    action: Literal["agree", "reject"]


class ParticipantOut(CamelModel):
    user: UserBrief
    role: Literal["publisher", "partner"]
    arrived: bool
    rated: bool


class ArriveWindow(CamelModel):
    from_: str = Field(serialization_alias="from", validation_alias="from")
    to: str


class MatchSummary(CamelModel):
    id: str
    status: MatchStatusName
    match_type: MatchTypeName
    slots_needed: int
    filled_count: int
    date: str
    time_slot: str
    start_at: str
    court: CourtOut
    publisher: UserBrief
    expected_ntrp_min: float | None = None
    expected_ntrp_max: float | None = None
    gender_pref: GenderPrefName
    my_role: RoleName
    my_application_status: ApplicationStatusName | None = None
    my_application_id: str | None = None
    available_actions: list[str] = Field(default_factory=list)


class MatchDetail(CamelModel):
    id: str
    status: MatchStatusName
    match_type: MatchTypeName
    slots_needed: int
    filled_count: int
    date: str
    time_slot: str
    start_at: str
    court: CourtOut
    publisher: UserPublic
    expected_ntrp_min: float | None = None
    expected_ntrp_max: float | None = None
    gender_pref: GenderPrefName
    my_role: RoleName
    my_application_status: ApplicationStatusName | None = None
    my_application_id: str | None = None
    available_actions: list[str] = Field(default_factory=list)
    participants: list[ParticipantOut]
    pending_application_count: int | None = None
    my_ratings: list[dict[str, object]] = Field(default_factory=list)
    cancel_reason: int | None = None
    matched_time: str | None = None
    completed_time: str | None = None
    arrive_window: ArriveWindow


class RecommendItem(MatchSummary):
    rule_score: float
    llm_score: int | None = None
    final_score: float | None = None
    match_reason: str | None = None


class RecommendPage(CamelModel):
    items: list[RecommendItem] = Field(serialization_alias="list", validation_alias="list")
    page: int
    page_size: int
    total: int
    has_more: bool
    llm_applied: bool


class ApplyResult(CamelModel):
    application_id: str
    status: ApplicationStatusName
    request: MatchSummary


class WithdrawResult(CamelModel):
    status: ApplicationStatusName


class ApplicationItem(CamelModel):
    application_id: str
    applicant: UserPublic
    status: ApplicationStatusName
    apply_time: str
    llm_score: int | None = None
    match_reason: str | None = None


class ApplicationList(CamelModel):
    items: list[ApplicationItem] = Field(serialization_alias="list", validation_alias="list")


class HandleResult(CamelModel):
    application_status: ApplicationStatusName
    request: MatchSummary
