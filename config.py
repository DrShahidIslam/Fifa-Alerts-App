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

# ── General Football Mode ────────────────────────────────────────────
# When True, football-specific RSS feeds pass ALL stories without keyword
# filtering (since they already only contain football content).
GENERAL_FOOTBALL_MODE = True

# RSS feeds that are football-only (all stories are relevant when general mode is on)
FOOTBALL_ONLY_FEEDS = [
    "ESPN FIFA", "BBC Sport Football", "FOX Sports",
    "The Guardian Football", "Sky Sports Football",
]

# ── Keyword Watchlists ────────────────────────────────────────────────
# Primary keywords — FIFA World Cup 2026 and variants
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

# General football keywords — catch all major football news
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
    # Top clubs (drive major news)
    "real madrid", "barcelona", "manchester united", "manchester city",
    "liverpool", "chelsea", "arsenal", "bayern munich",
    "psg", "paris saint-germain", "juventus", "inter milan",
    "ac milan", "atletico madrid", "borussia dortmund",
]

# Player keywords — stars fans search for (no "world cup" suffix needed)
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

# Combined master list for filtering
ALL_KEYWORDS = (
    PRIMARY_KEYWORDS + GENERAL_FOOTBALL_KEYWORDS + TEAM_KEYWORDS +
    PLAYER_KEYWORDS + VENUE_KEYWORDS + LOGISTICS_KEYWORDS
)

# ── Detection Settings ────────────────────────────────────────────────
SPIKE_THRESHOLD = 2.0           # 2x above the rolling average = spike
ROLLING_WINDOW_HOURS = 24       # Baseline window for comparison
SCAN_INTERVAL_MINUTES = 30      # How often the agent scans
DEDUP_WINDOW_HOURS = 168        # Don't re-alert about the same story within 7 days

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
