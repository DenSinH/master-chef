from typing import Annotated, Callable, Optional

import redis as pyredis
from sanic import Request, Websocket
from pydantic import Field
from .limiter import SanicLimiter


class RateLimiter:
    def __init__(
        self,
        times: Annotated[int, Field(ge=0)] = 1,
        milliseconds: Annotated[int, Field(ge=-1)] = 0,
        seconds: Annotated[int, Field(ge=-1)] = 0,
        minutes: Annotated[int, Field(ge=-1)] = 0,
        hours: Annotated[int, Field(ge=-1)] = 0,
        identifier: Optional[Callable] = None,
        callback: Optional[Callable] = None,
    ):
        self.times = times
        self.milliseconds = milliseconds + 1000 * seconds + 60000 * minutes + 3600000 * hours
        self.identifier = identifier
        self.callback = callback
        self._child = None

    def __and__(self, other: 'RateLimiter'):
        self._child = other
        return self

    async def _check(self, key):
        redis = SanicLimiter.redis
        pexpire = await redis.evalsha(
            SanicLimiter.lua_sha, 1, key, str(self.times), str(self.milliseconds)
        )
        return pexpire

    async def __call__(self, request: Request):
        if not SanicLimiter.redis:
            raise Exception("You must call SanicLimiter.init in startup event of sanic!")

        # moved here because constructor run before app startup
        identifier = self.identifier or SanicLimiter.identifier
        callback = self.callback or SanicLimiter.http_callback
        rate_key = await identifier(request)
        print(rate_key, request.route.name)
        key = f"{SanicLimiter.prefix}:{rate_key}:{request.route.name}:{self.times}:{self.milliseconds}"
        try:
            pexpire = await self._check(key)
        except pyredis.exceptions.NoScriptError:
            SanicLimiter.lua_sha = await SanicLimiter.redis.script_load(
                SanicLimiter.lua_script
            )
            pexpire = await self._check(key)
        if pexpire != 0:
            return await callback(request, pexpire)
        if self._child is not None:
            return await self._child(request)


class WebSocketRateLimiter(RateLimiter):
    async def __call__(self, ws: Websocket, context_key=""):
        if not SanicLimiter.redis:
            raise Exception("You must call FastAPILimiter.init in startup event of fastapi!")
        identifier = self.identifier or SanicLimiter.identifier
        rate_key = await identifier(ws)
        key = f"{SanicLimiter.prefix}:ws:{rate_key}:{context_key}"
        pexpire = await self._check(key)
        callback = self.callback or SanicLimiter.ws_callback
        if pexpire != 0:
            return await callback(ws, pexpire)
