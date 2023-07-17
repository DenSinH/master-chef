import requests
from pprint import pprint
from dotenv import load_dotenv

load_dotenv()

import os
import base64
import json


res = requests.get(
    "https://api.github.com/repos/DenSinH/master-chef-recipes/contents/recipes.json",
    headers={
        "accept": "application/vnd.github+json",
        "authorization": f"token {os.environ['GITHUB_RECIPES_READ_PAT_TOKEN']}"
    }
)

if not res.ok:
    print(res.status_code)
    quit(1)
else:
    file = res.json()
    raw = base64.b64decode(file["content"]).decode("utf-8")
    recipes = json.loads(raw)


recipes['0']['keywords'] = [
    'ui',
    'gele paprika',
    'kipfilet',
    'tomatenpuree',
    'kokosmelk',
]

res = requests.put(
    "https://api.github.com/repos/DenSinH/master-chef-recipes/contents/recipes.json",
    data=json.dumps({
        "message": "update recipes",
        "content": base64.b64encode(json.dumps(recipes, indent=2).encode("ascii")).decode("ascii"),
        "committer": {
            "name": "Dennis Hilhorst",
            "email": "dhilhorst2000@gmail.com"
        },
        "sha": file["sha"]
    }),
    headers={
        "accept": "application/vnd.github+json",
        "authorization": f"token {os.environ['GITHUB_RECIPES_WRITE_PAT_TOKEN']}"
    }
)

if not res.ok:
    print(res.status_code, res.text)
    quit(1)
else:
    print(res.text)
