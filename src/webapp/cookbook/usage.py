from typing import Union
import aiohttp
import datetime
from dotenv import load_dotenv

load_dotenv()

import os


API_KEY = os.environ["OPENAI_API_KEY"]
USAGE_CACHE = {}


async def get_usage(date: Union[datetime.date, str]):
    headers = {'Authorization': f'Bearer {API_KEY}'}
    url = 'https://api.openai.com/v1/usage'
    if isinstance(date, datetime.date):
        params = {'date': date.strftime("%Y-%m-%d")}
    else:
        params = {'date': date}

    if params["date"] != datetime.date.today().strftime("%Y-%m-%d"):
        if params["date"] in USAGE_CACHE:
            return USAGE_CACHE[params["date"]]

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
        result = await session.get(url, headers=headers, params=params)
        result.raise_for_status()
        data = await result.json()
        if params["date"] != datetime.date.today().strftime("%Y-%m-%d"):
            USAGE_CACHE[params["date"]] = data.get("data", [])
        return data.get("data", [])
