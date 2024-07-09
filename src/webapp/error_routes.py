import sanic
from sanic import Sanic, Request
from sanic_ext import render
import traceback
from sanic.exceptions import NotFound
from limiter import TooManyRequests
from utils.auth import CookbookAuthFailed
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
            "message": f"<p>{' '.join(exc.args)}</p>"
        }


    @app.exception(CookbookAuthFailed)
    async def auth_failed(request: Request, exc):
        """ Authentication failed default response """
        return sanic.json({
            "error": str(exc)
        }, 401)


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
