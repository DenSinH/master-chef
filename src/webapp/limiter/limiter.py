from math import ceil
from typing import Callable, Optional, Union

from sanic.exceptions import HTTPException
from sanic import Request, HTTPResponse
from sanic import Websocket


def get_client_address(request: Union[Request, Websocket]):
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0]
        if ip:
            return ip
    forwarded = request.headers.get('CF-Connecting-IP')
    if forwarded:
        return forwarded
    forwarded = request.headers.get('X-Real-IP')
    if forwarded:
        return forwarded
    forwarded = request.headers.get('Forwarded')
    if forwarded:
        ip = forwarded.split(';')[0].split('=')[1].strip()
        if ip:
            return ip
    return request.client_ip


async def default_identifier(request: Union[Request, Websocket]):
    ip = get_client_address(request)
    return ip + ":" + request.route.path


class TooManyRequests(HTTPException):

    status_code = 429


async def http_default_callback(request: Request, pexpire: int):
    """
    default callback when too many requests
    :param request:
    :param pexpire: The remaining milliseconds
    :param response:
    :return:
    """
    expire = ceil(pexpire / 1000)
    raise TooManyRequests(
        "Too Many Requests", headers={"Retry-After": str(expire)}
    )


async def ws_default_callback(ws: Websocket, pexpire: int):
    """
    default callback when too many requests
    :param ws:
    :param pexpire: The remaining milliseconds
    :return:
    """
    expire = ceil(pexpire / 1000)
    raise TooManyRequests(
        "Too Many Requests", headers={"Retry-After": str(expire)}
    )


class SanicLimiter:
    redis = None
    prefix: Optional[str] = None
    lua_sha: Optional[str] = None
    identifier: Optional[Callable] = None
    http_callback: Optional[Callable] = None
    ws_callback: Optional[Callable] = None
    lua_script = """local key = KEYS[1]
local limit = tonumber(ARGV[1])
local expire_time = ARGV[2]

local current = tonumber(redis.call('get', key) or "0")
if current > 0 then
 if current + 1 > limit then
 return redis.call("PTTL", key)
 else
        redis.call("INCR", key)
 return 0
 end
else
    redis.call("SET", key, 1, "px", expire_time)
 return 0
end"""

    @classmethod
    async def init(
        cls,
        redis,
        prefix: str = "sanic-limiter",
        identifier: Callable = default_identifier,
        http_callback: Callable = http_default_callback,
        ws_callback: Callable = ws_default_callback,
    ) -> None:
        cls.redis = redis
        cls.prefix = prefix
        cls.identifier = identifier
        cls.http_callback = http_callback
        cls.ws_callback = ws_callback
        cls.lua_sha = await redis.script_load(cls.lua_script)

    @classmethod
    async def close(cls) -> None:
        await cls.redis.close()