from .StringMatcher import StringMatcher as SequenceMatcher
from functools import lru_cache
import re
from dataclasses import dataclass


THRESHOLD = 0.8


@dataclass
class PartialMatch:
    matched: tuple[str]
    target_words: int
    score: int
    ingredient_idx: int = None

    def target_score(self):
        return abs(len(self.matched) - self.target_words)
    
    def total_length(self):
        return len(" ".join(self.matched))
    
    def sort_val(self):
        return (self.target_score(), -self.total_length())


def _process_string(s):
    return re.sub(" +", " ", re.sub(r"[^a-z ]+", " ", s.lower())).strip()


def _partial_search(s1, s2):
    """
    Reimplemented from
    https://github.com/seatgeek/fuzzywuzzy/blob/af443f918eebbccff840b86fa606ac150563f466/fuzzywuzzy/fuzz.py#L34
    """
    s1 = _process_string(s1).split(" ")
    s2 = _process_string(s2).split(" ")

    if len(s1) <= len(s2):
        shorter = s1
        longer = s2
    else:
        shorter = s2
        longer = s1

    shorter_str = " ".join(shorter)
    for i in range(len(longer)):
        for j in range(len(shorter) - 1, len(shorter) + 2):
            long_substr = " ".join(longer[i:i + j])
            m2 = SequenceMatcher(None, shorter_str, long_substr)
            r = m2.ratio()

            if r > THRESHOLD:
                yield PartialMatch(
                    matched=tuple(longer[i:i + j]),
                    target_words=len(shorter),
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
            print(substr)
            for match in _partial_search(substr, text):
                yield match


def _replace_references(string, sorted_references):
    if not len(sorted_references):
        return string
    ref = sorted_references[0]
    regex = re.compile(f"(^|\W)({'[^a-z]+'.join(ref.matched)})(\W|$)", flags=re.IGNORECASE)
    split = regex.split(string)
    new = ""
    while len(split) > 1:
        left, sepl, match, sepr, *split = split
        new += _replace_references(left, sorted_references[1:])
        new += sepl + f'<ref data-ingredient="{ref.ingredient_idx}">{match}</ref>' + sepr
    return new + _replace_references(split[0], sorted_references[1:])


@lru_cache(maxsize=1024)
def replace_ingredient_references(recipe_step, ingredients):
    ingredient_references = {}
    for i, ingredient in enumerate(ingredients):
        for match in _fuzzy_extract(ingredient, recipe_step):
            match.ingredient_idx = i
            if match.matched not in ingredient_references:
                ingredient_references[match.matched] = match
            elif match.score > ingredient_references[match.matched].score:
                ingredient_references[match.matched] = match
            elif match.score == ingredient_references[match.matched].score:
                if match.total_length() > ingredient_references[match.matched].total_length():
                    ingredient_references[match.matched] = match

    if not ingredient_references:
        return recipe_step
    
    sorted_references = sorted(ingredient_references.values(), key=lambda ref: ref.sort_val())
    return _replace_references(recipe_step, sorted_references)
