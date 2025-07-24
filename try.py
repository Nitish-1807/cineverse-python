import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

response= requests.get(f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}")
data = response.json()
movies = data.get("results", [])

print("\n🎬 Top 5 Trending Movies Today:")
for movie in movies[:5]:
    title = movie.get("title", "N/A")
    date = movie.get("release_date", "Unknown")
    rating = movie.get("vote_average", "N/A")
    print(f"• {title} ({date}) - ⭐ {rating}")
