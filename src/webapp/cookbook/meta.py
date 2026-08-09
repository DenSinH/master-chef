from enum import StrEnum


class Language(StrEnum):
    NL = "nl"
    EN = "en"


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    APPETIZER = "appetizer"
    MAIN = "main"
    SIDE = "side"
    DESSERT = "dessert"
    SNACK = "snack"
    BEVERAGE = "beverage"
    SOUP = "soup"
    SALAD = "salad"
    OTHER = "other"


class MeatType(StrEnum):
    CHICKEN = "chicken"
    BEEF = "beef"
    PORK = "pork"
    FISH = "fish"
    SEAFOOD = "seafood"
    VEGETARIAN = "vegetarian"
    OTHER = "other"


class CarbType(StrEnum):
    RICE = "rice"
    PASTA = "pasta"
    POTATOES = "potatoes"
    SWEET_POTATOES = "sweet potatoes"
    BREAD = "bread"
    WRAPS = "wraps"
    LEGUMES = "legumes"
    NOODLES = "noodles"
    NONE = "none"
    OTHER = "other"


class CuisineType(StrEnum):
    ITALIAN = "italian"
    JAPANESE = "japanese"
    INDIAN = "indian"
    KOREAN = "korean"
    MEXICAN = "mexican"
    THAI = "thai"
    CHINESE = "chinese"
    MEDITERRANEAN = "mediterranean"
    FRENCH = "french"
    GREEK = "greek"
    MIDDLE_EASTERN = "middle eastern"
    SPANISH = "spanish"
    EASTERN = "eastern"
    OTHER = "other"


class TemperatureType(StrEnum):
    WARM = "warm"
    COLD = "cold"
    ROOM_TEMPERATURE = "room temperature"
    ANY = "any"
