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


recipes['0'] = {'ingredients': [{'amount': '1', 'ingredient': 'ui'},
                 {'amount': '1', 'ingredient': 'gele paprika'},
                 {'amount': '2', 'ingredient': 'kipfilet'},
                 {'amount': '½ blikje', 'ingredient': 'tomatenpuree'},
                 {'amount': '200 ml', 'ingredient': 'kokosmelk'},
                 {'amount': '2 kl', 'ingredient': 'garam masala'},
                 {'amount': '2', 'ingredient': 'tomaten'},
                 {'amount': '2', 'ingredient': 'lente-uitjes'},
                 {'amount': '4', 'ingredient': "tortilla's"},
                 {'amount': '1 el', 'ingredient': 'arachideolie'},
                 {'amount': '½ kl', 'ingredient': 'cayennepeper'},
                 {'amount': None, 'ingredient': 'peper'},
                 {'amount': None, 'ingredient': 'zout'}],
 'name': 'Wraps kip tikka masala',
 'nutrition': [{'amount': '795.38 kcal', 'group': 'Calorieën'},
               {'amount': '61.5 g', 'group': 'Koolhydraten'},
               {'amount': '13.95 g', 'group': 'waarvan suikers'},
               {'amount': '37.07 g', 'group': 'Vet'},
               {'amount': '23.39 g', 'group': 'waarvan verzadigd'},
               {'amount': '46.92 g', 'group': 'Proteïnen'},
               {'amount': '6.69 g', 'group': 'Vezels'}],
 'people': 2,
 'preparation': ['Snij de ui in halve ringen. Snij de gele paprika in fijne '
                 'blokjes. Snij de kipfilet in blokjes.',
                 'Verhit de arachideolie in een antikleefpan en stoof de ui en '
                 'paprika. Voeg na 2 minuten de cayennepeper (gebruik minder '
                 'als je niet van pikant houdt) toe. Roer goed om en voeg dan '
                 'de kippenblokjes toe. Laat 5 minuten bakken, tot de kip mooi '
                 'gekleurd is. Kruid met peper en zout.',
                 'Voeg de aangegeven hoeveelheid tomatenpuree toe en laat kort '
                 'meebakken. Voeg de kokosmelk toe. Meng goed door elkaar en '
                 'laat 5 minuten zachtjes pruttelen, roer er dan de garam '
                 'masala door.',
                 'Snij ondertussen de tomaat in blokjes en de lente-uitjes in '
                 "ringen. Warm de tortilla's op in een antikleefpan zonder "
                 'vetstof en hou warm onder aluminiumfolie. Je kan ze ook '
                 'opwarmen (zonder verpakking!) in de microgolfoven.',
                 'Roer de tomatenblokjes door de kip tikka masala. Verdeel '
                 "over de tortilla's, strooi er de lente-uitjes over en rol de "
                 "tortilla's op. Serveer meteen."],
 'tags': ['main dish', 'poultry', 'wrap', 'Indian', 'quick and easy'],
 'time': 25,
 'url': 'https://15gram.be/recepten/wraps-kip-tikka-masala'}

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
