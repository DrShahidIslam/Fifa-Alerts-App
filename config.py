"""
Central configuration for the FIFA World Cup 2026 News Agent.
All settings, keywords, RSS feeds, and thresholds are defined here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# â€”â€” API Keys â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

_gemini_keys_env = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
GEMINI_API_KEYS = [k.strip() for k in _gemini_keys_env.split(",") if k.strip()]
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else None

WP_URL = os.getenv("WP_URL", "https://fifa-worldcup26.com")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
WP_PUBLISH_WEBHOOK_URL = os.getenv("WP_PUBLISH_WEBHOOK_URL", "").strip()
WP_PUBLISH_SECRET = os.getenv("WP_PUBLISH_SECRET", "").strip()

# â€”â€” RSS Feeds â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”
RSS_FEEDS = {
    "ESPN FIFA": "https://www.espn.com/espn/rss/soccer/news",
    "BBC Sport Football": "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "FOX Sports": "https://api.foxsports.com/v2/content/optimized-rss?partnerKey=MB0Wehpmuj2lUhuRhQaafhBjAJqaPU244byPn1YI&size=30&tags=fs/soccer",
    "The Guardian Football": "https://www.theguardian.com/football/rss",
    "FIFA News": "https://www.fifa.com/rss/news.xml",
    "Sky Sports Football": "https://www.skysports.com/rss/12040",
    "Reuters Soccer": "https://www.reuters.com/rssFeed/sportsNews",
}

GENERAL_FOOTBALL_MODE = True
FOOTBALL_ONLY_FEEDS = ["ESPN FIFA", "BBC Sport Football", "FOX Sports", "The Guardian Football", "Sky Sports Football"]

# â€”â€” Keyword Watchlists â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”
PRIMARY_KEYWORDS = [
    "world cup 2026", "fifa 2026", "fifa world cup",
    "world cup qualifier", "world cup qualification",
    "world cup 26", "football world cup 2026", "football world cup",
    "football worldcup 2026", "football worldcup",
    "fifa worldcup 2026", "worldcup 2026",
    "2026 world cup", "2026 worldcup", "wc 2026", "wc2026",
]

INCLUDE_GENERAL_FOOTBALL_KEYWORDS = True
GENERAL_FOOTBALL_KEYWORDS = [
    "football", "soccer", "champions league", "europa league", "conference league",
    "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
    "nations league", "international friendly", "copa america", "euro 2028", "afcon",
    "club world cup", "super cup", "transfer", "signing", "transfer window",
    "manager sacked", "manager appointed", "penalty", "red card", "hat trick", "hat-trick",
    "injury update", "ruled out", "suspended", "var", "offside", "golden boot", "ballon d'or",
]

EXCLUDE_KEYWORDS = [
    "t20", "cricket", "ipl", "odi", "test match", "icc", "cwc", "psl", "bbl", "big bash", "ashes",
    "bcci", "ecb cricket", "wpl", "hundred cricket", "wicket", "bowled", "lbw", "batting average",
    "run rate", "over rate", "innings", "stumps", "maiden over", "ind vs", "pak vs", "india vs",
    "pakistan vs", "aus vs", "eng vs", "super 8", "super 12", "rugby", "nfl", "nba", "baseball",
    "mlb", "tennis", "f1", "formula 1", "golf", "boxing", "ufc", "mma", "hockey", "nhl", "kabaddi",
    "badminton", "swimming", "cycling", "wrestling", "snooker", "winter olympics", "skiing",
]

TEAM_KEYWORDS = [
    "usa soccer", "us men's national team", "usmnt", "mexico national team", "el tri",
    "canada soccer", "canmnt", "argentina", "brazil", "france", "germany", "spain",
    "england", "portugal", "netherlands", "italy", "japan", "south korea", "australia",
    "saudi arabia", "nigeria", "senegal", "morocco", "cameroon", "colombia", "uruguay",
    "ecuador", "paraguay", "wales", "croatia", "belgium", "switzerland", "denmark",
    "serbia", "poland", "turkey", "iran", "qatar", "indonesia", "bahrain", "new zealand",
    "jamaica", "costa rica", "bolivia", "suriname", "new caledonia", "bosnia",
    "northern ireland", "georgia", "iceland",
]

PLAYER_KEYWORDS = [
    "messi", "ronaldo", "mbappe", "haaland", "bellingham", "vinicius", "salah", "kane",
    "de bruyne", "neymar", "pedri", "saka", "pulisic", "alphonso davies", "son heung-min",
    "lamine yamal", "erling haaland", "bukayo saka", "phil foden", "bruno fernandes",
    "victor osimhen", "florian wirtz", "jamal musiala",
]

VENUE_KEYWORDS = [
    "metlife stadium", "estadio azteca", "sofi stadium", "hard rock stadium", "at&t stadium",
    "bmo field", "bc place", "nrg stadium", "lincoln financial field", "lumen field",
    "arrowhead stadium", "gillette stadium", "mercedes-benz stadium", "estadio akron",
    "estadio bbva", "world cup stadium", "world cup venue",
]

LOGISTICS_KEYWORDS = [
    "world cup tickets", "world cup ticket sale", "world cup visa", "world cup travel",
    "world cup hotel", "world cup broadcast", "world cup live stream", "world cup draw",
    "world cup schedule", "world cup fixtures", "world cup group", "world cup format",
    "world cup jersey", "world cup kit", "world cup ball", "world cup opening ceremony",
    "world cup final", "world cup bracket", "world cup wall chart",
]

_base_keywords = PRIMARY_KEYWORDS + TEAM_KEYWORDS + PLAYER_KEYWORDS + VENUE_KEYWORDS + LOGISTICS_KEYWORDS
if GENERAL_FOOTBALL_MODE and INCLUDE_GENERAL_FOOTBALL_KEYWORDS:
    ALL_KEYWORDS = _base_keywords + GENERAL_FOOTBALL_KEYWORDS
else:
    ALL_KEYWORDS = _base_keywords

# â€”â€” Detection & Generation â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”
SPIKE_THRESHOLD = 2.0
SPIKE_MIN_SCORE = 35
ROLLING_WINDOW_HOURS = 24
SCAN_INTERVAL_MINUTES = 60
DEDUP_WINDOW_HOURS = 168

TRENDS_GEO = ""
TRENDS_KEYWORDS_PER_BATCH = 5

WP_DEFAULT_CATEGORY = "News"
WP_DEFAULT_STATUS = "draft"

ARTICLE_MIN_WORDS = 800
ARTICLE_MAX_WORDS = 1500
ARTICLE_MIN_SOURCES = int(os.getenv("ARTICLE_MIN_SOURCES", "2"))
ARTICLE_MIN_UNIQUE_SOURCE_DOMAINS = int(os.getenv("ARTICLE_MIN_UNIQUE_SOURCE_DOMAINS", "2"))
TREND_WATCHLIST_LIMIT = int(os.getenv("TREND_WATCHLIST_LIMIT", "25"))
ARTICLE_RESEARCH_QUERY_LIMIT = int(os.getenv("ARTICLE_RESEARCH_QUERY_LIMIT", "6"))

GEMINI_MODEL = "gemini-2.0-flash"
SKIP_AI_IMAGE = os.getenv("SKIP_AI_IMAGE", "false").lower() in ("true", "1", "yes")
USE_GEMINI_IMAGEN = os.getenv("USE_GEMINI_IMAGEN", "false").lower() in ("true", "1", "yes")
ALLOW_SOURCE_ARTICLE_IMAGES = os.getenv("ALLOW_SOURCE_ARTICLE_IMAGES", "true").lower() in ("true", "1", "yes")
SOURCE_IMAGE_FALLBACK_ON_AI_FAILURE = os.getenv("SOURCE_IMAGE_FALLBACK_ON_AI_FAILURE", "true").lower() in ("true", "1", "yes")

# --- SiliconFlow (Out of credits, deprioritized) ---
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "").strip()
SILICONFLOW_API_URL = os.getenv("SILICONFLOW_API_URL", "https://api.siliconflow.cn/v1/images/generations").strip()
SILICONFLOW_USER_INFO_URL = os.getenv("SILICONFLOW_USER_INFO_URL", "https://api.siliconflow.cn/v1/user/info").strip()
SILICONFLOW_IMAGE_MODEL = os.getenv("SILICONFLOW_IMAGE_MODEL", "Kwai-Kolors/Kolors").strip()
SILICONFLOW_NEGATIVE_PROMPT = os.getenv(
    "SILICONFLOW_NEGATIVE_PROMPT",
    "mutated hands, poorly drawn hands, extra fingers, missing fingers, malformed hands, "
    "deformed fingers, unnatural hands, bad anatomy, bad proportions, disfigured, blurry, "
    "worst quality, low quality",
).strip()
USE_SILICONFLOW_IMAGE = os.getenv("USE_SILICONFLOW_IMAGE", "true").lower() in ("true", "1", "yes")

# --- Hugging Face (New Primary) ---
HUGGING_FACE_TOKEN = os.getenv("HUGGING_FACE_TOKEN", "").strip()
HUGGING_FACE_API_URL = os.getenv("HUGGING_FACE_API_URL", "https://router.huggingface.co/hf-inference/models").strip()
HUGGING_FACE_IMAGE_MODEL = os.getenv("HUGGING_FACE_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell").strip()
USE_HUGGING_FACE_IMAGE = os.getenv("USE_HUGGING_FACE_IMAGE", "true").lower() in ("true", "1", "yes")

# --- Together AI (Secondary Proxy) ---
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "").strip()
TOGETHER_API_URL = os.getenv("TOGETHER_API_URL", "https://api.together.xyz/v1/images/generations").strip()
TOGETHER_IMAGE_MODEL = os.getenv("TOGETHER_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell").strip()
USE_TOGETHER_IMAGE = os.getenv("USE_TOGETHER_IMAGE", "true").lower() in ("true", "1", "yes")

# â€”â€” Logging â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”
LOG_FILE = "agent.log"
LOG_LEVEL = "INFO"
