"""
Central configuration for the FIFA World Cup 2026 News Agent.
All settings, keywords, RSS feeds, and thresholds are defined here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WP_URL = os.getenv("WP_URL", "https://fifa-worldcup26.com")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

# ── RSS Feeds ─────────────────────────────────────────────────────────
RSS_FEEDS = {
    "ESPN FIFA": "https://www.espn.com/espn/rss/soccer/news",
    "BBC Sport Football": "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "FOX Sports": "https://api.foxsports.com/v2/content/optimized-rss?partnerKey=MB0Wehpmuj2lUhuRhQaafhBjAJqaPU244byPn1YI&size=30&tags=fs/soccer",
    "The Guardian Football": "https://www.theguardian.com/football/rss",
    "FIFA News": "https://www.fifa.com/rss/news.xml",
    "Sky Sports Football": "https://www.skysports.com/rss/12040",
    "Reuters Soccer": "https://www.reuters.com/rssFeed/sportsNews",
}

# ── Keyword Watchlists ────────────────────────────────────────────────
# Primary keywords (must match at least one to be relevant)
PRIMARY_KEYWORDS = [
    "world cup 2026", "fifa 2026", "fifa world cup",
    "world cup qualifier", "world cup qualification",
    "world cup 26",
]

# Team keywords — all qualified + playoff teams
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

# Player keywords — stars fans search for
PLAYER_KEYWORDS = [
    "messi world cup", "ronaldo world cup", "mbappe world cup",
    "haaland world cup", "bellingham world cup", "vinicius world cup",
    "salah world cup", "kane world cup", "de bruyne world cup",
    "neymar world cup", "pedri world cup", "saka world cup",
    "pulisic world cup", "alphonso davies world cup",
    "son heung-min world cup", "lamine yamal world cup",
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

# Combined master list for filtering
ALL_KEYWORDS = (
    PRIMARY_KEYWORDS + TEAM_KEYWORDS + PLAYER_KEYWORDS +
    VENUE_KEYWORDS + LOGISTICS_KEYWORDS
)

# ── Detection Settings ────────────────────────────────────────────────
SPIKE_THRESHOLD = 2.0           # 2x above the rolling average = spike
ROLLING_WINDOW_HOURS = 24       # Baseline window for comparison
SCAN_INTERVAL_MINUTES = 30      # How often the agent scans
DEDUP_WINDOW_HOURS = 12         # Don't re-alert about the same story within 12h

# ── Google Trends Settings ────────────────────────────────────────────
TRENDS_GEO = ""                 # Worldwide (empty = global)
TRENDS_KEYWORDS_PER_BATCH = 5   # pytrends allows max 5 keywords per request

# ── WordPress Settings ────────────────────────────────────────────────
WP_DEFAULT_CATEGORY = "Blog"
WP_DEFAULT_STATUS = "draft"     # 'draft', 'pending', or 'publish'

# ── Article Generation Settings ────────────────────────────────────────
ARTICLE_MIN_WORDS = 800
ARTICLE_MAX_WORDS = 1500
GEMINI_MODEL = "gemini-2.0-flash"

# ── Logging ───────────────────────────────────────────────────────────
LOG_FILE = "agent.log"
LOG_LEVEL = "INFO"
