import sanic
from sanic import Request
import sanic_jwt
from sanic_jwt import Responses
from sanic_jwt.responses import COOKIE_OPTIONS
from sanic_jwt.validators import validate_scopes as _validate_scopes
import os

from data import users

from cookbook import DEFAULT_COLLECTION


class CookbookAuthFailed(Exception):
    pass


def _set_cookie(response, key, value, config, force_httponly=None):
    """ Setting a cookie in the response """
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
    """ Authenticate user from username / password form data """
    username = request.form.get("username").strip()
    password = request.form.get("password")

    if await users.login_user(username, password):
        scopes = ["user"]

        # if user is admin, add scope
        if username == os.environ.get("ADMIN_USER", "admin"):
            scopes.append("admin")
        
        return {
            "user_id": username,
            "scopes": scopes
        }
    raise CookbookAuthFailed("Invalid password")


async def extend_scopes(user, *args, **kwargs):
    """ Method to retrieve scopes from user, 
        needed for sanic-jwt """
    return user.get("scopes", [])


async def validate_scopes(request: Request, scopes):
    """ Override of sanic-jwt's scope validation """
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
        """ What to do on failed responses, basically:
            For GET: redirect to login
            For POST: either return unauthorized response code, or redirect to login form
                      (this distinction is needed since otherwise a failed login will loop,
                      continuously redirecting to the page itself) """
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
        """ Response after getting the jwt on successful login
            Basically, we want to redirect, though the recipe pages
            have to be handled separately """
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
