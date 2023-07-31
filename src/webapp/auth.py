import sanic
import sanic_jwt.exceptions
from sanic import Request
from sanic_jwt import exceptions
from sanic_jwt import Responses
from sanic_jwt.responses import _set_cookie

from dotenv import load_dotenv; load_dotenv()
import os


async def authenticate(request, *args, **kwargs):
    if request.form.get("password") != os.environ.get("PASSWORD"):
        raise exceptions.AuthenticationFailed("Invalid password.")

    # todo: could add user data if we have multiple users
    return {}


class JwtResonses(Responses):

    @staticmethod
    def exception_response(request: Request, exception):
        if request.method == "GET":
            return sanic.redirect(request.app.url_for("login_form"))
        else:
            if isinstance(exception, sanic_jwt.exceptions.Unauthorized):
                # unauthorized response
                return sanic.json({}, 401)
            raise exception

    # basically the default, but we return a redirect
    @staticmethod
    def get_token_response(
            request, access_token, output, config, refresh_token=None
    ):
        response = sanic.redirect("/")

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