import datetime
import os
import string
from pathlib import Path

import msgspec.json
from sanic import Sanic, response

from . import auth, cookbook
from .utils.compress import init_compression
from .utils.imgupload import init_client
from .utils.minifyloader import MinifyingFileSystemLoader

""" Initialize all app components """
response.BaseHTTPResponse._dumps = msgspec.json.encode

app = Sanic("master-chef", configure_logging=False)
app.ext.templating.environment.loader = MinifyingFileSystemLoader(
    Path(__file__).parent / "templates"
)


def _strftimestamp(timestamp):
    """Format timestamp to text"""
    date = datetime.datetime.fromtimestamp(timestamp).astimezone()
    return date.strftime("%Y-%m-%d")


def _addIngredient_references(step: str, recipe: cookbook.Recipe):
    """Add ingredient references to recipe step"""
    return cookbook.replace_ingredient_references(
        step, tuple(ingredient.ingredient for ingredient in recipe.ingredients)
    )


# 10MB max request size
app.config.REQUEST_MAX_SIZE = 10000000

app.ext.templating.environment.filters["strftimestamp"] = _strftimestamp
app.ext.templating.environment.filters["ingredientrefs"] = _addIngredient_references
app.ext.templating.environment.filters["capwords"] = string.capwords
app.ext.templating.environment.globals["CUISINE_TYPES"] = cookbook.CUISINE_TYPES
app.ext.templating.environment.globals["MEAL_TYPES"] = cookbook.MEAL_TYPES
app.ext.templating.environment.globals["MEAT_TYPES"] = cookbook.MEAT_TYPES
app.ext.templating.environment.globals["CARB_TYPES"] = cookbook.CARB_TYPES
app.ext.templating.environment.globals["TEMPERATURE_TYPES"] = cookbook.TEMPERATURE_TYPES
app.ext.templating.environment.globals["LANGUAGES"] = {
    "nl": "Nederlands",
    "en": "English",
}

app.config.SECRET = os.environ.get("SECRET", os.environ["PASSWORD"])
here = Path(__file__).parent
app.static("/static", here / "static")
app.static("/robots.txt", here / "static" / "robots.txt", name="robots")
app.static("/favicon.ico", here / "static" / "favicon.ico", name="favicon")

auth.init_jwt(app, app.config.SECRET, 60 * 60)

app.before_server_start(init_client)

init_compression(app)
