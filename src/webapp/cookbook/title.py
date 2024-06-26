"""
Generates random titles for the cookbook.
They are generated from some predetermined,
Dutch and English combinations of prefixes, 
postfixes and names.
"""

import random


_prefixes = {
    'nl': [
        'Koken met',
        'Recepten van',
        'Smullen met',
        'Genieten met',
    ],
    'en': [
        'Cooking with',
        'Recipes by',
        'Feasting with',
    ]
}

# Postfixes for the cookbook titles
_postfixes = {
    'nl': [
        "Keuken",
        "Lekkernijen",
        "Kookboek",
        "Smaakmakers",
        "Proeverij",
        "Feestmaal",
    ],
    'en': [
        "Kitchen",
        "Delight",
        "Cookbook",
        "Treats",
        "Feast",
    ]
}


def _generate_title(name, language):
    if random.choice(["pre", "post"]) == "post":
        postfix = random.choice(_postfixes[language])
        if name.endswith("s"):
            return f"{name}' {postfix}"
        else:
            return f"{name}'s {postfix}"
    else:
        prefix = random.choice(_prefixes[language])
        return f"{prefix} {name}"


def generate_title():
    name = random.choice(["Dennis", "Merel", "Merel & Dennis", "Dennis & Merel"])
    language = random.choice(["en", "nl"])
    return _generate_title(name, language)
