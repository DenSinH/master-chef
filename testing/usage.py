import requests
import datetime
from dotenv import load_dotenv

load_dotenv()

import os
from pprint import pprint


api_key = os.environ["OPENAI_API_KEY"]

# API headers
headers = {'Authorization': f'Bearer {api_key}'}

# API endpoint
url = 'https://api.openai.com/v1/usage'

# Date for which to get usage data
date = datetime.date(year=2023, month=8, day=2)

# Parameters for API request
params = {'date': date.strftime('%Y-%m-%d')}

# Send API request and get response
response = requests.get(url, headers=headers, params=params)
pprint(response.json())
