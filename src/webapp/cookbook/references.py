from thefuzz import fuzz
from fuzzysearch import find_near_matches
from functools import lru_cache
import re


# Sample list of ingredient names
ingredient_names = ["Garlic cloves", "Garlic Powder", "onion", "tomato", "salt", "pepper"]


def fuzzy_extract(query, text, threshold):
    query = re.sub('[^a-z\- ]', '', query.lower()).strip()
    score = fuzz.partial_token_set_ratio(query, text)
    if score > threshold:
        for match in find_near_matches(query.lower(), text.lower(), max_l_dist=1):
            yield (match.matched.lower(), score)


@lru_cache(maxsize=1024)
def replace_ingredient_references(recipe_step, ingredients):
    ingredient_references = {}
    for i, ingredient in enumerate(ingredients):
        matches = fuzzy_extract(ingredient, recipe_step, 80)
        for match, score in matches:
            if match in ingredient_references:
                if score <= ingredient_references[match][1]:
                    continue
            ingredient_references[match] = (i, score)

    for reference, (i, _) in ingredient_references.items():
        recipe_step = re.sub(f"({re.escape(reference)})", fr'<ref data-ingredient="{i}">\1</ref>', recipe_step, flags=re.IGNORECASE)

    return recipe_step
