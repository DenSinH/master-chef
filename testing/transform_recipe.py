import openai
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

import os
import re
import json


openai.api_key = os.environ["OPENAI_API_KEY"]

MAX_RETRIES = 1
MODEL = "gpt-3.5-turbo"
PROMPT = """
The following text is from a website, and it contains a recipe, possibly in Dutch, as well as unnecessary other text from the webpage.
The recipe contains information on the ingredients, the prepration and possibly nutritional information.
Could you convert the recipe to a JSON object with the following keys:
"name": the name of this recipe.
"ingredients": a list of dictionaries, with keys "ingredient", mapping to the name of the ingredient, and "amount" which is a string containing the amount of this ingredient needed including the unit, or null if no specific amount is given.
               For example, the ingredient "one onion" should yield {{'amount': '1', 'ingredient': 'onion'}}, and the ingredient "zout" should yield {{'amount': null, 'ingredient': 'zout'}}.
"preparation": a list of strings containing the steps of the recipe.
"nutrition": null if there is no nutritional information in the recipe, or a list of dictionaries containing the keys "group", with the type
of nutrional information, and "amount": with the amount of this group that is contained in the recipe, as a string including the unit.
"url:": the literal string "{url}"
"people": the amount of people that can be fed from this meal as an integer, in case this information is present, otherwise null
"time": the time that this recipe takes to make in minutes as an integer, in case this information is present, otherwise null
"tags": generate a list of about 3-5 English strings that can be seen as the most important keywords for the recipe.

Keep the language the same, and preferably do not change anything about the text in the recipe at all.
Only output the JSON object, and nothing else.
Here comes the text:

{text}
"""


class RecipeConversionError(Exception):
    pass


def translate_page(url):
    print("Retrieving URL")
    res = requests.get(url)
    if not res.ok:
        raise RecipeConversionError(f"Could not get the specified url, status code {res.status_code}")
    soup = BeautifulSoup(res.text, features="html.parser")
    text = re.sub(r"(\n\s*)+", "\n", soup.text)

    print(f"Converting with ChatGPT ({MODEL})")
    messages = [
        {"role": "system", "content": "You are a helpful assistant that converts recipies into JSON format."},
        {"role": "user", "content": PROMPT.format(url=url, text=text)}
    ]
    for i in range(1 + MAX_RETRIES):
        chat_completion = openai.ChatCompletion.create(
            model=MODEL, messages=messages, temperature=0.2
        )
        reply = chat_completion.choices[0].message.content
        try:
            return json.loads(reply)
        except json.JSONDecodeError:
            print("Conversion failed, retrying")
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": "this is not a parseable json object, "
                                                        "only output the json object"})
    raise RecipeConversionError("ChatGPT did not return a parsable json object, please try again")


if __name__ == '__main__':
    from pprint import pprint

    recipe = translate_page("https://15gram.be/recepten/wraps-kip-tikka-masala")
    pprint(recipe)
