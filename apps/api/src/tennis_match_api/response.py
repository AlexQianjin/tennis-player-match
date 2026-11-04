from pydantic import BaseModel, ConfigDict


class ApiResponse[T](BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: int = 0
    message: str = "success"
    data: T | None = None
