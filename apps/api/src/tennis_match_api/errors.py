class BizError(Exception):
    def __init__(self, code: int, message: str, data: object | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    @property
    def http_status(self) -> int:
        if self.code < 1000:
            return self.code
        return self.code // 100


class DatabaseUnavailable(BizError):
    def __init__(self) -> None:
        super().__init__(50301, "服务启动中，请稍后重试")
