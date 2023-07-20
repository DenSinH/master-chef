import sanic
from sanic import Sanic
from sanic import Request
from sanic.exceptions import NotFound

import cookbook

app = Sanic(__name__)
app.static("/static", "./static")


def _parse_recipe_form(form: sanic.request.RequestParameters):
    ingredients = []
    for amount, ingredient in zip(form.getlist("ingredient-amount", []), form.getlist("ingredient-type", [])):
        if ingredient == "null":
            continue
        if amount == "-1":
            amount = None

        ingredients.append({
            "amount": amount,
            "ingredient": ingredient
        })

    nutrition = []
    for amount, group in zip(form.getlist("nutrition-amount", []), form.getlist("nutrition-group", [])):
        if group == "null":
            continue
        if amount == "-1":
            amount = None

        nutrition.append({
            "amount": amount,
            "group": group
        })
    if not nutrition:
        nutrition = None

    recipe = {
        "name": form["name"][0],
        "url": form["url"][0] if "url" in form else None,
        "people": int(form["people"][0]) if "people" in form else None,
        "time": int(form["time"][0]) if "time" in form else None,
        "ingredients": ingredients,
        "nutrition": nutrition,
        "preparation": form.getlist("preparation", []),
        "thumbnail": str(form["thumbnail"][0]) if "thumbnail" in form else None
    }
    return recipe


@app.get("/")
@app.ext.template("cookbook.html")
async def index(request: Request):
    return {
        "recipes": await cookbook.get_recipes()
    }


@app.get("/recipe/<id>")
@app.ext.template("recipe.html")
async def recipe(request: Request, id: str):
    recipes = await cookbook.get_recipes()
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    return {
        "recipe": recipes[id],
        "recipe_id": id
    }


@app.get("/recipe/<id>/update")
@app.ext.template("add/form.html")
async def update_recipe_form(request: Request, id: str):
    recipes = await cookbook.get_recipes()
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    return {
        "recipe": recipes[id],
        "action": app.url_for('update_recipe', id=id)
    }


@app.post("/recipe/<id>/update")
async def update_recipe(request: Request, id: str):
    recipe = _parse_recipe_form(request.form)
    await cookbook.update_recipe(id, recipe)

    return sanic.redirect(app.url_for("recipe", id=id))


@app.post("/recipe/<id>/delete")
async def delete_recipe(request: Request, id: str):
    recipes = await cookbook.get_recipes()
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    print(f"delete {id}")
    # await cookbook.delete_recipe(id)
    return sanic.redirect("/")


@app.get("/add/url")
@app.ext.template("add/url.html")
async def add_recipe_url_form(request: Request):
    return {}


@app.post("/add/url")
@app.ext.template("add/form.html")
async def add_recipe_url(request: Request):
    url = request.form["url"][0]
    recipe = await cookbook.translate_url(url)
    return {
        "recipe": recipe,
        "action": app.url_for('add_recipe_form'),
        "refresh_warning": True
    }


@app.get("/add/text")
@app.ext.template("add/text.html")
async def add_recipe_text_form(request: Request):
    return {}


@app.post("/add/text")
@app.ext.template("add/form.html")
async def add_recipe_text(request: Request):
    recipe = cookbook.translate_page(request.form["text"][0])
    return {
        "recipe": recipe,
        "action": app.url_for('add_recipe_form'),
        "refresh_warning": True
    }


@app.get("/add/form")
@app.ext.template("add/form.html")
async def add_recipe_form_form(request: Request):
    return {
        "recipe": {},  # empty recipe for template rendering
        "action": app.url_for('add_recipe_form')
    }


@app.get("/test")
@app.ext.template("add/form.html")
async def test(request: Request):
    return {
        "recipe": {'ingredients': [{'amount': '1', 'ingredient': 'ui'},
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
 'tags': ['main dish', 'poultry', 'wrap'],
 'time': 25,
 'url': 'https://15gram.be/recepten/wraps-kip-tikka-masala'}
    }


@app.post("/add/form")
async def add_recipe_form(request: Request):
    from pprint import pprint
    pprint(request.form)

    recipe = _parse_recipe_form(request.form)
    pprint(recipe)
    return sanic.redirect("/")


if __name__ == '__main__':
    import sys
    import os

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 80)), debug="--debug" in sys.argv)
