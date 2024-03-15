from .StringMatcher import StringMatcher as SequenceMatcher
from functools import lru_cache
import re
from dataclasses import dataclass


THRESHOLD = 0.8


@dataclass
class PartialMatch:
    start: int
    end: int
    matched: str
    score: int


def _process_string(s):
    return re.sub(r"[^a-z\- ]+", " ", s.lower()).strip()


def _partial_search(s1, s2):
    """
    Reimplemented from
    https://github.com/seatgeek/fuzzywuzzy/blob/af443f918eebbccff840b86fa606ac150563f466/fuzzywuzzy/fuzz.py#L34
    """
    s1 = _process_string(s1)
    s2 = _process_string(s2)

    if len(s1) <= len(s2):
        shorter = s1
        longer = s2
    else:
        shorter = s2
        longer = s1

    for i, c in enumerate(longer):
        if c != " ":
            continue
        long_start = i + 1
        long_end = long_start + len(shorter)
        long_substr = longer[long_start:long_end]

        m2 = SequenceMatcher(None, shorter, long_substr)
        r = m2.ratio()

        if r > THRESHOLD:
            yield PartialMatch(
                start=long_start,
                end=long_end,
                matched=long_substr,
                score=int(round(100 * r))
            )


def _fuzzy_extract(query, text):
    query = _process_string(query)
    words = query.split(" ")

    for i in range((len(words) // 2) + 1):
        # find longest match first
        # match at least half the words
        for j in reversed(range(i + ((len(words) + 1) // 2), len(words) + 1)):
            substr = " ".join(words[i:j])
            for match in _partial_search(substr, text):
                yield match


@lru_cache(maxsize=1024)
def replace_ingredient_references(recipe_step, ingredients):
    ingredient_references = {}
    for i, ingredient in enumerate(ingredients):
        for match in _fuzzy_extract(ingredient, recipe_step):
            if match.matched not in ingredient_references:
                ingredient_references[match.matched] = (match, i)
            elif match.score > ingredient_references[match.matched][0].score:
                ingredient_references[match.matched] = (match, i)
            elif match.score == ingredient_references[match.matched][0].score:
                if len(match.matched) > len(ingredient_references[match.matched][0].matched):
                    # prefer longer matches
                    ingredient_references[match.matched] = (match, i)

    if not ingredient_references:
        return recipe_step
    

    regex = re.compile(f"(^|\W)({'|'.join(re.escape(reference.lower()) for reference in sorted(ingredient_references, key=lambda ref: -len(ref)))})(\W|$)", flags=re.IGNORECASE)
    return regex.sub(lambda ref: fr'{ref.group(1)}<ref data-ingredient="{ingredient_references[ref.group(2).lower()][1]}">{ref.group(2)}</ref>{ref.group(3)}', recipe_step)


if __name__ == "__main__":
    # Sample list of ingredient names
    ingredient_names = ("ui", "knoflook", "olijfolie", "komijn", "paprikapoeder", "cayennepeper", "paprika", "venkel", "verse tomaatjes", "tomatenpuree", "Peper en zout", "eieren", "gehakte tomatenblokjes")
    step = "Fruit de ui aan tot deze glazig is en voeg de knoflook, komijn, paprikapoeder en cayenne toe en bak dit even mee."
    print(replace_ingredient_references(step, ingredient_names))