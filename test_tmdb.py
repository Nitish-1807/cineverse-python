import requests

TMDB_API_KEY = "becc1638b2dcedba410c1c54ac853c61"
url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={TMDB_API_KEY}"

try:
    response = requests.get(url)
    response.raise_for_status()
    print("✅ Connection successful!")
    data = response.json()
    print(f"Fetched {len(data['results'])} results.")
except requests.exceptions.RequestException as e:
    print("❌ Connection failed:")
    print(e)
