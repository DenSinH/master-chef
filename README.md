# master-chef

Code used to host a website that allows me to store recipes from other websites in one central place. 
It uses ChatGPT to convert recipes to a JSON object which I store in a private repo. 
I read the contents off a webpage containing a recipe, ask chatgpt to convert this for me, and allow myself to edit 
the contents of the recipe. I can also feed it text directly, or add a recipe completely manually, though I have not used
these options yet. 

The HTML and CSS for the pages is also almost entirely generated using ChatGPT.


## Setting up

In order to set up and run the cookbook, you need to do a couple of things.
First of all, you need the environment variables as seen in `.env.example`.
Some of these require some effort to obtain:
- `RECIPE_REPO_NAME`: A repository with two files: `recipes.json` and `unmade.json`, containing
  empty json objects, for storing your recipes.
- `RECIPE_PAT`: In your GitHub account, go to "Settings > Developer Settings > Personal access tokens > Fine grained tokens" and create a new PAT. 
    - For "Repository access" select "Only select repostiories" and select the 
      repository you plan to use for the recipes (which you specified in 
      `RECIPE_REPO_NAME`). 
    - In the permissions tab for "Contents", select "Read & Write".
- `INSTAGRAM_USER` / `INSTAGRAM_PASS` should just be Instagram credentials for an account that may be used for the cookbook (**This includes posting pictures as admin**).
- `OPENAI_API_KEY`: This is just your OpenAI access token that you get when you have an OpenAI account. Make sure you have funds on there.
- `IMGUR_...`: For these, we need to set up an ImGur account with credentials to post to an album in this account. You may follow [this documentation](https://api.imgur.com/oauth2) on the Imgur API.
  - I think `IMGUR_ALBUM_ID` is broken...
  - `IMGUR_CLIENT_ID` and `IMGUR_CLIENT_SECRET` are created when you register an app on ImGur.
  - To obtain `IMGUR_REFRESH_TOKEN`, you must set a redirect URL in the Imgur app. This must be a secure website, but may just be imgur itself. Whenever you request access for the imgur app, you will be redirected to this URL and the refresh token will be in the URL encoded parameters (I think, this was a while ago).
