import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TMDB_API_KEY = "becc1638b2dcedba410c1c54ac853c61"
url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={TMDB_API_KEY}"

session = requests.Session()

# Retry strategy for handling connection errors
retries = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retries)

# Mount it for both HTTP and HTTPS
session.mount("http://", adapter)
session.mount("https://", adapter)

headers = {
    "User-Agent": "Mozilla/5.0",  # mimic a browser
    "Accept": "application/json",
}

try:
    response = session.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    print("✅ Connection successful!")
    data = response.json()
    print(f"Fetched {len(data['results'])} results.")
except requests.exceptions.RequestException as e:
    print("❌ Connection failed:")
    print(e)
