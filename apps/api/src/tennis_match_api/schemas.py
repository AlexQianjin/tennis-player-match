from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from tennis_match_api.ntrp import parse_ntrp

StyleName = Literal["singles", "doubles", "casual", "competitive"]
GenderName = Literal["male", "female"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Profile(CamelModel):
    id: str
    nickname: str | None = None
    avatar: str | None = None
    ntrp: float | None = None
    gender: str | None = None
    age: int | None = None
    city: str | None = None
    style: list[str] = Field(default_factory=list)
    bio: str | None = None
    credit_score: int = 0
    confirm_count: int = 0
    cancel_count: int = 0
    avg_rating: float | None = None
    rating_count: int = 0
    profile_completed: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    ntrp_update_time: str | None = None
    ntrp_next_editable_at: str | None = None
    active_request_id: str | None = None


class ProfileUpdate(CamelModel):
    nickname: str | None = None
    avatar: str | None = None
    ntrp: float | None = None
    gender: GenderName | None = None
    age: int | None = Field(default=None, ge=6, le=99)
    city: str | None = None
    style: list[StyleName] | None = None
    bio: str | None = None

    @field_validator("nickname")
    @classmethod
    def _nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text or len(text) > 20:
            raise ValueError("nickname must be 1-20 characters")
        return text

    @field_validator("avatar")
    @classmethod
    def _avatar(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("avatar is empty")
        return text

    @field_validator("ntrp")
    @classmethod
    def _ntrp(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return float(parse_ntrp(value))

    @field_validator("city")
    @classmethod
    def _city(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("city is empty")
        return text

    @field_validator("bio")
    @classmethod
    def _bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if len(text) > 500:
            raise ValueError("bio must be at most 500 characters")
        return text

    @field_validator("style")
    @classmethod
    def _style(cls, value: list[StyleName] | None) -> list[StyleName] | None:
        if value is None:
            return None
        unique: list[StyleName] = []
        for item in value:
            if item not in unique:
                unique.append(item)
        return unique


class UserPublic(CamelModel):
    id: str
    nickname: str | None = None
    avatar: str | None = None
    ntrp: float | None = None
    gender: str | None = None
    credit_score: int = 0
    avg_rating: float | None = None
    rating_count: int = 0
    age: int | None = None
    city: str | None = None
    style: list[str] = Field(default_factory=list)
    bio: str | None = None


class LoginResult(CamelModel):
    is_new_user: bool
    user_info: Profile


class CourtOut(CamelModel):
    id: str
    name: str
    district: str | None = None
    address: str
    latitude: float | None = None
    longitude: float | None = None


class CourtList(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[CourtOut] = Field(serialization_alias="list", validation_alias="list")


class HealthData(BaseModel):
    status: str
