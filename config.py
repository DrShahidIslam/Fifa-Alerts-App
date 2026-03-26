"""
Central configuration for the FIFA World Cup 2026 News Agent.
All settings, keywords, RSS feeds, and thresholds are defined here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# â”€â”€ API Keys â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

_gemini_keys_env = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
GEMINI_API_KEYS = [k.strip() for k in _gemini_keys_env.split(",") if k.strip()]
# Keep first key for backward compatibility if needed
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else None
WP_URL = os.getenv("WP_URL", "https://fifa-worldcup26.com")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
# Optional: foolproof publish via webhook on your server (avoids firewall blocking GitHub IPs)
WP_PUBLISH_WEBHOOK_URL = os.getenv("WP_PUBLISH_WEBHOOK_URL", "").strip()
WP_PUBLISH_SECRET = os.getenv("WP_PUBLISH_SECRET", "").strip()

# â”€â”€ RSS Feeds â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
RSS_FEEDS = {
    "ESPN FIFA": "https://www.espn.com/espn/rss/soccer/news",
    "BBC Sport Football": "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "FOX Sports": "https://api.foxsports.com/v2/content/optimized-rss?partnerKey=MB0Wehpmuj2lUhuRhQaafhBjAJqaPU244byPn1YI&size=30&tags=fs/soccer",
    "The Guardian Football": "https://www.theguardian.com/football/rss",
    "FIFA News": "https://www.fifa.com/rss/news.xml",
    "Sky Sports Football": "https://www.skysports.com/rss/12040",
    "Reuters Soccer": "https://www.reuters.com/rssFeed/sportsNews",
}

# â”€â”€ General Football Mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# When True, football-specific RSS feeds pass ALL stories without keyword
# filtering. Set to False for strict FIFA 2026 World Cup focus.
GENERAL_FOOTBALL_MODE = True

# RSS feeds that are football-only (only used when general mode is on)
FOOTBALL_ONLY_FEEDS = [
    "ESPN FIFA", "BBC Sport Football", "FOX Sports",
    "The Guardian Football", "Sky Sports Football",
]

# â”€â”€ Keyword Watchlists â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Primary keywords â€” FIFA World Cup 2026 and variants
PRIMARY_KEYWORDS = [
    "world cup 2026", "fifa 2026", "fifa world cup",
    "world cup qualifier", "world cup qualification",
    "world cup 26",
    # Football world cup variants (user-requested)
    "football world cup 2026", "football world cup",
    "football worldcup 2026", "football worldcup",
    "fifa worldcup 2026", "worldcup 2026",
    "2026 world cup", "2026 worldcup",
    "wc 2026", "wc2026",
]

# General football keywords â€” KEPT for reference but NOT included in ALL_KEYWORDS
# to maintain strict FIFA 2026 focus. Re-add to ALL_KEYWORDS if you want broader coverage.
INCLUDE_GENERAL_FOOTBALL_KEYWORDS = True

GENERAL_FOOTBALL_KEYWORDS = [
    "football", "soccer",
    "champions league", "europa league", "conference league",
    "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
    "nations league", "international friendly",
    "copa america", "euro 2028", "afcon",
    "club world cup", "super cup",
    "transfer", "signing", "transfer window",
    "manager sacked", "manager appointed",
    "penalty", "red card", "hat trick", "hat-trick",
    "injury update", "ruled out", "suspended",
    "var", "offside", "golden boot", "ballon d'or",
]

# Exclusion keywords â€” stories/trends containing these are discarded
EXCLUDE_KEYWORDS = [
    # Cricket
    "t20", "cricket", "ipl", "odi", "test match",
    "icc", "cwc", "psl", "bbl", "big bash", "ashes",
    "bcci", "ecb cricket", "wpl", "hundred cricket",
    "wicket", "bowled", "lbw", "batting average", "run rate",
    "over rate", "innings", "stumps", "maiden over",
    "ind vs", "pak vs", "india vs", "pakistan vs",
    "aus vs", "eng vs", "super 8", "super 12",
    # Other sports
    "rugby", "nfl", "nba", "baseball", "mlb",
    "tennis", "f1", "formula 1", "golf", "boxing", "ufc", "mma",
    "hockey", "nhl", "kabaddi", "badminton", "swimming",
    "cycling", "wrestling", "snooker", "winter olympics", "skiing",
]

# Team keywords â€” national teams only (no clubs to avoid league noise)
TEAM_KEYWORDS = [
    # Host nations
    "usa soccer", "us men's national team", "usmnt",
    "mexico national team", "el tri",
    "canada soccer", "canmnt",
    # Big names
    "argentina", "brazil", "france", "germany", "spain",
    "england", "portugal", "netherlands", "italy",
    "japan", "south korea", "australia", "saudi arabia",
    "nigeria", "senegal", "morocco", "cameroon",
    "colombia", "uruguay", "ecuador", "paraguay",
    "wales", "croatia", "belgium", "switzerland",
    "denmark", "serbia", "poland", "turkey",
    "iran", "qatar", "indonesia", "bahrain",
    "new zealand", "jamaica", "costa rica",
    "bolivia", "suriname", "new caledonia",
    "bosnia", "northern ireland", "georgia", "iceland",
]

# Player keywords â€” stars fans search for (no "world cup" suffix needed)
PLAYER_KEYWORDS = [
    "messi", "ronaldo", "mbappe", "haaland", "bellingham",
    "vinicius", "salah", "kane", "de bruyne",
    "neymar", "pedri", "saka", "pulisic", "alphonso davies",
    "son heung-min", "lamine yamal", "erling haaland",
    "bukayo saka", "phil foden", "bruno fernandes",
    "victor osimhen", "florian wirtz", "jamal musiala",
]

# Venue & logistics keywords
VENUE_KEYWORDS = [
    "metlife stadium", "estadio azteca", "sofi stadium",
    "hard rock stadium", "at&t stadium", "bmo field",
    "bc place", "nrg stadium", "lincoln financial field",
    "lumen field", "arrowhead stadium", "gillette stadium",
    "mercedes-benz stadium", "estadio akron", "estadio bbva",
    "world cup stadium", "world cup venue",
]

LOGISTICS_KEYWORDS = [
    "world cup tickets", "world cup ticket sale",
    "world cup visa", "world cup travel", "world cup hotel",
    "world cup broadcast", "world cup live stream",
    "world cup draw", "world cup schedule", "world cup fixtures",
    "world cup group", "world cup format",
    "world cup jersey", "world cup kit", "world cup ball",
    "world cup opening ceremony", "world cup final",
    "world cup bracket", "world cup wall chart",
]

# Combined master list for filtering (GENERAL_FOOTBALL_KEYWORDS excluded for strict WC focus)
_base_keywords = PRIMARY_KEYWORDS + TEAM_KEYWORDS + PLAYER_KEYWORDS + VENUE_KEYWORDS + LOGISTICS_KEYWORDS
if GENERAL_FOOTBALL_MODE and INCLUDE_GENERAL_FOOTBALL_KEYWORDS:
    ALL_KEYWORDS = _base_keywords + GENERAL_FOOTBALL_KEYWORDS
else:
    ALL_KEYWORDS = _base_keywords

# â”€â”€ Detection Settings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SPIKE_THRESHOLD = 2.0           # 2x above the rolling average = spike
SPIKE_MIN_SCORE = 35            # Minimum spike score to trigger alert
ROLLING_WINDOW_HOURS = 24       # Baseline window for comparison
SCAN_INTERVAL_MINUTES = 60      # How often the agent scans (60m = 24 req/day, well within NewsAPI 100 limit)
DEDUP_WINDOW_HOURS = 168        # Don't re-alert about the same story within 7 days

# â”€â”€ Google Trends Settings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
TRENDS_GEO = ""                 # Worldwide (empty = global)
TRENDS_KEYWORDS_PER_BATCH = 5   # pytrends allows max 5 keywords per request

# â”€â”€ WordPress Settings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
WP_DEFAULT_CATEGORY = "News"
WP_DEFAULT_STATUS = "draft"     # 'draft', 'pending', or 'publish'

# â”€â”€ Article Generation Settings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ARTICLE_MIN_WORDS = 800
ARTICLE_MAX_WORDS = 1500
ARTICLE_MIN_SOURCES = int(os.getenv("ARTICLE_MIN_SOURCES", "2"))
ARTICLE_MIN_UNIQUE_SOURCE_DOMAINS = int(os.getenv("ARTICLE_MIN_UNIQUE_SOURCE_DOMAINS", "2"))
GEMINI_MODEL = "gemini-2.5-flash"
# Set to True to skip AI image generation (saves Gemini quota; article publishes without featured image)
SKIP_AI_IMAGE = os.getenv("SKIP_AI_IMAGE", "false").lower() in ("true", "1", "yes")
# Imagen is paid-only; set True only if you have a paid Gemini plan. Free tier uses Pollinations + placeholder.
USE_GEMINI_IMAGEN = os.getenv("USE_GEMINI_IMAGEN", "false").lower() in ("true", "1", "yes")

# â”€â”€ Logging â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
LOG_FILE = "agent.log"
LOG_LEVEL = "INFO"
