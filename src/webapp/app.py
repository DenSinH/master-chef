from sanic import Sanic, response
from sanic_session import Session
from sanic_jwt import initialize
import msgspec.json
import datetime
import string
import os
from utils.auth import JWT_TOKEN_NAME, authenticate, extend_scopes, JwtResonses
from utils.compress import init_compression
from utils.minifyloader import MinifyingFileSystemLoader
from utils.imgupload import init_client

import cookbook
from data import init_db
from limiter import init_limiter, close_limiter, RateLimiter


""" Initialize all app components """
response.BaseHTTPResponse._dumps = msgspec.json.encode

app = Sanic(__name__, configure_logging=False)
app.ext.templating.environment.loader = MinifyingFileSystemLoader(
    "templates/"
)

def _strftimestamp(timestamp):
    """ Format timestamp to text """
    date = datetime.datetime.fromtimestamp(timestamp)
    return date.strftime("%Y-%m-%d")


def _add_ingredient_references(step: str, recipe: cookbook.Recipe):
    """ Add ingredient references to recipe step """
    return cookbook.replace_ingredient_references(
        step, 
        tuple(ingredient.ingredient for ingredient in recipe.ingredients)
    )


# 10MB max request size
app.config.REQUEST_MAX_SIZE = 10000000

app.ext.templating.environment.filters["strftimestamp"] = _strftimestamp
app.ext.templating.environment.filters["ingredientrefs"] = _add_ingredient_references
app.ext.templating.environment.filters["capwords"] = string.capwords
app.ext.templating.environment.globals["CUISINE_TYPES"] = cookbook.CUISINE_TYPES
app.ext.templating.environment.globals["MEAL_TYPES"] = cookbook.MEAL_TYPES
app.ext.templating.environment.globals["MEAT_TYPES"] = cookbook.MEAT_TYPES
app.ext.templating.environment.globals["CARB_TYPES"] = cookbook.CARB_TYPES
app.ext.templating.environment.globals["TEMPERATURE_TYPES"] = cookbook.TEMPERATURE_TYPES
app.ext.templating.environment.globals["LANGUAGES"] = {
    "nl": "Nederlands",
    "en": "English"
}

app.config.SECRET = os.environ.get("SECRET", os.environ["PASSWORD"])
app.static("/static", "./static")
app.static("/robots.txt", "./static/robots.txt", name="robots")
app.static("/favicon.ico", "./static/favicon.ico", name="favicon")

initialize(
    app,
    authenticate=authenticate,
    cookie_set=True,
    cookie_access_token_name=JWT_TOKEN_NAME,
    url_prefix="/login",  # post to authenticate function from .auth
    login_redirect_url="/login",
    secret=app.config.SECRET,
    responses_class=JwtResonses,
    expiration_delta=60 * 60,
    algorithm="HS256",
    add_scopes_to_payload=extend_scopes,
    scopes_enabled=True,
)
_session = Session(app)
app.before_server_start(init_db)
app.before_server_start(init_client)

# global rate limit of 5 requests per second
app.ctx.global_limiter = RateLimiter(times=5, seconds=1)
app.before_server_start(init_limiter)
app.after_server_stop(close_limiter)

init_compression(app)
