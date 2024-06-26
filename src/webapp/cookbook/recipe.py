from dataclasses import dataclass, field
import dataclasses
import types
from .meta import *
from thefuzz import process


class RecipeError(Exception):
    pass


class Fixable:

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
                
            if value is None:
                # assume None means the default value
                # so we skip it
                continue
            elif isinstance(field.type, types.GenericAlias):
                if field.type.__origin__ is list:
                    # iterate through field values
                    subscript, = field.type.__args__
                    if not isinstance(value, list):
                        # make list of value
                        if isinstance(value, subscript):
                            value = [value]
                        else:
                            raise RecipeError(f"Expected list for field {key}, got {value}")
                    
                    # initialize elementwise
                    if issubclass(subscript, Fixable):
                        fixed[key] = [subscript.from_data(**v) for v in value]
                    elif dataclasses.is_dataclass(subscript):
                        fixed[key] = [subscript(**v) for v in value]
                    else:
                        fixed[key] = list(subscript(v) for v in value)
                else:
                    raise NotImplementedError(f"GenericAlias {field.type} loading")
            else:
                # value may be a list, like in a form submission
                if isinstance(value, list):
                    if len(value) == 0:
                        # assume default value again
                        continue

                    # choose first value
                    value = value[0]

                if issubclass(field.type, Fixable):
                    fixed[key] = field.type.from_data(**value)
                elif dataclasses.is_dataclass(field.type):
                    fixed[key] = field.type(**value)
                else:
                    fixed[key] = field.type(value)

        # validate allowed values
        for key, value in fixed.items():
            field = fields[key]

            if value is None:
                continue

            allowed_values = field.metadata.get("allowed_values")
            if allowed_values is not None:
                def _fix_value(v):
                    if v is None:
                        return v
                    if v in allowed_values:
                        return v
                    process.extractOne(v, allowed_values)[0]

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
    meat_type: list[str] = field(default_factory=lambda: ["other"], metadata={"allowed_values": MEAT_TYPES})
    carb_type: list[str] = field(default_factory=lambda: ["other"], metadata={"allowed_values": CARB_TYPES})
    cuisine: str = field(default=None, metadata={"allowed_values": CUISINE_TYPES})
    temperature: str = field(default="any", metadata={"allowed_values": TEMPERATURE_TYPES})

    def __post_init__(self):
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
