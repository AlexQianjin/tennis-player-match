from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


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
    active_request_id: str | None = None


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
