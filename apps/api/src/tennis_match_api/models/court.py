from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from tennis_match_api.models.base import Base


class Court(Base):
    __tablename__ = "court"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(32))
    district: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str] = mapped_column(String(255))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
