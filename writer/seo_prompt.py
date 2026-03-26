"""
SEO Prompt Template - Master prompt used for Gemini article generation.
Enforces SEO best practices, editorial style, and internal linking.
All URLs below are real pages on fifa-worldcup26.com; do not add or invent others.
"""

import hashlib
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urlunparse

import requests

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)

# Real internal links only (from site). Add new blog posts here as they are published.
# Model must ONLY use links from this list; never hallucinate URLs.
INTERNAL_LINKS = {
    # Main / hub pages
    "home": {"url": "https://fifa-worldcup26.com/", "anchor": "World Cup 2026"},
    "tickets": {"url": "https://fifa-worldcup26.com/tickets/", "anchor": "World Cup 2026 tickets"},
    "venues": {"url": "https://fifa-worldcup26.com/venues/", "anchor": "host stadiums and venues"},
    "venues_usa": {"url": "https://fifa-worldcup26.com/venues/usa/", "anchor": "USA venues"},
    "venues_canada": {"url": "https://fifa-worldcup26.com/venues/canada/", "anchor": "Canada venues"},
    "venues_mexico": {"url": "https://fifa-worldcup26.com/venues/mexico/", "anchor": "Mexico venues"},
    "teams": {"url": "https://fifa-worldcup26.com/teams/", "anchor": "all qualified teams"},
    "teams_guide": {"url": "https://fifa-worldcup26.com/teams-guide/", "anchor": "teams guide"},
    "travel": {"url": "https://fifa-worldcup26.com/worldcup-travel-flights-hotels-visa/", "anchor": "travel and visa guide"},
    "broadcasting": {"url": "https://fifa-worldcup26.com/how-to-watch-worldcup/", "anchor": "how to watch World Cup 2026"},
    "qualifiers": {"url": "https://fifa-worldcup26.com/qualifiers/", "anchor": "World Cup 2026 qualifiers"},
    "matches": {"url": "https://fifa-worldcup26.com/matches/", "anchor": "match schedule"},
    "standings": {"url": "https://fifa-worldcup26.com/standings/", "anchor": "standings"},
    "groups": {"url": "https://fifa-worldcup26.com/groups/", "anchor": "groups"},
    "news": {"url": "https://fifa-worldcup26.com/news/", "anchor": "latest World Cup news"},
    "history": {"url": "https://fifa-worldcup26.com/world-cup-history/", "anchor": "World Cup history"},
    "records": {"url": "https://fifa-worldcup26.com/records/", "anchor": "records"},
    "sitemap": {"url": "https://fifa-worldcup26.com/sitemap/", "anchor": "sitemap"},
    # Blog / editorial (only real published posts)
    "beginner_guide": {"url": "https://fifa-worldcup26.com/world-cup-2026-beginner-guide/", "anchor": "beginner's guide to World Cup 2026"},
    "messi_2026": {"url": "https://fifa-worldcup26.com/is-messi-playing-world-cup-2026/", "anchor": "Messi at World Cup 2026"},
    "opening_match": {"url": "https://fifa-worldcup26.com/world-cup-2026-opening-match/", "anchor": "opening match"},
    "bracket": {"url": "https://fifa-worldcup26.com/fifa-world-cup-2026-bracket/", "anchor": "World Cup 2026 bracket"},
    "who_qualified": {"url": "https://fifa-worldcup26.com/who-has-qualified-world-cup-2026/", "anchor": "who has qualified"},
    "us_visa": {"url": "https://fifa-worldcup26.com/us-visa-guide-world-cup-2026/", "anchor": "US visa guide for World Cup"},
    "cheapest_cities": {"url": "https://fifa-worldcup26.com/cheapest-world-cup-2026-host-cities/", "anchor": "cheapest host cities"},
    "jerseys": {"url": "https://fifa-worldcup26.com/world-cup-2026-jerseys-kits/", "anchor": "World Cup 2026 jerseys"},
    "tickets_sale": {"url": "https://fifa-worldcup26.com/world-cup-2026-tickets-sale-dates/", "anchor": "ticket sale dates"},
    "ball_trionda": {"url": "https://fifa-worldcup26.com/world-cup-ball-trionda/", "anchor": "World Cup ball Trionda"},
    "italy_nigeria_qualify": {"url": "https://fifa-worldcup26.com/did-italy-and-nigeria-qualify-world-cup/", "anchor": "Italy and Nigeria qualification"},
    "cost_calculator": {"url": "https://fifa-worldcup26.com/world-cup-cost-calculator/", "anchor": "World Cup cost calculator"},
    "salah_transfer": {"url": "https://fifa-worldcup26.com/salah-liverpool-mls-saudi-transfer-rumors/", "anchor": "Salah transfer rumors"},
    "ifab_rules": {"url": "https://fifa-worldcup26.com/ifab-new-rules-football-world-cup-time-wasting/", "anchor": "new IFAB rules"},
    "sandy_grossman": {"url": "https://fifa-worldcup26.com/football-world-cup-2026-sandy-grossman-award/", "anchor": "Sandy Grossman Award"},
    "quansah_belgium": {"url": "https://fifa-worldcup26.com/john-quansah-injury-pain-pride-belgium/", "anchor": "John Quansah and Belgium"},
    "kane_vinicius": {"url": "https://fifa-worldcup26.com/kane-vinicius-contract-transfer-news/", "anchor": "Kane and Vinicius transfer news"},
    "qatar_iran_postponement": {"url": "https://fifa-worldcup26.com/qatar-football-postponement-iran-finalissima/", "anchor": "Qatar postponement and Iran Finalissima"},
    "messi_miami_comeback": {"url": "https://fifa-worldcup26.com/messis-first-goals-ignite-miami-comeback/", "anchor": "Messi's first goals and Miami comeback"},
}

_INTERNAL_LINKS_CACHE = {"loaded_at": 0, "links": None}
_INTERNAL_LINKS_CACHE_TTL_SECONDS = 6 * 60 * 60
_INTERNAL_LINKS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "internal_links_cache.json")

ARTICLE_WRAPPER_STYLE = "padding:clamp(1rem,3vw,1.5rem) clamp(1rem,4vw,2rem) clamp(2rem,5vw,2.5rem);"
KEY_FACTS_STYLE = "border-left:4px solid #e94560;padding:clamp(1rem,2.5vw,1.25rem);margin:1.5rem 0;border-radius:0 14px 14px 0;background-color:#f9f9f9;color:#000000;box-sizing:border-box;"
IMPORTANT_UPDATE_STYLE = "padding:clamp(1rem,2.5vw,1.25rem);margin:1.5rem 0;border:1px solid #ffc107;border-radius:14px;background-color:#fffdf5;color:#000000;box-sizing:border-box;"
CTA_CONTAINER_STYLE = "display:block !important;padding:clamp(1.25rem,4vw,2.25rem) !important;margin:2rem 0 !important;border-radius:20px !important;background:linear-gradient(135deg,#081225 0%,#0d2746 55%,#123b63 100%) !important;text-align:center !important;box-shadow:0 18px 40px rgba(0,0,0,0.28) !important;border:1px solid rgba(255,255,255,0.08) !important;border-left:5px solid #e94560 !important;box-sizing:border-box !important;overflow:hidden !important;"
CTA_BUTTON_STYLE = "display:inline-flex;align-items:center;justify-content:center;width:100%;max-width:420px;min-height:56px;padding:1rem 1.5rem;border-radius:14px;background:#e94560;color:#ffffff;text-decoration:none;font-weight:700;font-size:clamp(1rem,2.4vw,1.125rem);line-height:1.3;box-sizing:border-box;"
FAQ_CARD_STYLE = "margin:1rem 0;padding:clamp(1rem,2.4vw,1.35rem);background-color:#f9f9f9;border-radius:16px;border:1px solid #dddddd;overflow:hidden;color:#000000;box-sizing:border-box;"

ARTICLE_STRUCTURE_VARIANTS = [
    {
        "id": "A",
        "name": "Summary First",
        "instructions": (
            "Start with a direct summary section that answers the main query immediately. "
            "Then include a key facts callout, then context and implications, then the important update callout, "
            "then outlook and next steps, then CTA, then FAQ."
        ),
    },
    {
        "id": "B",
        "name": "Timeline First",
        "instructions": (
            "Start with what happened today and a short timeline section. "
            "Move to analysis and entity relationships. Place key facts callout after timeline, "
            "then important update callout, then practical implications, then CTA, then FAQ."
        ),
    },
    {
        "id": "C",
        "name": "Analysis First",
        "instructions": (
            "Open with why this matters and who is affected. "
            "Then cover confirmed facts and evidence with the key facts callout, then implications and scenarios, "
            "then important update callout, then what to watch next, then CTA, then FAQ."
        ),
    },
    {
        "id": "D",
        "name": "Fan Guide Angle",
        "instructions": (
            "Begin with a practical fan-focused overview. "
            "Then provide confirmed facts in the key facts callout, then explain schedule, teams, or travel impact, "
            "then important update callout, then strategic takeaways, then CTA, then FAQ."
        ),
    },
]


def _slug_to_anchor(url):
    """Create a human anchor text from URL slug."""
    path = urlparse(url).path.strip("/")
    if not path:
        return "World Cup 2026 hub"
    slug = path.split("/")[-1]
    words = [w for w in re.split(r"[-_]+", slug) if w]
    if not words:
        return "World Cup 2026 updates"
    pretty = " ".join(words[:6]).strip()
    return pretty[:1].upper() + pretty[1:]


def _normalize_internal_url(url):
    """Canonicalize site URLs so comparisons do not fail on slash/query variants."""
    if not url or not isinstance(url, str):
        return ""

    raw = url.strip()
    if not raw:
        return ""

    if raw.startswith("/"):
        raw = config.WP_URL.rstrip("/") + raw

    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return ""

    site = urlparse(config.WP_URL)
    if parsed.netloc.lower() != site.netloc.lower():
        return raw.rstrip("/")

    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if not path.endswith("/"):
        path = f"{path}/"

    normalized = parsed._replace(
        scheme=site.scheme,
        netloc=site.netloc,
        path=path,
        params="",
        query="",
        fragment="",
    )
    return urlunparse(normalized)


def _dedupe_urls(urls):
    unique = []
    seen = set()
    for url in urls:
        normalized = _normalize_internal_url(url)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _is_valid_internal_url(url):
    normalized = _normalize_internal_url(url)
    if not normalized or "wp-content" in normalized or "wp-json" in normalized or "xmlrpc.php" in normalized:
        return False
    if any(x in normalized for x in ("/feed", "/tag/", "/author/", "/comments/", ".jpg", ".png", ".webp", ".svg", ".pdf")):
        return False
    return normalized.startswith(config.WP_URL.rstrip("/") + "/")


def _extract_urls_from_sitemap_xml(xml_text):
    """Extract URLs from XML sitemap or sitemap index."""
    urls = []
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for node in root.findall(".//sm:loc", ns):
            if node.text:
                urls.append(node.text.strip())
    except Exception:
        pass
    return urls


def _fetch_dynamic_internal_links(max_links=40):
    """Discover verified internal URLs from live sitemap files."""
    base = config.WP_URL.rstrip("/")
    sitemap_candidates = [f"{base}/sitemap_index.xml", f"{base}/sitemap.xml"]
    headers = {"User-Agent": "FIFANewsAgent/1.0"}
    timeout = 12

    discovered_urls = []
    child_sitemaps = []
    for sm in sitemap_candidates:
        try:
            r = requests.get(sm, headers=headers, timeout=timeout)
            if r.status_code == 200 and r.text:
                locs = _extract_urls_from_sitemap_xml(r.text)
                if locs:
                    child_sitemaps.extend(locs)
        except Exception:
            continue

    prioritized = []
    for loc in child_sitemaps:
        if any(k in loc for k in ("post-sitemap", "news-sitemap", "page-sitemap", "category-sitemap")):
            prioritized.append(loc)
    for loc in child_sitemaps:
        if loc not in prioritized:
            prioritized.append(loc)

    for sm in prioritized[:12]:
        try:
            r = requests.get(sm, headers=headers, timeout=timeout)
            if r.status_code != 200:
                continue
            for loc in _extract_urls_from_sitemap_xml(r.text):
                if _is_valid_internal_url(loc):
                    discovered_urls.append(_normalize_internal_url(loc))
                if len(discovered_urls) >= max_links:
                    break
            if len(discovered_urls) >= max_links:
                break
        except Exception:
            continue

    return _dedupe_urls(discovered_urls)[:max_links]


def _load_cached_dynamic_links():
    try:
        if os.path.exists(_INTERNAL_LINKS_FILE):
            with open(_INTERNAL_LINKS_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                links = payload.get("links") or []
                if links:
                    return _dedupe_urls([l for l in links if isinstance(l, str)])
    except Exception:
        pass
    return []


def _save_cached_dynamic_links(links):
    try:
        payload = {"updated_at": time.time(), "links": _dedupe_urls(links)}
        with open(_INTERNAL_LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass


def append_to_dynamic_links_cache(url):
    """Append a newly published URL to the dynamic links cache so it can be used immediately."""
    normalized = _normalize_internal_url(url)
    if not normalized or not _is_valid_internal_url(normalized):
        return

    links = _load_cached_dynamic_links()
    if normalized not in links:
        links.append(normalized)
        _save_cached_dynamic_links(links)

        # Update memoized cache if already loaded
        if _INTERNAL_LINKS_CACHE["links"] is not None:
            anchor = _slug_to_anchor(normalized)
            existing = [item for item in _INTERNAL_LINKS_CACHE["links"] if item["url"] == normalized]
            if not existing:
                _INTERNAL_LINKS_CACHE["links"].append({"url": normalized, "anchor": anchor})


def get_verified_internal_links():
    """Return static + live-discovered internal links."""
    now = time.time()
    if _INTERNAL_LINKS_CACHE["links"] and (now - _INTERNAL_LINKS_CACHE["loaded_at"]) < _INTERNAL_LINKS_CACHE_TTL_SECONDS:
        return _INTERNAL_LINKS_CACHE["links"]

    merged = []
    seen_urls = set()

    for info in INTERNAL_LINKS.values():
        url = _normalize_internal_url(info.get("url", "").strip())
        anchor = info.get("anchor", "").strip()
        if not url or not anchor:
            continue
        if url not in seen_urls:
            seen_urls.add(url)
            merged.append({"url": url, "anchor": anchor})

    dynamic = _load_cached_dynamic_links()
    file_age_seconds = 0
    try:
        if os.path.exists(_INTERNAL_LINKS_FILE):
            file_age_seconds = time.time() - os.path.getmtime(_INTERNAL_LINKS_FILE)
    except OSError:
        pass

    if not dynamic or file_age_seconds > _INTERNAL_LINKS_CACHE_TTL_SECONDS:
        fetched = _fetch_dynamic_internal_links(max_links=60)
        if fetched:
            dynamic = _dedupe_urls(dynamic + fetched)
            _save_cached_dynamic_links(dynamic)

    for url in dynamic:
        if url not in seen_urls and _is_valid_internal_url(url):
            seen_urls.add(url)
            merged.append({"url": url, "anchor": _slug_to_anchor(url)})

    _INTERNAL_LINKS_CACHE["links"] = merged
    _INTERNAL_LINKS_CACHE["loaded_at"] = now
    return merged


def _extract_entities_from_topic(topic_title, matched_keyword, source_texts=None):
    """Extract known entities (players, teams, competitions) from topic data.

    Returns a dict with lists: players, teams, competitions, and a combined
    'primary_entity' string for use in intros and metas.
    """
    combined_text = f"{topic_title} {matched_keyword}".lower()
    if source_texts:
        for src in source_texts[:3]:
            combined_text += f" {(src.get('title') or '')[:200]}".lower()

    players = []
    for kw in config.PLAYER_KEYWORDS:
        if kw.lower() in combined_text and kw not in players:
            players.append(kw)

    teams = []
    for kw in config.TEAM_KEYWORDS:
        if kw.lower() in combined_text and kw not in teams:
            teams.append(kw)

    competitions = []
    comp_terms = [
        "world cup 2026", "world cup", "champions league", "europa league",
        "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
        "nations league", "copa america", "afcon", "qualifiers",
        "club world cup", "conference league",
    ]
    for comp in comp_terms:
        if comp in combined_text and comp not in competitions:
            competitions.append(comp)

    # Determine the single most important entity for intro/meta use
    primary_entity = ""
    if players:
        primary_entity = players[0].title()
    elif teams:
        primary_entity = teams[0].title()
    elif competitions:
        primary_entity = competitions[0].title()

    return {
        "players": [p.title() for p in players],
        "teams": [t.title() for t in teams],
        "competitions": [c.title() for c in competitions],
        "primary_entity": primary_entity,
    }


def _select_article_variant(topic_title, matched_keyword):
    """Pick a deterministic structure variant by topic."""
    seed = f"{topic_title}|{matched_keyword}".encode("utf-8")
    idx = int(hashlib.sha256(seed).hexdigest(), 16) % len(ARTICLE_STRUCTURE_VARIANTS)
    return ARTICLE_STRUCTURE_VARIANTS[idx]


def build_article_prompt(topic_title, source_texts, matched_keyword="", keyword_strategy=None):
    """
    Build the master SEO prompt for Gemini article generation.

    Args:
        topic_title: The trending topic headline
        source_texts: List of source article texts (from source_fetcher)
        matched_keyword: The primary keyword that triggered detection

    Returns:
        str: The complete prompt for Gemini
    """
    sources_block = ""
    for i, src in enumerate(source_texts[:5], 1):
        sources_block += f"""
--- SOURCE {i} ({src.get('source_domain', 'Unknown')}) ---
{src.get('text', '')[:2000]}
"""

    variant = _select_article_variant(topic_title, matched_keyword or topic_title)

    # --- Entity extraction for prompt enrichment ---
    entities = _extract_entities_from_topic(topic_title, matched_keyword or "", source_texts)
    entity_block_lines = []
    if entities["players"]:
        entity_block_lines.append(f"Players: {', '.join(entities['players'])}")
    if entities["teams"]:
        entity_block_lines.append(f"Teams: {', '.join(entities['teams'])}")
    if entities["competitions"]:
        entity_block_lines.append(f"Competitions: {', '.join(entities['competitions'])}")
    if entities["primary_entity"]:
        entity_block_lines.append(f"Primary Entity (use prominently): {entities['primary_entity']}")
    entity_block = "\n".join(entity_block_lines) if entity_block_lines else "No specific entities detected — derive entities from sources."

    verified_links = get_verified_internal_links()
    static_urls = {
        _normalize_internal_url(info["url"])
        for info in INTERNAL_LINKS.values()
        if info.get("url")
    }
    static_links = [item for item in verified_links if item["url"] in static_urls]
    dynamic_links = [item for item in verified_links if item["url"] not in static_urls]
    link_budget = max(0, 120 - len(static_links))
    selected_links = static_links + dynamic_links[-link_budget:]
    links_suggestion = "\n".join([
        f"  - [{item['anchor']}]({item['url']})"
        for item in selected_links
    ])

    keyword_strategy = keyword_strategy or {
        "primary": matched_keyword or topic_title,
        "secondary": [],
        "supporting": [],
    }
    secondary_keywords = ", ".join(keyword_strategy.get("secondary", [])[:4]) or "None"
    supporting_keywords = ", ".join(keyword_strategy.get("supporting", [])[:8]) or "None"

    prompt = f"""You are an expert sports journalist and master of Semantic Search, AEO (Answer Engine Optimization), and GEO (Generative Engine Optimization) for fifa-worldcup26.com.
Your articles must be engineered to rank by providing high information density, clear entity relationships, and direct answers.

TASK: Write a complete, publish-ready article about the following trending topic.

TRENDING TOPIC: {topic_title}
PRIMARY KEYWORD: {matched_keyword or topic_title}
FOCUS KEYWORD: {matched_keyword or topic_title}
SECONDARY KEYWORDS: {secondary_keywords}
SUPPORTING KEYWORDS: {supporting_keywords}

--- IDENTIFIED ENTITIES (emphasize these throughout the article) ---
{entity_block}

--- SOURCE MATERIAL (use ONLY these facts, do NOT fabricate) ---
{sources_block}

--- ADVANCED OPTIMIZATION RULES (NON-NEGOTIABLE) ---

1) KEYWORD STRATEGY:
   a) Treat the PRIMARY KEYWORD as the lead search target.
   b) Use SECONDARY KEYWORDS only where they genuinely improve topical coverage.
   c) Use SUPPORTING KEYWORDS to deepen context, FAQs, and entity relationships. Do not stuff them.
2) MAIN TITLE: Keep the visible article title compact and editorial, ideally 45-70 characters. It must include a clear hook, the exact main keyword, and if natural one supporting keyword or entity (player, team, or competition). Do not stack multiple clauses or repeat the same keyword.
3) META TITLE: Create a separate meta title for search results. It must contain the exact main keyword and MUST be strictly under 60 characters to avoid truncation.
4) META DESCRIPTION: The meta description must contain the main keyword and name the primary entity. It MUST be strictly between 145 and 155 characters to avoid truncation and fit perfectly within search snippets. Use an action verb plus curiosity gap.
5) FIRST PARAGRAPH — CRITICAL (this is the most important paragraph for user engagement and SEO):
   a) Must be 25-45 words: enough to be substantive, short enough to be punchy.
   b) Must directly answer the core search intent behind the topic in the very first sentence.
   c) Must name the primary entity (specific player, team, or competition) within the first 12 words.
   d) Must contain the main keyword naturally.
   e) BANNED openers: Never start with "In this article", "This article", "Fans are asking", "Let's", "Here's", "Today we", "Read on", "We explore", or any meta-commentary about the article itself. Start with the NEWS.
   f) The second sentence must state WHY this matters or what changed.
6) ENTITY-FIRST WRITING: Every section's opening sentence should lead with the most important entity name (person, team, or event) as the grammatical subject, not a vague pronoun or filler phrase.
7) VALUE-ADD ANALYSIS: Include one dedicated paragraph early in the article that goes beyond reporting. It must explain the likely impact of the news on fans, the team or player involved, upcoming matches, rankings, transfers, tactics, or the wider World Cup 2026 picture. This paragraph must be analytical, cautious, and original rather than a reworded summary.
8) KEYWORD PLACEMENT: Include the main keyword naturally in the short slug, opening paragraph, at least one H2, and the conclusion. Avoid stuffing.
9) AEO OPTIMIZATION (Answer Engines like Google AI Overview, Perplexity, ChatGPT):
   a) Write at least 3 sentences in the article that directly answer likely search questions (who, what, when, where, why, how) in a single, self-contained, factual sentence that an AI engine can quote verbatim.
   b) Use question-matching phrasing: open at least 2 sentences with "Who", "When", "Why", or "How" to mirror natural queries.
   c) Place the most direct answer within the first 150 words of the article.
10) GEO OPTIMIZATION (Generative Engine Optimization):
   a) Write with high information density: no filler sentences, every sentence must add a new fact or insight.
   b) Use clear entity co-occurrence: mention related entities together (e.g., player + team + competition in the same sentence) to strengthen knowledge graph signals.
   c) Include at least one "definitive statement" per section that states a verifiable fact clearly.
11) EXTERNAL LINKING: Include exactly ONE high-quality, high-authority external link (e.g., to BBC, ESPN, or official sites) naturally in the article to boost SEO.
12) STYLE: No emojis. No long punctuation dashes. Keep paragraphs short, max 2 sentences per <p>.
13) SCHEMA TAGS: FAQ JSON-LD must be wrapped in <script type="application/ld+json"> and </script>.
14) ORIGINALITY AND ATTRIBUTION:
   a) Do not paraphrase source articles section by section. Synthesize them into a single original narrative.
   b) Only state facts that are clearly supported by the source material above.
   c) When a fact is time-sensitive, attribute it naturally to the reporting or official update rather than presenting a stitched rumor summary as settled fact.
   d) If the source material is thin or conflicting, acknowledge uncertainty briefly instead of filling gaps.
15) THIN-CONTENT AVOIDANCE:
   a) Never discuss that the topic is trending, rising in searches, or popular on Google unless the story itself is literally about search data.
   b) Never use headings like "Why this is trending" or "Why fans are searching for this".
   c) Treat trend signals only as newsroom discovery signals, not as article substance.
   d) Every section must add confirmed facts, context, implications, or practical next steps.

--- ARTICLE STRUCTURE ---

1. TITLE: Visible on-page headline. Natural, editorial, compact, and usually 45-70 characters. Include a hook, the exact main keyword, and one supporting keyword or entity if it fits naturally.
2. SEO_TITLE: Separate meta title for search results. MUST be under 60 chars (to prevent truncation), and includes the exact main keyword.
3. META_DESCRIPTION: 145-155 chars (no more, no less), includes the exact main keyword AND the primary entity name, and uses a compelling action-oriented hook.
4. SLUG: extremely short, punchy, keyword-rich, lowercase, hyphens only, and based on the main keyword.
5. ARTICLE BODY: Magazine-quality HTML with a hook intro before the first H2.
6. FAQ: 3-4 schema-ready questions.

RULES:
- Do NOT output any <!-- wp:... --> comments.
- Output strictly raw HTML inside content.

VISUAL DESIGN LOCK (NON-NEGOTIABLE):
- Keep the exact same visual style system for every article: same padding, colors, border styles, and CTA look.
- Use this exact wrapper and style attributes:
  <div class="wp-block-group" style="{ARTICLE_WRAPPER_STYLE}"> ... </div>
- Include one Key Facts style callout using this exact style string:
  {KEY_FACTS_STYLE}
- Include one Important Update style callout using this exact style string:
  {IMPORTANT_UPDATE_STYLE}
- Include this exact CTA block style and button style:
  CTA container: {CTA_CONTAINER_STYLE}
  CTA button: {CTA_BUTTON_STYLE}
  CTA button must link to https://fifa-worldcup26.com/ and keep the same button styling.
- Include FAQ cards using this same style skeleton:
  {FAQ_CARD_STYLE}
- CRITICAL FIX FOR DARK THEME: The main article text MUST REMAIN UNSTYLED entirely so the website's dark theme forces it to white. However, since the Key Facts callout, Important Update callout, and FAQ cards use LIGHT background colors, you MUST explicitly add style="color:#000000;" to EVERY <p>, <ul>, <li>, and <h[1-6]> tag INSIDE those specific boxes ONLY. NEVER apply black text styling to normal paragraphs outside of those boxes!
- CTA TEXT COLOR RULE: Inside the CTA box, explicitly set the CTA heading and supporting paragraph text to color:#ffffff;, keep them centered, and keep the inner text wrapper at max-width:40rem;margin:0 auto; so it looks balanced on desktop and mobile.

STRUCTURE VARIATION (MANDATORY):
- Use this variant for this article.
- Variant ID: {variant['id']}
- Variant Name: {variant['name']}
- Variant Guide: {variant['instructions']}
- Keep all mandatory blocks: key facts callout, important update callout, CTA block, FAQ plus JSON-LD.
- Use 4-6 topical sections with unique H2 headings based on the story.
- At least one H2 must contain the main keyword or a very close natural variation.
- The opening 120 words must directly satisfy the likely search query before expanding into analysis.
- Include a standalone "Why this matters" or equivalent analysis section within the first half of the article.
- Do not use generic headings such as "Next Section" or "Another Section".
- Build comprehensive coverage: answer the update first, then expand with timeline, context, implications, affected teams or players, and what comes next.

INTERNAL LINKING RULES (STRICT):
- Use only genuine internal links from the list below. Do NOT invent URLs. If you hallucinate URLs that are not in this list, you will be penalized.
- Include 2-3 internal links naturally where relevant.
- Use exact URL and anchor text.

Allowed genuine internal links (copy URL and anchor exactly):
{links_suggestion}

EDITORIAL GUIDELINES:
- Tone: authoritative but conversational.
- Word count: 800-1500 words.
- Prioritize search intent coverage: what happened, why it matters, who is affected, and what comes next.
- Use a strong opening hook and a clean scannable structure with short sections, lists only where useful, and conclusion-led takeaways.
- Never fabricate facts, quotes, scores, or dates.
- If sources conflict, mention both perspectives.
- This is an unofficial fan guide. Never claim to represent FIFA.

OUTPUT FORMAT:
Return your response in this exact structured format:

TITLE: [your title]
SEO_TITLE: [your separate seo title]
META_DESCRIPTION: [your meta description]
SLUG: [your-slug]
TAGS: [tag1, tag2, tag3, ...]
CATEGORY: News

---CONTENT_START---
[Generate raw HTML only. Keep the exact visual design styles above, but follow the selected variant for section order and heading flow. Put FAQ JSON-LD inside <script type="application/ld+json">...</script>. Do not use ```html markdown tags.]
---CONTENT_END---
"""

    return prompt


def build_image_prompt(topic_title, article_content_snippet=""):
    """
    Build a prompt for Gemini Imagen to generate a featured image.

    Args:
        topic_title: The article title
        article_content_snippet: First 200 chars of article for context

    Returns:
        str: Image generation prompt
    """
    prompt = f"""Generate a premium, photorealistic editorial sports photograph suitable for a major sports news website like Getty Images or AFP.

Context: This image is for a World Cup 2026 article about: {topic_title}

CRITICAL INSTRUCTIONS:
- ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO NUMBERS, AND NO WATERMARKS anywhere in the image.
- DO NOT attempt to write the topic title or any keywords on the image.
- DO NOT include graphic design overlays, borders, or lower-thirds.

Style & Composition Guidelines:
- Photorealistic, high-end DSLR sports editorial photography
- Dynamic, energetic, and capturing the emotional intensity of international football
- Settings: either intense on-pitch action, passionate fans in the stadium, or dramatic stadium architecture
- Lighting: Natural stadium lighting, high-contrast, dramatic shadows, vibrant colors
- 16:9 aspect ratio, landscape orientation
- The image should evoke excitement and anticipation for the World Cup

Exclusions:
- Do NOT include recognizable real faces of actual specific players to avoid likeness issues
- Do NOT include official trademarked FIFA logos or specific team crests (use generic national colors/flags instead)"""

    return prompt
