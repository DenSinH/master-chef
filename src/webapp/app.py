import datetime
import os
import string
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from jinja2 import FileSystemLoader
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import FileResponse
from starlette.templating import Jinja2Templates

from . import cookbook
from .utils import s3

HERE = Path(__file__).parent

app = FastAPI(
    title="master-chef",
)

# With GZipMiddleware we don't really need a minifying template loader
# any whitespace will be properly compressed anyway
app.add_middleware(
    GZipMiddleware,
    minimum_size=500,
)

templates = Jinja2Templates(
    directory=HERE / "templates",
)
templates.env.loader = FileSystemLoader(HERE / "templates")


def _strftime(dt: datetime.datetime):
    """Format timestamp to text."""
    return dt.strftime("%Y-%m-%d")


def _strftimestamp(timestamp: float):
    """Format timestamp to text."""
    dt = datetime.datetime.fromtimestamp(timestamp).astimezone()
    return _strftime(dt)


def _add_ingredient_references(step: str, recipe: cookbook.Recipe):
    """Add ingredient references to recipe step."""
    return cookbook.replace_ingredient_references(
        step,
        tuple(ingredient.ingredient for ingredient in recipe.ingredients),
    )


templates.env.filters["strftimestamp"] = _strftimestamp
templates.env.filters["strftime"] = _strftime
templates.env.filters["ingredientrefs"] = _add_ingredient_references
templates.env.filters["capwords"] = string.capwords

templates.env.globals["CuisineType"] = cookbook.CuisineType
templates.env.globals["MealType"] = cookbook.MealType
templates.env.globals["MeatType"] = cookbook.MeatType
templates.env.globals["CarbType"] = cookbook.CarbType
templates.env.globals["TemparatureType"] = cookbook.TemperatureType
templates.env.globals["LANGUAGES"] = {
    "nl": "Nederlands",
    "en": "English",
}


app.mount(
    "/static",
    StaticFiles(directory=HERE / "static"),
    name="static",
)

# initialize JWT settings
app.state.secret = os.environ["SECRET"]


@app.get("/robots.txt", name="robots")
async def robots():
    return FileResponse(HERE / "static" / "robots.txt")


@app.get("/favicon.ico", name="favicon")
async def favicon():
    return FileResponse(HERE / "static" / "favicon.ico")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with s3.client_lifetime():
            yield
    finally:
        pass
