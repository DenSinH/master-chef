from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from webapp import auth
from webapp.app import templates

router = APIRouter()


@router.get("/login")
async def login_form(request: Request):
    """User login form."""
    redirect = request.query_params.get("redirect", "/")
    return templates.TemplateResponse(
        request=request,
        name="users/login.html",
        context={"redirect": redirect},
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """User login post."""
    username = username.strip()

    if auth.login(username, password):
        redirect = request.query_params.get("redirect", "/")
        response = JSONResponse(
            {"redirect": redirect},
        )
        auth.login_user(username, request, response)

        return response

    return JSONResponse(
        {"error": "Invalid username or password"},
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request):
    """User logout page."""
    response = RedirectResponse(
        url=request.app.url_path_for("index"),
        status_code=303,
    )

    auth.logout_user(response)
    return response
