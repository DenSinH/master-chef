import sanic
from sanic import Sanic, Request
from sanic_ext import render
import traceback
from sanic.exceptions import NotFound, Unauthorized, Forbidden
from limiter import TooManyRequests
import logging 

logger = logging.getLogger(__name__)


def add_error_routes(app: Sanic):
    """ Add error-related routes to app """

    @app.exception(NotFound)
    @app.ext.template("sorry.html")
    async def notfound(request: Request, exc):
        """ 404 page """
        return {
            "title": "Resource not found",
            "message": f"<p>{' '.join(exc.args)}</p>",
            "centering": True,
        }


    @app.exception(Unauthorized)
    async def unauthorized(request: Request, exc: Unauthorized):
        """ Unauthorized request, redirect to login for GET,
        For POST (or other methods), just return a 401 unauthorized status code. """
        if request.method == "GET":
            return sanic.redirect(request.app.url_for("login_form", redirect=request.url))
        return sanic.empty(exc.status_code)


    @app.exception(Forbidden)
    @app.ext.template("sorry.html")
    async def forbidden(request: Request, exc: Forbidden):
        """ Insufficient scope """
        return {
            "title": "You do not have access to this page",
            "message": "<p>Perhaps you tried accessing an admin-only route as a user.</p>",
            "centering": True,
        }


    @app.exception(TooManyRequests)
    async def too_many_requests(request: Request, exc: TooManyRequests):
        """ Too many requests default response """
        return sanic.json({
            "error": "Too many requests"
        }, exc.status_code)


    @app.exception(Exception)
    async def exception(request: Request, exc):
        """ Stacktrace page """
        tb = traceback.format_exc()
        logger.error(f"Error occurred in request to \"{request.url}\":\n{tb}")
        return await render(
            "sorry.html",
            500,
            context={
                "title": "Whoops!",
                "message": "<p>An error occurred:</p>"
                          f"<pre>{tb}</pre>"
            }
        )
