from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Computed,
    Date,
    Integer,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from tennis_match_api.models.base import Base


class MatchRequest(Base):
    __tablename__ = "match_request"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    publisher_id: Mapped[int] = mapped_column(BigInteger)
    court_id: Mapped[int] = mapped_column(BigInteger)
    city: Mapped[str] = mapped_column(String(32))
    match_date: Mapped[date] = mapped_column(Date)
    time_slot: Mapped[str] = mapped_column(String(11))
    start_at: Mapped[datetime] = mapped_column()
    end_at: Mapped[datetime] = mapped_column()
    match_type: Mapped[int] = mapped_column(SmallInteger)
    slots_needed: Mapped[int] = mapped_column(SmallInteger)
    filled_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    expected_ntrp_min: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    expected_ntrp_max: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    gender_pref: Mapped[int] = mapped_column(SmallInteger, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    cancel_reason: Mapped[int | None] = mapped_column(SmallInteger)
    cancelled_by: Mapped[int | None] = mapped_column(BigInteger)
    matched_time: Mapped[datetime | None] = mapped_column()
    completed_time: Mapped[datetime | None] = mapped_column()
    cancelled_time: Mapped[datetime | None] = mapped_column()
    version: Mapped[int] = mapped_column(Integer, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    active_publisher_id: Mapped[int | None] = mapped_column(
        BigInteger,
        Computed(
            "CASE WHEN status IN (1, 2) AND is_deleted = FALSE THEN publisher_id END",
            persisted=True,
        ),
    )


class Application(Base):
    __tablename__ = "application"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(BigInteger)
    applicant_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    close_reason: Mapped[int | None] = mapped_column(SmallInteger)
    handle_time: Mapped[datetime | None] = mapped_column()
    version: Mapped[int] = mapped_column(Integer, default=0)
    create_time: Mapped[datetime] = mapped_column()


class MatchParticipant(Base):
    __tablename__ = "match_participant"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    role: Mapped[int] = mapped_column(SmallInteger)
    application_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    arrived: Mapped[bool] = mapped_column(Boolean, default=False)
    arrived_time: Mapped[datetime | None] = mapped_column()
    rated: Mapped[bool] = mapped_column(Boolean, default=False)
    rated_time: Mapped[datetime | None] = mapped_column()
    left_time: Mapped[datetime | None] = mapped_column()
    version: Mapped[int] = mapped_column(Integer, default=0)
    publisher_request_id: Mapped[int | None] = mapped_column(
        BigInteger,
        Computed("CASE WHEN role = 1 THEN request_id END", persisted=True),
    )


class StateTransitionLog(Base):
    __tablename__ = "state_transition_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int] = mapped_column(BigInteger)
    request_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(32))
    from_status: Mapped[int | None] = mapped_column(SmallInteger)
    to_status: Mapped[int | None] = mapped_column(SmallInteger)
    operator_type: Mapped[int] = mapped_column(SmallInteger)
    operator_id: Mapped[int | None] = mapped_column(BigInteger)
    detail: Mapped[dict[str, object] | None] = mapped_column(JSON)
    create_time: Mapped[datetime] = mapped_column()
