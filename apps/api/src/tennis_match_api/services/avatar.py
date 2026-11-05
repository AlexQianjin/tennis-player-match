import re

from tennis_match_api.config import Settings
from tennis_match_api.errors import BizError

# cloud://<env-id>.<bucket>/<path>
_FILE_ID = re.compile(r"^cloud://(?P<env>[A-Za-z0-9_-]+)\.(?P<bucket>[^/]+)/(?P<path>[^?#]+)$")


def validate_avatar_file_id(file_id: str, settings: Settings) -> None:
    """Accept a WeChat cloud fileID for this environment under the avatar prefix.

    No object-storage credentials are required: the client uploads and we only
    check the id shape. When ``CBR_ENV_ID`` is unset (local http/dev), the env
    segment is not compared.
    """
    match = _FILE_ID.match(file_id.strip())
    if match is None:
        raise BizError(40004, "头像文件无效")
    path = match.group("path")
    prefix = settings.avatar_path_prefix
    if not prefix.endswith("/"):
        prefix = f"{prefix}/"
    if not path.startswith(prefix) or ".." in path.split("/"):
        raise BizError(40004, "头像文件无效")
    if settings.cbr_env_id is not None and match.group("env") != settings.cbr_env_id:
        raise BizError(40004, "头像文件无效")
