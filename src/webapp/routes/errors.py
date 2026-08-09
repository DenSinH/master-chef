import logging
import traceback

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from webapp.app import templates

logger = logging.getLogger()


def add_error_handlers(app: FastAPI):
    @app.exception_handler(HTTP_404_NOT_FOUND)
    async def notfound(request: Request, exc: HTTPException):
        return templates.TemplateResponse(
            request=request,
            name="sorry.html",
            context={
                "title": "Resource not found",
                "message": f"<p>{' '.join(map(str, exc.detail if isinstance(exc.detail, list) else [exc.detail]))}</p>",
                "centering": True,
            },
            status_code=404,
        )

    @app.exception_handler(HTTP_401_UNAUTHORIZED)
    async def unauthorized(request: Request, exc: HTTPException):
        if request.method == "GET":
            return RedirectResponse(
                url=app.url_path_for("login_form"),
                status_code=303,
            )

        return Response(status_code=401)

    @app.exception_handler(HTTP_403_FORBIDDEN)
    async def forbidden(request: Request, exc: HTTPException):
        return templates.TemplateResponse(
            request=request,
            name="sorry.html",
            context={
                "title": "You do not have access to this page",
                "message": (
                    "<p>Perhaps you tried accessing an admin-only "
                    "route as a user.</p>"
                ),
                "centering": True,
            },
            status_code=403,
        )

    @app.exception_handler(Exception)
    async def exception(request: Request, exc: Exception):
        tb = traceback.format_exc()

        logger.error(
            'Error occurred in request to "%s":\n%s',
            request.url,
            tb,
        )

        return templates.TemplateResponse(
            request=request,
            name="sorry.html",
            context={
                "title": "Whoops!",
                "message": (
                    "<p>An error occurred:</p>"
                    f'<pre style="overflow-x: auto;">{tb}</pre>'
                ),
            },
            status_code=500,
        )
