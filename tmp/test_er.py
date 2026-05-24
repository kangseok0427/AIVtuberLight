import httpx, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('ER_API_KEY')
resp = httpx.get('https://open-api.bser.io/open-api/v1/rank/top/10/1', headers={'x-api-key': key})
print(resp.status_code)
print(resp.json())