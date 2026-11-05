from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Computed, Integer, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from tennis_match_api.models.base import Base


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    openid: Mapped[str] = mapped_column(String(64))
    unionid: Mapped[str | None] = mapped_column(String(64))
    nickname: Mapped[str | None] = mapped_column(String(64))
    avatar_file_id: Mapped[str | None] = mapped_column(String(512))
    ntrp: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    gender: Mapped[int | None] = mapped_column(SmallInteger)
    age: Mapped[int | None] = mapped_column(SmallInteger)
    city: Mapped[str | None] = mapped_column(String(32))
    style_mask: Mapped[int] = mapped_column(SmallInteger, default=0)
    bio: Mapped[str | None] = mapped_column(String(500))
    confirm_count: Mapped[int] = mapped_column(Integer, default=0)
    cancel_count: Mapped[int] = mapped_column(Integer, default=0)
    credit_score: Mapped[int] = mapped_column(
        Integer,
        Computed("GREATEST(confirm_count - cancel_count, 0)", persisted=True),
    )
    rating_sum: Mapped[int] = mapped_column(Integer, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_rating: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        Computed(
            "CASE WHEN rating_count > 0 THEN ROUND(rating_sum / rating_count, 2) END",
            persisted=True,
        ),
    )
    # First NTRP assignment leaves this NULL so a new player can correct it once.
    ntrp_update_time: Mapped[datetime | None] = mapped_column()
    profile_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_time: Mapped[datetime | None] = mapped_column()
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=0)
