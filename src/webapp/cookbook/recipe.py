import hashlib
from enum import StrEnum
from functools import partial
from typing import Annotated, Any, Literal, TypeVar, overload

import msgspec.json
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from thefuzz import process

from .meta import (
    CarbType,
    CuisineType,
    Language,
    MealType,
    MeatType,
    TemperatureType,
)

_E = TypeVar("_E", bound="StrEnum")


def _to_str_list(value: list) -> list[str]:
    """Friendly cast to list of strings, ensures single-keyed dictionaries will get converted
    to a list of strings with their values."""
    result = []
    for v in value:
        if isinstance(v, dict) and len(v) == 1:
            result.append(next(iter(v.values())))
        else:
            result.append(str(v))
    return result


def _friendly_optional(value: Any) -> Any | None:
    """Friendly optional cast, from string null / None values"""
    if isinstance(value, str) and value.lower() in ("null", "none", ""):
        return None
    return value


def _friendly_from_list(value: Any) -> Any:
    """Friendly cast from list, for example from form submissions."""
    if isinstance(value, list | tuple):
        if len(value) == 1:
            return value[0]
        if len(value) == 0:
            return None

    # no cast possible
    return value


@overload
def _fuzzy_enum_match(
    enum_type: type[_E],
    value: str,
    optional: Literal[False] = False,
) -> _E: ...


@overload
def _fuzzy_enum_match(
    enum_type: type[_E],
    value: str,
    optional: Literal[True],
) -> _E | None: ...


def _fuzzy_enum_match(
    enum_type: type[_E], value: str, optional: bool = False
) -> _E | None:
    """Fuzzy match allowed enum values"""
    if value is None and optional:
        return None

    allowed_values: list[str] = [val.value for val in enum_type]

    # strict match
    if value in allowed_values:
        return enum_type(value)

    match, score = process.extractOne(value, allowed_values)[0]
    if score < 70:
        if optional:
            return None
        msg = f"Invalid value {value!r}; expected one of {allowed_values}"
        raise ValueError(msg)
    return enum_type(match)


FriendlyOptionalString = Annotated[
    str | None,
    BeforeValidator(_friendly_optional),
    BeforeValidator(_friendly_from_list),
]
FriendlyString = Annotated[
    str,
    BeforeValidator(_friendly_from_list),
]
FriendlyOptionalInt = Annotated[
    int | None,
    BeforeValidator(_friendly_optional),
    BeforeValidator(_friendly_from_list),
]


def FriendlyOptionalEnum(enum_type: type[_E]) -> type[_E]:
    return Annotated[
        enum_type | None,
        BeforeValidator(partial(_fuzzy_enum_match, enum_type, optional=True)),
        BeforeValidator(_friendly_optional),
        BeforeValidator(_friendly_from_list),
    ]


def FriendlyEnum(enum_type: type[_E]) -> type[_E]:
    return Annotated[
        enum_type,
        BeforeValidator(partial(_fuzzy_enum_match, enum_type)),
        BeforeValidator(_friendly_from_list),
    ]


class RecipeDataBase(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        # don't want to be too strict
        extra="allow",
    )


class RecipeMeta(BaseModel):
    language: FriendlyOptionalEnum(Language) = Field(
        default=None,
        description="Language in which this recipe is written",
    )
    meal_type: FriendlyEnum(MealType) = Field(
        default=MealType.OTHER,
        description="Which meal in the day this recipe is for",
    )
    meat_type: list[FriendlyEnum(MeatType)] = Field(
        default_factory=lambda: [MeatType.OTHER],
        description="Type of meat used in this recipe",
        max_length=2,
    )
    carb_type: list[FriendlyEnum(CarbType)] = Field(
        default_factory=lambda: [CarbType.OTHER],
        description="Type of carbs used in this recipe",
        max_length=2,
    )
    cuisine: FriendlyOptionalEnum(CuisineType) = Field(
        default=None,
        description="Which cuisine this recipe is from (or null if unknown / no fitting cuisine)",
    )
    temperature: FriendlyEnum(TemperatureType) = Field(
        default=TemperatureType.ANY,
        description="At what temperature this recipe is best served",
    )


class Ingredient(BaseModel):
    ingredient: FriendlyString = Field(
        description="Ingredient name OR title of this section of the ingredient list (starting with #)",
    )
    amount: FriendlyOptionalString = Field(
        description="Amount to use of this ingredient, or null if unknown / unspecified",
    )


class Nutrition(BaseModel):
    group: FriendlyString = Field(
        description="Nutrition value group",
    )
    amount: FriendlyOptionalString = Field(
        description="Amount of this nutrition group, or null if unknown",
    )


class Recipe(BaseModel):
    name: FriendlyString = Field(
        description="Name of this dish",
    )
    meta: RecipeMeta = Field(default_factory=RecipeMeta)
    time: FriendlyOptionalInt = Field(
        default=None,
        description="Time in minutes it takes to prepare this recipe, or null if unknown",
    )
    people: FriendlyOptionalInt = Field(
        default=None,
        description="Number of people / portions this recipe will make, or null if unknown",
    )
    url: FriendlyOptionalString = Field(
        default=None,
        description="Original URL of this recipe's source, or null if unknown",
    )
    ingredients: list[Ingredient] = Field(
        default_factory=list,
        description=(
            "List of ingredients and amounts used in this recipe, for example 'one onion' corresponds to "
            "{'amount': '1', 'ingredient': 'onion'} and 'a pinch of salt' corresponds to "
            "{'amount': 'a pinch', 'ingredient': 'salt'}, or 'zout' corresponds to {'ingredient': 'zout'}."
            "An ingriedent section might look like {'ingredient': '# For the sauce'}."
        ),
    )
    preparation: Annotated[list[str], BeforeValidator(_to_str_list)] = Field(
        default_factory=list,
        description=(
            "Steps to create this recipe, for example 'mix everything together in a big bowl'. Start with"
            " # to turn it into a 'section header' for part of the recipe, for example "
            "'# Creating the sauce'"
        ),
    )
    nutrition: list[Nutrition] = Field(
        default_factory=list,
        description=("List of nutritional values for one serving of this recipe"),
    )
    remarks: FriendlyOptionalString = Field(
        default=None,
        description="Additional remarks for this recipe to be added by an admin",
    )
    thumbnail: FriendlyOptionalString = Field(
        default=None,
        description="Thumbnail URL for this recipe, injected automatically",
    )

    # preserved fields
    date_created: float = Field(
        default=0.0,
        description="Timestamp this recipe was last updated in the cookbook, injected automatically",
    )
    date_updated: float = Field(
        default=0.0,
        description="Timestamp this recipe was created in the cookbook, injected automatically",
    )
    igcode: str | None = Field(
        default=None,
        description="Instagram post code linked to this recipe, injected automatically",
    )

    @property
    def sha(self) -> hashlib._Hash:
        """Hash for this recipe for etag / caching purposes"""
        return hashlib.sha256(
            msgspec.json.encode(self.model_dump(), order="deterministic"),
            usedforsecurity=False,
        )
