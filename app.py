from flask import Flask, render_template, request, jsonify, session as flask_session
import requests
import os
from datetime import datetime
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import jsonify
import subprocess
import wikipedia
from flask import session

# Load .env variables
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

BASE_URL = "https://api.themoviedb.org/3"
API_KEY = TMDB_API_KEY

app = Flask(__name__, static_folder='static', template_folder='templates') # Explicitly set folders
app.secret_key = os.getenv("FLASK_SECRET_KEY", "some-secret-key")  # For session storage
language_map = {
    "en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu",
    "fr": "French", "ja": "Japanese", "ko": "Korean", "ml": "Malayalam", "kn": "Kannada"
}

# Session with retry setup
http_session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
adapter = HTTPAdapter(max_retries=retries)
http_session.mount('https://', adapter)
http_session.mount('http://', adapter)

provider_redirects = {
    "Amazon Prime Video": "https://www.primevideo.com",
    "Netflix": "https://www.netflix.com",
    "Disney Plus": "https://www.hotstar.com/in",
    "YouTube": "https://www.youtube.com",
    "Jio Cinema": "https://www.jiocinema.com",
    "Apple TV": "https://tv.apple.com"
}
# Safe GET function
def safe_get(url):
    try:
        print(f"🔗 Fetching: {url}")
        res = http_session.get(url, timeout=10)
        res.raise_for_status()
        return res.json().get("results", [])
    except Exception as e:
        print(f"❌ Failed fetching {url}\n{e}")
        return []

# Home route
@app.route("/")
def home():
    query = request.args.get("query", "")
    min_rating = int(request.args.get("min_rating", 0))
    language_filter = request.args.get("language", "")

    if query:
        search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query}"
        search_res = safe_get(search_url)
        
        # Step 1: Keep only movies and people
        filtered_results = [r for r in search_res if r.get("media_type") in ("movie", "person")]

        # Step 2: Apply filters to movies only
        filtered_results = [
            r for r in filtered_results if (
                r.get("media_type") == "person" or (
                    r.get("media_type") == "movie" and
                    r.get("vote_average", 0) >= min_rating and
                    (language_filter == '' or r.get("original_language") == language_filter)
                )
            )
        ]

        return render_template(
            "home.html",
            results=filtered_results,
            has_searched=True,
            min_rating=min_rating,
            language_filter=language_filter,
            language_map=language_map
        )

    # Default sections
    trending = safe_get(f"{BASE_URL}/trending/movie/week?api_key={API_KEY}")
    telugu = safe_get(f"{BASE_URL}/discover/movie?api_key={API_KEY}&with_original_language=te&sort_by=popularity.desc")
    tamil = safe_get(f"{BASE_URL}/discover/movie?api_key={API_KEY}&with_original_language=ta&sort_by=popularity.desc")
    hindi = safe_get(f"{BASE_URL}/discover/movie?api_key={API_KEY}&with_original_language=hi&sort_by=popularity.desc")
    top_rated_movies = safe_get(f"{BASE_URL}/movie/top_rated?api_key={API_KEY}")[:10] # Renamed to match template

    # Combine carousel movies from all 3, matching React's specific slice and filter logic
    # React's filter: rate >= 6 || year > 2024 || rate == 0;
    all_carousel_sources = (trending[:6] if trending else []) + \
                           (telugu[1:14] if telugu else []) + \
                           (tamil[:6] if tamil else [])

    carousel_movies_filtered = []
    for movie in all_carousel_sources:
        rate = movie.get("vote_average", 0)
        year_str = movie.get("release_date", "")[:4]
        year = int(year_str) if year_str.isdigit() else 0

        # Apply React's exact filter logic
        if rate >= 6 or year > 2024 or rate == 0:
            carousel_movies_filtered.append(movie)

    return render_template(
        "home.html",
        trending=trending,
        telugu=telugu,
        tamil=tamil,
        hindi=hindi,
        top_rated=top_rated_movies, # Use the renamed variable
        carousel_movies=carousel_movies_filtered, # Use the filtered list
        has_searched=False,
        min_rating=min_rating,
        language_filter=language_filter,
        language_map=language_map # Pass language map
    )

@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    url = f"{BASE_URL}/movie/{movie_id}?api_key={API_KEY}&append_to_response=credits,videos,reviews,watch/providers"
    try:
        res = http_session.get(url, timeout=10)
        res.raise_for_status()
    except Exception as e:
        return f"Error fetching movie detail: {e}"

    movie = res.json()

    # Trailer (Matching React's logic for finding first YouTube Trailer)
    trailer_key = None
    for v in movie.get("videos", {}).get("results", []):
        if v.get("site") == "YouTube" and v.get("type") == "Trailer":
            trailer_key = v["key"]
            break

    # Watch Providers for India (Matching React's structure)
    providers = []
    provider_link = "#" # Renamed to avoid conflict with 'link' variable if it's used elsewhere
    prov_data = movie.get("watch/providers", {}).get("results", {}).get("IN")
    if prov_data:
        provider_link = prov_data.get("link", "#")
        providers = prov_data.get("flatrate", []) # Prioritize flatrate, as in React display

    # Crew (filtered + sorted - Matching React's logic)
    crew = []
    important_jobs = [
        "Director", "Writer", "Screenplay", "Story",
        "Original Music Composer", "Music", "Director of Photography",
        "Cinematography", "Editor"
    ]
    added_jobs_set = set() # Renamed to avoid conflict with 'added' local variable
    for c in movie.get("credits", {}).get("crew", []):
        if c.get("job") in important_jobs and c["job"] not in added_jobs_set:
            added_jobs_set.add(c["job"])
            crew.append(c)

    crew.sort(key=lambda x: important_jobs.index(x["job"]) if x["job"] in important_jobs else len(important_jobs)) # Use len for safe index

    return render_template("movie_detail.html",
                           movie=movie,
                           trailer_key=trailer_key,
                           providers=providers,
                           provider_link=provider_link,
                           reviews=movie.get("reviews", {}).get("results", []),
                           crew=crew,
                           language_map=language_map)

@app.route("/person/<int:person_id>")
def person_detail(person_id):
    url1 = f"{BASE_URL}/person/{person_id}?api_key={TMDB_API_KEY}"
    url2 = f"{BASE_URL}/person/{person_id}/combined_credits?api_key={TMDB_API_KEY}"

    try:
        person = http_session.get(url1, timeout=100).json()
        credits_res = http_session.get(url2, timeout=100).json()
    except Exception as e:
        return f"Error fetching person details: {e}"

    birthplace = person.get("place_of_birth", "").lower()
    is_hollywood = any(loc in birthplace for loc in ["usa", "united states", "canada", "uk", "england", "australia","india"])

    all_projects = {}
    for credit in credits_res.get("cast", []) + credits_res.get("crew", []):
        if not credit.get("poster_path"):
            continue
        pid = credit["id"]
        if pid not in all_projects:
            all_projects[pid] = credit.copy()
            all_projects[pid]["roles"] = []
        role = credit.get("job") or credit.get("character")
        if role:
            all_projects[pid]["roles"].append(role)

    projects = list(all_projects.values())
    projects.sort(key=lambda x: x.get("popularity", 0), reverse=True)

    known_movies = [p for p in projects if p.get("media_type") == "movie"]
    known_tv = [p for p in projects if p.get("media_type") == "tv"]
    known_for = projects if not is_hollywood else []

    today = datetime.today().date().isoformat()
    upcoming = sorted(
        [p for p in projects if (p.get("release_date") or p.get("first_air_date", "9999-12-31")) >= today],
        key=lambda x: x.get("release_date", x.get("first_air_date", "9999-12-31"))
    )

    return render_template("person_detail.html",
                           person=person,
                           known_for=known_for,
                           known_movies=known_movies[:40] if is_hollywood else [],
                           known_tv=known_tv[:10] if is_hollywood else [],
                           upcoming=upcoming)

# Add TV Show Detail Route
@app.route('/tv/<int:tv_id>')
def tv_detail(tv_id):
    url = f"{BASE_URL}/tv/{tv_id}?api_key={API_KEY}&append_to_response=credits,videos,watch/providers"
    try:
        res = http_session.get(url, timeout=10)
        res.raise_for_status()
    except Exception as e:
        return f"Error fetching TV show detail: {e}"

    tv_show = res.json()

    # Cast (Matching React's slice)
    cast = tv_show.get("credits", {}).get("cast", [])[:25]

    # Crew (Matching React's logic)
    crew = []
    important_jobs = [
        "Director", "Writer", "Screenplay", "Story",
        "Original Music Composer", "Music",
        "Director of Photography", "Cinematography", "Editor",
        "Creator" # Added 'Creator' as in React
    ]
    added_jobs_set = set()
    for c in tv_show.get("credits", {}).get("crew", []):
        if c.get("job") in important_jobs and c["job"] not in added_jobs_set:
            added_jobs_set.add(c["job"])
            crew.append(c)
    crew.sort(key=lambda x: important_jobs.index(x["job"]) if x["job"] in important_jobs else len(important_jobs))

    # Watch Providers (Matching React's logic for India)
    providers = []
    provider_link = "#"
    prov_data = tv_show.get("watch/providers", {}).get("results", {}).get("IN")
    if prov_data:
        provider_link = prov_data.get("link", "#")
        providers = prov_data.get("flatrate", [])

    return render_template("tv_detail.html",
                           tv_show=tv_show,
                           cast=cast,
                           crew=crew,
                           providers=providers,
                           provider_link=provider_link,
                           language_map=language_map)

# Add TV Shows Route
@app.route("/shows")
def shows():
    language = request.args.get("language", "")
    search_query = request.args.get("search_query", "")

    tv_shows = []
    anime_shows = []

    if search_query:
        search_url = f"{BASE_URL}/search/tv?api_key={API_KEY}&query={search_query}"
        search_results = safe_get(search_url)

        tv_shows_filtered = []
        anime_filtered = []
        for item in search_results:
            if 16 in item.get("genre_ids", []): # Genre ID 16 for Animation/Anime
                if not language or item.get("original_language") == language:
                    anime_filtered.append(item)
            else:
                if not language or item.get("original_language") == language:
                    tv_shows_filtered.append(item)
        tv_shows = tv_shows_filtered
        anime_shows = anime_filtered
    else:
        # Default popular TV Shows
        tv_url = f"{BASE_URL}/discover/tv?api_key={API_KEY}&sort_by=popularity.desc&without_keywords=210024" # 210024 is for anime
        if language:
            tv_url += f"&with_original_language={language}"
        tv_shows = safe_get(tv_url)[:20]

        # Default popular Anime
        anime_url = f"{BASE_URL}/discover/tv?api_key={API_KEY}&with_keywords=210024&sort_by=popularity.desc&vote_count.gte=500"
        if language:
            anime_url += f"&with_original_language={language}"
        anime_shows = safe_get(anime_url)[:30]

    return render_template("shows.html",
                           tv_shows=tv_shows,
                           anime_shows=anime_shows,
                           language=language,
                           search_query=search_query,
                           language_map=language_map)

# Add Upcoming Route
@app.route("/upcoming")
def upcoming():
    language_filter = request.args.get("language", "")
    today = datetime.today().date().isoformat()
    
    url = f"{BASE_URL}/discover/movie?api_key={API_KEY}&sort_by=release_date.asc&primary_release_date.gte={today}"
    if language_filter:
        url += f"&with_original_language={language_filter}"
    
    upcoming_movies = safe_get(url)[:30]

    return render_template("upcoming.html",
                           upcoming_movies=upcoming_movies,
                           language_filter=language_filter,
                           language_map=language_map)

@app.route("/watchlist")
def watchlist():

    return render_template("watchlist.html", language_map=language_map)

@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if request.method == "POST":
        user_input = request.form.get("user_input", "").strip()
        previous_topic = flask_session.get("last_topic", "")

        # Use previous topic if current input is too vague
        if len(user_input.split()) <= 4 and not any(keyword in user_input.lower() for keyword in ["movie", "series", "anime", "show", "character", "actor", "actress", "plot"]):
            user_input = f"{previous_topic} {user_input}"

        # Store the most recent topic (if this seems like a new one)
        session["last_topic"] = user_input

        # Step 1: Try Wikipedia
        try:
            wiki_summary = wikipedia.summary(user_input, sentences=5)
            prompt = f"""You are a helpful assistant. Please answer the following user query using Wikipedia:

User: {user_input}

Wikipedia Summary: {wiki_summary}

Answer:"""
        except wikipedia.exceptions.DisambiguationError as e:
            prompt = f"""The user query was ambiguous. Try to help them understand the topic better.
Query: {user_input}
Disambiguation Options: {e.options[:5]}
Answer:"""
        except wikipedia.exceptions.PageError:
            # Step 2: Fallback to TMDb
            tmdb_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={user_input}"
            try:
                response = requests.get(tmdb_url, timeout=10)
                response.raise_for_status()
                results = response.json().get("results", [])
            except Exception as e:
                results = []

            if results:
                movie = results[0]
                title = movie.get("title", "Unknown")
                overview = movie.get("overview", "No overview available.")
                year = movie.get("release_date", "")[:4]
                prompt = f"""You are a helpful movie assistant.
A user is asking about the movie "{title}" ({year}).
Here is some info about it:
Overview: {overview}
User Question: {user_input}
Answer:"""
            else:
                prompt = f"No relevant info found in Wikipedia or TMDb. User asked: {user_input}"

        try:
            result = subprocess.run(
                f'ollama run gemma3:4b "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )

            print("🔧 SUBPROCESS STDOUT:")
            print(result.stdout)
            print("🔧 SUBPROCESS STDERR:")
            print(result.stderr)

            if result.returncode != 0:
                reply = f"⚠️ Model error: {result.stderr.strip()}"
            elif not result.stdout.strip():
                reply = "⚠️ Empty model response."
            else:
                reply = result.stdout.strip()

        except Exception as e:
            print("🔥 Exception while calling model:", e)
            reply = f"⚠️ Error calling the model: {e}"

        return jsonify({"reply": reply})

    return render_template("chatbot.html", language_map=language_map)

@app.route("/clear_chat")
def clear_chat():
    flask_session.pop("last_topic", None)
    return render_template("chatbot.html", language_map=language_map)
@app.route('/deep_dive', methods=['POST'])
def deep_dive():
    data = request.get_json()
    title = data.get("title", "")
    overview = data.get("overview", "")

    prompt = f"""You're an AI movie analyst known for punchy, stylish takes. Here's a short, fun analysis of the film "{title}":

"{overview}"

Write a compact and creative piece (under 200 words) that explores the film’s themes, vibes, or clever observations — like something from a smart blog or magazine. No breakdowns, no chatty tone. Just a unique perspective or metaphor. Bold key phrases using **markdown**, but avoid lists or headings."""

    try:
        result = subprocess.run(
            f'ollama run gemma3:4b "{prompt}"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )
        reply = result.stdout.strip() or "No analysis available."
    except Exception as e:
        reply = f"⚠️ Error generating analysis: {e}"

    return jsonify({"reply": reply})


# Run the app
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000) # Use 0.0.0.0 to be accessible externally if needed