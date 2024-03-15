from thefuzz import fuzz
from fuzzysearch import find_near_matches
from functools import lru_cache
import re


THRESHOLD = 0.8

def fuzzy_extract(query, text):
    query = re.sub('[^a-z\- ]', '', query.lower()).strip()
    score = fuzz.partial_token_set_ratio(query, text)
    if score > THRESHOLD:
        for match in find_near_matches(query.lower(), text.lower(), max_l_dist=int((1.0 - THRESHOLD) * len(query))):
            yield (match.matched.lower(), score)


@lru_cache(maxsize=1024)
def replace_ingredient_references(recipe_step, ingredients):
    ingredient_references = {}
    for i, ingredient in enumerate(ingredients):
        matches = fuzzy_extract(ingredient, recipe_step)
        for match, score in matches:
            if match in ingredient_references:
                if score <= ingredient_references[match][1]:
                    continue
            ingredient_references[match] = (i, score)

    regex = re.compile(f"({'|'.join(re.escape(reference.lower()) for reference in ingredient_references)})", flags=re.IGNORECASE)
    return regex.sub(lambda ref: fr'<ref data-ingredient="{ingredient_references[ref.group().lower()][0]}">{ref.group()}</ref>', recipe_step)


if __name__ == "__main__":
    # Sample list of ingredient names
    ingredient_names = ["Garlic cloves", "Garlic Powder", "onion", "tomato", "salt", "pepper"]