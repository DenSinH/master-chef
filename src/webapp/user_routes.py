import sanic
from sanic import Request, Sanic

from . import auth


def add_user_routes(app: Sanic):
    """Add user-related routes to app"""

    @app.get("/login")
    @app.ext.template("users/login.html")
    async def login_form(request: Request):
        """User login form"""
        return {"redirect": dict(request.query_args).get("redirect", "/")}

    @app.post("/login")
    async def login(request: Request):
        """User login post"""
        username = request.form.get("username").strip()
        password = request.form.get("password")

        if auth.login(username, password):
            redirect = dict(request.query_args).get("redirect", "/")
            response = sanic.json({"redirect": redirect})
            auth.login_user(username, request, response)
            return response

        return sanic.json({"error": "Invalid username or password"}, 401)

    @app.get("/logout")
    async def logout(request: Request):
        """User logout page"""
        response = sanic.redirect(request.app.url_for("index"))
        auth.logout_user(response)
        return response
