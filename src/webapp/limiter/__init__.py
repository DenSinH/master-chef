from .limiter import SanicLimiter, TooManyRequests
from .depends import RateLimiter, WebSocketRateLimiter

from sanic import Sanic, Request
import redis.asyncio as redis


async def init_limiter(app: Sanic, loop):
    @app.on_request
    async def on_request(request: Request):
        # todo: this is not very future proof
        if request.route.name == f"{app.name}.static":
            # exempt static files
            return

        if hasattr(app.ctx, "global_limiter"):
            await app.ctx.global_limiter(request)

        if hasattr(request.route.ctx, "limiter"):
            limiter = request.route.ctx.limiter
            await limiter(request)

    await SanicLimiter.init(redis.from_url("redis://redis", port=6379, encoding="utf8"))


async def close_limiter(app: Sanic, loop):
    await SanicLimiter.close()
