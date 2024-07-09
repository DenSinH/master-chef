import sanic
from sanic import Sanic, Request
from sanic_ext import render
from limiter import RateLimiter

import auth
import data.users as users


class CookbookAuthFailed(Exception):
    pass


def add_user_routes(app: Sanic):
    """ Add user-related routes to app """
    @app.get("/login")
    @app.ext.template("users/login.html")
    async def login_form(request: Request):
        """ User login form """
        return {
            "redirect": dict(request.query_args).get("redirect", "/")
        }
    

    @app.post("/login")
    async def login(request: Request):
        """ User login post """
        username = request.form.get("username").strip()
        password = request.form.get("password")

        if await users.login_user(username, password):
            redirect = dict(request.query_args).get("redirect", "/")
            response = sanic.json({
                "redirect": redirect
            })
            auth.login_user(username, request, response)
            return response
        
        return sanic.json({
            "error": "Invalid username or password"
        }, 401)


    @app.get("/register")
    @app.ext.template("users/register.html")
    async def register_form(request: Request):
        """ User registration form """
        return {}


    @app.post("/register")
    async def register(request: Request):
        """ User registration endpoint """
        username = request.form.get("username").strip()

        # username validation
        if not username:
            return sanic.json({
                "error": "Username must be specified"
            }, 400)
        if len(username) < 3:
            return sanic.json({
                "error": "Username must be at least 3 characters long"
            }, 400)
        if len(username) > 50:
            return sanic.json({
                "error": "Username must be at most 50 characters long"
            }, 400)
        
        password = request.form.get("password")

        # password validation
        if not password or len(password) < 6:
            return sanic.json({
                "error": "Password must be at least of length 6"
            }, 400)
        if (await users.get_user(username)) is not None:
            return sanic.json({
                "error": "Username already exists"
            }, 400)

        # rate limit after checks, otherwise
        # failed attempts will trigger rate limiting
        await RateLimiter(times=1, hours=1)(request)
        try:
            await users.register_user(username, password)
        except users.UserExistsException as e:
            return sanic.json({
                "error": "Username already exists"
            }, 400)
        
        # login user
        response = sanic.json({"redirect": app.url_for("registered")})
        auth.login_user(username, request, response)
        return response

    @app.get("/forgot-password")
    async def forgot_password(request: Request):
        """ Forgot password page """
        username = dict(request.query_args).get("username")
        user = await users.get_user(username)
        if user is None:
            return sanic.redirect("login")

        # password can only be reset if the admin cleared it
        if user.password is not None:
            return await render(
                "sorry.html",
                context={
                    "title": "Please wait...",
                    "message": "<p>Please ask for Dennis to clear your password so you can reset it.</p>",
                    "centering": True
                }
            )
        return await render(
            "users/forgot.html",
            context={
                "username": username
            }
        )


    @app.post("/forgot-password", ctx_limiter=RateLimiter(times=1, minutes=5))
    async def update_password(request: Request):
        """ Update password post route """
        username = dict(request.query_args).get("username")
        user = await users.get_user(username)
        if user is None:
            return sanic.json({"error": "This user does not exist, are you sure you entered the right name before hitting 'Forgot password'"}, 400)
        
        # can only update password if it has been cleared
        if user.password is not None:
            return sanic.redirect(app.url_for("forgot_password", username=username))

        newpassword = request.form.get("password")
        if not newpassword or len(newpassword) < 6:
            return sanic.json({"error": "Password must be at least length 6"}, 400)
        await users.update_user_password(username, newpassword)
        return sanic.json({"redirect": app.url_for("login_form")})


    @app.get("/registered")
    @app.ext.template("users/registered.html")
    async def registered(request: Request):
        """ Registration form landing page """
        username = auth.get_username(request) or "there"
        return {
            "username": username
        }


    @app.get("/logout")
    async def logout(request: Request):
        """ User logout page """
        response = sanic.redirect(request.app.url_for("index"))
        auth.logout_user(response)
        return response
