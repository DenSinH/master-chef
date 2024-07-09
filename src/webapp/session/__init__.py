from sanic import Sanic, Request, HTTPResponse
import redis.asyncio as redis
import msgspec.json
import uuid
import os


class SessionDict(dict):

    def __init__(self, sid, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sid = sid
        self.modified = False

    def __setitem__(self, key, value) -> None:
        self.modified = True
        return super().__setitem__(key, value)
    
    def __delitem__(self, key) -> None:
        self.modified = True
        return super().__delitem__(key)
    
    def setdefault(self, key, default=None):
        self.modified = True
        return super().setdefault(key, default=default)

    def clear(self) -> None:
        self.modified = True
        return super().clear()

    def popitem(self) -> tuple:
        self.modified = True
        return super().popitem()
    
    def pop(self, key, **kwargs):
        self.modified = True
        return super().pop(key, **kwargs)
    
    def update(self, *args, **kwargs):
        self.modified = True
        return super().update(*args, **kwargs)


def init_session(app: Sanic, prefix="session", cookie_name="session", expiration_delta=2592000):
    _redis = redis.from_url(os.environ["REDIS_URL"], encoding="utf8")

    @app.on_request
    async def open_session(request: Request):
        """ Try to read session on request """
        sid = request.cookies.get(cookie_name, None)
        if sid is None:
            sid = uuid.uuid4().hex
            session = SessionDict(sid)
        else:
            value = await _redis.get(f"{prefix}:{sid}")
            if value is not None:
                data = msgspec.json.decode(value)
                session = SessionDict(sid, data)
            else:
                session = SessionDict(sid)
        
        # set session on request
        request.ctx.session = session

    @app.on_response
    async def save_session(request: Request, response: HTTPResponse):
        """ Save session on response """
        if not hasattr(request.ctx, "session"):
            return
        
        session: SessionDict = request.ctx.session
        if not session:
            await _redis.delete(f"{prefix}:{session.sid}")
            response.delete_cookie(cookie_name)
            return
        
        if session.modified:
            data = msgspec.json.encode(session)
            await _redis.setex(f"{prefix}:{session.sid}", expiration_delta, data)
        
        response.add_cookie(
            cookie_name, session.sid,
            httponly=True,
            max_age=expiration_delta,
            secure=True,
        )
