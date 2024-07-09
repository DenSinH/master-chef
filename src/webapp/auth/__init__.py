import jwt
import datetime
from functools import wraps
from sanic import Sanic, Request, HTTPResponse
from sanic.exceptions import Unauthorized, Forbidden
import os

JWT_ALGORITHM = "HS256"
JWT_COOKIE_NAME = "CookbookToken"


def init_jwt(app: Sanic, secret=None, expiration_delta=None):
    """ Initialize JWT data by setting the secret and expiration delta options """
    assert secret is not None
    app.config.update(
        jwt_secret=secret,
        jwt_expiration_delta=expiration_delta or 30 * 60
    )
    
    @app.middleware('request')
    async def jwt_authentication(request: Request):
        """ Read userdata on request """
        token = request.cookies.get(JWT_COOKIE_NAME)
        if token:
            payload = _decode_jwt(request.app, token)
            if payload:
                request.ctx.user = payload
            else:
                # for an invalid / expired token,
                # just set the user to None
                request.ctx.user = None
        else:
            request.ctx.user = None


def _encode_jwt(app: Sanic, username: str):
    """ Encode a JWT token for the given username """
    payload = {
        "username": username,
        "scopes": ['user'],
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=app.config["jwt_expiration_delta"])
    }
    if username == os.environ.get("ADMIN_USER", "admin"):
        payload["scopes"].append("admin")

    token = jwt.encode(
        payload, 
        app.config["jwt_secret"], 
        algorithm=JWT_ALGORITHM
    )
    return token


def _decode_jwt(app: Sanic, token: str):
    """ Decode a JWT token belonging to the given app """
    try:
        payload = jwt.decode(
            token, 
            app.config["jwt_secret"], 
            algorithms=[JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    

def protected(*required_scopes):
    """ Validate scope decorator """
    def decorator(f):
        @wraps(f)
        async def decorated_function(request: Request, *args, **kwargs):
            # validate user is logged in at all
            if not request.ctx.user:
                raise Unauthorized("Token required")
            
            # validate scopes
            user_scopes = request.ctx.user.get("scopes", [])
            if not all(scope in user_scopes for scope in required_scopes):
                raise Forbidden("Insufficient scope")
            
            return await f(request, *args, **kwargs)
        return decorated_function
    return decorator


def get_username(request: Request):
    """ Helper function to retrieve username from request
    context, without having to deal with the context manually. """
    if not request.ctx.user:
        return None
    return request.ctx.user["username"]


def is_admin(request: Request):
    """ Helper function to retrieve admin role status from request
    context, without having to deal with the context manually. """
    if not request.ctx.user:
        return False
    return "admin" in request.ctx.user["scopes"]


def is_user(request: Request):
    """ Helper function to retrieve user role status from request
    context, without having to deal with the context manually. """
    if not request.ctx.user:
        return False
    return "user" in request.ctx.user["scopes"]


def login_user(username: str, request: Request, response: HTTPResponse):
    """ Login the given user by setting the JWT token cookie """
    token = _encode_jwt(request.app, username)
    response.add_cookie(
        JWT_COOKIE_NAME, token,
        httponly=True,
        samesite="Strict",
        max_age=request.app.config["jwt_expiration_delta"]
    )


def logout_user(response: HTTPResponse):
    """ Logout the user by removing the cookie """
    response.delete_cookie(JWT_COOKIE_NAME)
