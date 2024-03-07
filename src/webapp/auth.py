import sanic
from sanic import Request
import sanic_jwt
from sanic_jwt import Responses
from sanic_jwt.responses import COOKIE_OPTIONS
from sanic_jwt.validators import validate_scopes as _validate_scopes

from data import users

from cookbook import DEFAULT_COLLECTION

from dotenv import load_dotenv; load_dotenv()
import os


class CookbookAuthFailed(Exception):
    pass


def _set_cookie(response, key, value, config, force_httponly=None):
    response.cookies.add_cookie(key, value)
    response.cookies.get_cookie(key).httponly = (
        config.cookie_httponly() if force_httponly is None else force_httponly
    )
    response.cookies.get_cookie(key).path = config.cookie_path()

    for item, option in COOKIE_OPTIONS:
        value = getattr(config, option)()
        if value:
            setattr(response.cookies.get_cookie(key), item, value)


async def authenticate(request, *args, **kwargs):
    username = request.form.get("username").strip()
    password = request.form.get("password")

    if await users.login_user(username, password):
        scopes = ["user"]
        if username == os.environ.get("ADMIN_USER", "admin"):
            scopes.append("admin")
        return {
            "user_id": username,
            "scopes": scopes
        }
    raise CookbookAuthFailed("Invalid password")


async def extend_scopes(user, *args, **kwargs):
    return user.get("scopes", [])


async def validate_scopes(request: Request, scopes):
    return await _validate_scopes(
        request,
        scopes,
        await request.app.ctx.auth.extract_scopes(request),
        override=request.app.ctx.auth.override_scope_validator,
        destructure=request.app.ctx.auth.destructure_scopes,
    )


class JwtResonses(Responses):

    @staticmethod
    def exception_response(request: Request, exception):
        if request.method == "GET":
            return sanic.redirect(request.app.url_for("login_form", redirect=request.url))
        else:
            if isinstance(exception, sanic_jwt.exceptions.Unauthorized):
                # unauthorized response
                return sanic.empty(401)
            if isinstance(exception, sanic_jwt.exceptions.AuthenticationFailed):
                return sanic.redirect(request.app.url_for("login_form"))
            raise exception

    # basically the default, but we return a redirect
    @staticmethod
    def get_token_response(
            request: Request, access_token, output, config, refresh_token=None
    ):
        redirect = dict(request.query_args).get("redirect", "/")

        # special case for recipe page, as it has a template parameter
        if redirect == "recipe":
            last_recipe = request.cookies.get("last-recipe", None)
            last_collection = request.cookies.get("last-collection", DEFAULT_COLLECTION)
            if last_recipe is None:
                redirect = request.app.url_for("collection", collection=last_collection)
            else:
                redirect = request.app.url_for("recipe", id=last_recipe, collection=last_collection)
        response = sanic.json({"redirect": redirect})

        if config.cookie_set():
            key = config.cookie_access_token_name()

            if config.cookie_split():
                signature_name = config.cookie_split_signature_name()
                header_payload, signature = access_token.rsplit(
                    ".", maxsplit=1
                )
                _set_cookie(
                    response, key, header_payload, config, force_httponly=False
                )
                _set_cookie(
                    response,
                    signature_name,
                    signature,
                    config,
                    force_httponly=True,
                )
            else:
                _set_cookie(response, key, access_token, config)

            if refresh_token and config.refresh_token_enabled():
                key = config.cookie_refresh_token_name()
                _set_cookie(response, key, refresh_token, config)

        return response
