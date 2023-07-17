import requests
from pprint import pprint
from dotenv import load_dotenv

load_dotenv()

import os


res = requests.get(
    "https://api.github.com/repos/DenSinH/master-chef-recipes/contents/recipes.json",
    headers={
        "accept": "application/vnd.github.v3.raw",
        "authorization": f"token {os.environ['GITHUB_RECIPES_READ_PAT_TOKEN']}"
    }
)

if not res.ok:
    print(res.status_code)
else:
    pprint(res.json())
