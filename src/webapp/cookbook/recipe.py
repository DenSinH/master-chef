import abc
import dataclasses
import hashlib
import types
import typing
from dataclasses import dataclass, field
from typing import Any

import msgspec.json
from thefuzz import process

from .meta import *


class RecipeError(Exception):
    pass


def _is_list_of_single_keyed_dicts(value: list) -> bool:
    """Check whether the given value is a list of single keyed dicts. We want to check this,
    since sometimes ChatGPT returns a list of {'step' : 'step text'} dicts for recipe steps,
    which get converted to string literals directly."""
    return all(isinstance(v, dict) for v in value) and len({k for v in value for k in v}) == 1


class Fixable(abc.ABC):
    """
    Abstract (data)class that can be instantiated from a dictionary,
    loosely parsing the dictionary into its fields.
    """

    @staticmethod
    def _fix_field(field: dataclasses.Field, value: Any) -> Any:
        if value is None:
            # assume None means the default value
            return None
        elif isinstance(field.type, types.GenericAlias):
            origin = typing.get_origin(field.type) or field.type
            field_args = typing.get_args(field.type)

            if origin is list:
                # iterate through field values
                subscript, = field_args

                # the subscript may be subscripted itself
                subscript = typing.get_origin(subscript) or subscript
                if not isinstance(value, list):
                    # make list of value
                    value = [value]

                # initialize elementwise
                if issubclass(subscript, Fixable):
                    assert all(isinstance(v, dict) for v in value)
                    return [subscript.from_data(**v) for v in value]
                elif dataclasses.is_dataclass(subscript):
                    assert all(isinstance(v, dict) for v in value)
                    return [subscript(**v) for v in value]
                elif subscript is not dict and _is_list_of_single_keyed_dicts(value):
                    # all single-keyed dicts with the same key, take the value
                    # this fixes an issue where ChatGPT returns a list of
                    # {'step': 'step text'} dicts for the recipe steps
                    # instead of converting to subscript directly, we take the first
                    # (and only) dict value
                    return [subscript(next(iter(v.values()))) for v in value]
                else:
                    return list(subscript(v) for v in value)
            else:
                raise NotImplementedError(f"GenericAlias {field.type} loading")
        else:
            # value may be a list, like in a form submission
            if isinstance(value, list):
                if len(value) == 0:
                    # assume default value again
                    return None

                # choose first value
                value = value[0]

            if issubclass(field.type, Fixable):
                return field.type.from_data(**value)
            elif dataclasses.is_dataclass(field.type):
                return field.type(**value)
            else:
                return field.type(value)

    @classmethod
    def from_data(cls, **kwargs):
        fields = {field.name: field for field in dataclasses.fields(cls)}
        fixed = {}
        for key, field in fields.items():
            value = kwargs.get(key)

            if value is None:
                # did not find field, extract best match
                value, score, key = process.extractOne(key, kwargs)

                if score < 90:
                    # no match, use default value
                    continue

            fixed[key] = Fixable._fix_field(field, value)

        # validate allowed values
        for key, value in fixed.items():
            if value is None:
                continue

            # get allowed values
            field = fields[key]
            allowed_values = field.metadata.get("allowed_values")
            if allowed_values is None:
                continue

            def _fix_value(v):
                """Fix a single value v to one of the allowed values for this field"""
                if v is None:
                    return v

                # v may already be allowed
                if v in allowed_values:
                    return v
                return process.extractOne(v, allowed_values)[0]

            if isinstance(value, list):
                value = [_fix_value(v) for v in value]
            else:
                value = _fix_value(value)
            fixed[key] = value

        return cls(**fixed)


@dataclass(kw_only=True, slots=True, frozen=True)
class RecipeMeta(Fixable):
    language: str = field(default=None, metadata={"allowed_values": LANGUAGES})
    meal_type: str = field(default="other", metadata={"allowed_values": MEAL_TYPES})
    meat_type: list[str] = field(default_factory=lambda: ["other"],  metadata={"allowed_values": MEAT_TYPES})
    carb_type: list[str] = field(default_factory=lambda: ["other"], metadata={"allowed_values": CARB_TYPES})
    cuisine: str = field(default=None, metadata={"allowed_values": CUISINE_TYPES})
    temperature: str = field(default="any", metadata={"allowed_values": TEMPERATURE_TYPES})

    def __post_init__(self):
        # ensure max length
        object.__setattr__(self, 'carb_type', self.carb_type[:2])
        object.__setattr__(self, 'meat_type', self.meat_type[:2])


@dataclass(kw_only=True, slots=True, frozen=True)
class Ingredient(Fixable):
    ingredient: str
    amount: str = None


@dataclass(kw_only=True, slots=True, frozen=True)
class Nutrition(Fixable):
    group: str
    amount: str = None


@dataclass(kw_only=True, slots=True, frozen=True)
class Recipe(Fixable):
    name: str = ""
    meta: RecipeMeta = field(default_factory=RecipeMeta)
    time: int = None
    people: int = None
    url: str = None
    ingredients: list[Ingredient] = field(default_factory=list)
    preparation: list[str] = field(default_factory=list)
    nutrition: list[Nutrition] = field(default_factory=list)
    remarks: str = None
    thumbnail: str = None

    # preserved fields
    date_created: float = field(default=0.0, compare=False)
    date_updated: float = field(default=0.0, compare=False)
    igcode: str = None

    @property
    def sha(self) -> 'hashlib._Hash':
        return hashlib.sha256(
            msgspec.json.encode(
                dataclasses.asdict(self),
                order="deterministic"
            ),
            usedforsecurity=False
        )
