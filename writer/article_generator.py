"""
Article Generator — Uses Gemini to write SEO-optimized articles
from source material gathered by the source fetcher.
"""
import logging
import json
import re
import time
import html

from google import genai

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from writer.source_fetcher import fetch_multiple_sources
from writer.seo_prompt import (
    ARTICLE_WRAPPER_STYLE,
    CTA_BUTTON_STYLE,
    CTA_CONTAINER_STYLE,
    FAQ_CARD_STYLE,
    IMPORTANT_UPDATE_STYLE,
    KEY_FACTS_STYLE,
    build_article_prompt,
    get_verified_internal_links,
    _normalize_internal_url,
    _extract_entities_from_topic,
)
from gemini_client import generate_content_with_fallback

logger = logging.getLogger(__name__)

# Gemini retry handled by gemini_client


def _search_news_for_trend(keyword):
    """Search Google News RSS and NewsAPI to find background context for a trending keyword."""
    urls = []

    # 1. Google News RSS
    try:
        import feedparser
        import urllib.parse
        encoded_kw = urllib.parse.quote(keyword)
        rss_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:3]:
            if entry.link and entry.link not in urls:
                urls.append(entry.link)
    except Exception as e:
        logger.warning(f"Failed to fetch Google News RSS for trend: {e}")

    # 2. NewsAPI
    try:
        from newsapi import NewsApiClient
        from datetime import datetime, timedelta
        newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
        from_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
        results = newsapi.get_everything(
            q=keyword,
            language="en",
            sort_by="relevancy",
            from_param=from_date,
            page_size=5
        )
        if results.get("status") == "ok":
            for article in results.get("articles", [])[:3]:
                url = article.get("url")
                if url and url not in urls:
                    urls.append(url)
    except Exception as e:
        logger.warning(f"Failed to fetch NewsAPI for trend: {e}")

    return urls


def _dedupe_keep_order(values):
    seen = set()
    unique = []
    for value in values:
        normalized = (value or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique


def _normalize_whitespace(value):
    return re.sub(r"\s+", " ", (value or "")).strip()


def _trim_to_limit(text, limit):
    text = _normalize_whitespace(text)
    if len(text) <= limit:
        return text
    trimmed = text[: limit - 1].rstrip(" ,:;.-")
    cut = trimmed.rfind(" ")
    if cut > int(limit * 0.6):
        trimmed = trimmed[:cut]
    return trimmed.rstrip(" ,:;.-")


def _ensure_terminal_punctuation(text, punctuation="."):
    text = _normalize_whitespace(text).rstrip(" ,:;-/|")
    if not text:
        return ""
    if text[-1] not in ".!?":
        text = f"{text}{punctuation}"
    return text


def _clean_fragment(text):
    text = _normalize_whitespace(text)
    text = re.sub(r"^[\-\|\:,;.!?\s]+", "", text)
    text = re.sub(r"[\-\|\:,;\s]+$", "", text)
    return text


def _entity_from_title(article_title, primary_keyword):
    title = _clean_fragment(article_title)
    keyword = _clean_fragment(primary_keyword)
    if not title:
        return ""
    if keyword and title.lower() == keyword.lower():
        return ""
    if ":" in title:
        lead = _clean_fragment(title.split(":", 1)[0])
        if lead and lead.lower() != keyword.lower():
            return lead
    words = title.split()
    if 1 < len(words) <= 5 and title.lower() != keyword.lower():
        return title
    return ""


def _build_meta_title_candidate(primary_keyword, article_title="", seo_title=""):
    keyword = _clean_fragment(primary_keyword)
    article = _clean_fragment(article_title)
    seo = _clean_fragment(seo_title)
    entity = _entity_from_title(article, keyword)

    candidates = []
    if entity and keyword and entity.lower() != keyword.lower():
        candidates.extend([
            f"{keyword}: {entity} latest update",
            f"{keyword}: {entity} news",
        ])
    if keyword:
        candidates.extend([
            f"{keyword}: latest update",
            f"{keyword}: key facts and latest news",
            f"{keyword} latest news",
        ])
    if seo:
        candidates.append(seo if _contains_keyword(seo, keyword) else f"{keyword}: {seo}")
    if article and article.lower() != keyword.lower():
        candidates.append(article if _contains_keyword(article, keyword) else f"{keyword}: {article}")
    return [candidate for candidate in candidates if candidate]


def _build_meta_description_candidate(primary_keyword, primary_entity="", article_title="", meta_description=""):
    keyword = _clean_fragment(primary_keyword)
    entity = _clean_fragment(primary_entity) or _entity_from_title(article_title, keyword)
    meta = _clean_fragment(meta_description)

    candidates = []
    if meta:
        base = meta if _contains_keyword(meta, keyword) else f"{keyword}: {meta}"
        if entity and not _contains_keyword(base, entity):
            base = f"{base.rstrip('.! ')} involving {entity}"
        candidates.append(base)

    if keyword and entity and entity.lower() != keyword.lower():
        candidates.extend([
            f"Track the latest {keyword} update as {entity} drives the biggest talking point, with confirmed facts, context, and what happens next.",
            f"Follow the latest {keyword} news around {entity}, including confirmed developments, key context, and what to watch next.",
        ])
    if keyword:
        candidates.extend([
            f"Get the latest {keyword} update with confirmed facts, key context, and what to watch next as the story develops.",
            f"Discover the latest {keyword} news, including confirmed facts, key context, and the next major development to watch.",
        ])
    return [candidate for candidate in candidates if candidate]


def _contains_keyword(text, keyword):
    return bool(keyword and text and keyword.lower() in text.lower())


def _clean_topic_label(value):
    value = _normalize_whitespace((value or "").replace("_", " "))
    value = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", value)
    value = re.sub(r"^(general football|football|soccer)\s*[:\-]\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*[|:,-]+\s*$", "", value).strip()
    return value


def _clean_topic_for_editorial_use(topic_title):
    text = _clean_topic_label(topic_title)
    text = re.sub(r"^(rising search|trending)\s*:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsearch signal detected for\b", "", text, flags=re.IGNORECASE).strip(" -:|,")
    return text


def _strip_title_markup(value):
    value = _clean_topic_label(value)
    value = re.sub(r"[`#]+", "", value)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip(" -:|,")


def _dedupe_title_phrases(title):
    parts = [part.strip(" -:|,") for part in re.split(r"\s*[:|,-]\s*", title) if part.strip(" -:|,")]
    deduped = []
    seen = set()
    for part in parts:
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(part)
    return ": ".join(deduped) if deduped else title


def _build_article_title(raw_title, primary_keyword, topic_title, primary_entity=""):
    title = _dedupe_title_phrases(_strip_title_markup(raw_title or ""))
    topic = _strip_title_markup(topic_title)
    keyword = _strip_title_markup(primary_keyword)
    entity = _strip_title_markup(primary_entity)

    if not title or title.lower() in {"general football", "football", "soccer"}:
        title = topic or keyword

    if not _contains_keyword(title, keyword):
        lead = entity or topic
        if lead and lead.lower() != keyword.lower():
            title = f"{lead}: {keyword}"
        else:
            title = keyword or title

    title = re.split(r"\s+By\s+\w+", title, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    title = re.sub(r"\b(the endur\w+ quest.*|with immediate implications.*)$", "", title, flags=re.IGNORECASE).strip(" -:|,")

    segments = [seg.strip() for seg in re.split(r"\s*:\s*", title) if seg.strip()]
    if len(segments) > 2:
        title = ": ".join(segments[:2])

    if len(title) > 70:
        candidate = ""
        if entity and keyword and entity.lower() != keyword.lower():
            candidate = f"{entity}: {keyword}"
        elif keyword:
            candidate = keyword
        if topic and keyword and topic.lower() != keyword.lower():
            topic_words = topic.split()
            short_topic = " ".join(topic_words[:6]).strip(" -:|,")
            candidate = f"{short_topic}: {keyword}" if short_topic else candidate
        title = candidate or title

    if len(title) > 70:
        title = _trim_to_limit(title, 70)

    return title.strip(" -:|,")


def _derive_focus_keyword(primary_keyword, topic_title):
    keyword = _clean_topic_label(primary_keyword)
    generic_terms = {"general football", "football", "soccer", "sports", "general"}
    if keyword and keyword.lower() not in generic_terms and len(keyword) >= 4:
        return keyword

    title = _clean_topic_label(topic_title)
    if not title:
        return keyword or "football news"

    if ":" in title:
        title = title.split(":", 1)[1].strip()

    title = re.split(r"[|]", title, maxsplit=1)[0].strip()
    title = re.split(r"\s+and\s+|\s+vs\.?\s+|\s+v\s+", title, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    title = re.sub(r"\s*&\s*$", "", title).strip()
    words = title.split()
    if len(words) > 5:
        title = " ".join(words[:5])
    return title or keyword or "football news"


def _sanitize_slug(value):
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:70].strip("-")


def _summarize_source_quality(source_texts):
    """Build simple source-quality metadata for editorial QA and publish gating."""
    quality = {
        "source_count": 0,
        "unique_domains": [],
        "unique_domain_count": 0,
        "source_urls": [],
        "uses_aggregated_summary_only": False,
        "needs_manual_fact_check": False,
        "flags": [],
    }

    if not source_texts:
        quality["uses_aggregated_summary_only"] = True
        quality["needs_manual_fact_check"] = True
        quality["flags"].append("No extracted source material was available.")
        return quality

    urls = []
    domains = []
    only_aggregated = True
    for src in source_texts:
        domain = (src.get("source_domain") or "").strip().lower()
        url = (src.get("url") or "").strip()
        if domain:
            domains.append(domain)
        if url:
            urls.append(url)
        if domain and domain != "aggregated_summaries":
            only_aggregated = False

    unique_domains = []
    seen = set()
    for domain in domains:
        if domain and domain not in seen:
            seen.add(domain)
            unique_domains.append(domain)

    quality["source_count"] = len(source_texts)
    quality["unique_domains"] = unique_domains
    quality["unique_domain_count"] = len(unique_domains)
    quality["source_urls"] = urls
    quality["uses_aggregated_summary_only"] = only_aggregated

    if only_aggregated:
        quality["flags"].append("Only aggregated topic summaries were available.")
    if quality["source_count"] < getattr(config, "ARTICLE_MIN_SOURCES", 2):
        quality["flags"].append(
            f"Only {quality['source_count']} extracted source(s); target is at least {getattr(config, 'ARTICLE_MIN_SOURCES', 2)}."
        )
    if quality["unique_domain_count"] < getattr(config, "ARTICLE_MIN_UNIQUE_SOURCE_DOMAINS", 2):
        quality["flags"].append(
            "Not enough independent source domains for confident live publication."
        )

    quality["needs_manual_fact_check"] = bool(quality["flags"])
    return quality


def _source_title_terms(source_texts, limit=3):
    terms = []
    for src in (source_texts or [])[:limit]:
        title = _clean_topic_label(src.get("title", ""))
        if title:
            terms.append(title)
    return _dedupe_keep_order(terms)


def _derive_keyword_strategy(topic_title, matched_keyword, source_texts=None):
    primary = _derive_focus_keyword(matched_keyword, topic_title)
    candidates = []
    cleaned_topic = _clean_topic_for_editorial_use(topic_title)
    if cleaned_topic and cleaned_topic.lower() != primary.lower():
        candidates.append(cleaned_topic)

    entities = _extract_entities_from_topic(topic_title, matched_keyword or "", source_texts)
    candidates.extend(entities.get("players", []))
    candidates.extend(entities.get("teams", []))
    candidates.extend(entities.get("competitions", []))
    candidates.extend(_source_title_terms(source_texts))

    secondary = []
    supporting = []
    seen = {primary.lower()}
    for item in candidates:
        cleaned = _clean_topic_label(item)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        if len(secondary) < 4:
            secondary.append(cleaned)
        elif len(supporting) < 8:
            supporting.append(cleaned)

    return {
        "primary": primary,
        "secondary": secondary,
        "supporting": supporting,
    }


def _build_research_queries(topic, source_texts=None):
    topic_title = _clean_topic_for_editorial_use(topic.get("topic", ""))
    matched_keyword = _clean_topic_label(topic.get("matched_keyword", ""))
    strategy = _derive_keyword_strategy(topic_title, matched_keyword, source_texts)

    queries = []
    if topic_title:
        queries.append(topic_title)
        queries.append(f"{topic_title} world cup")
    if matched_keyword and matched_keyword.lower() != topic_title.lower():
        queries.append(matched_keyword)
        queries.append(f"{matched_keyword} latest")
    for item in strategy["secondary"][:3]:
        queries.append(item)
        queries.append(f"{item} world cup")
    for src in (topic.get("stories") or [])[:3]:
        title = _clean_topic_label(src.get("title", ""))
        if title:
            queries.append(title)

    return _dedupe_keep_order(queries)[:getattr(config, "ARTICLE_RESEARCH_QUERY_LIMIT", 6)]


def _discover_additional_source_urls(topic, existing_urls=None, source_texts=None):
    discovered = list(existing_urls or [])
    for query in _build_research_queries(topic, source_texts=source_texts):
        for url in _search_news_for_trend(query):
            if url not in discovered:
                discovered.append(url)
    return discovered


def _build_meta_title(seo_title, primary_keyword, article_title=""):
    for candidate in _build_meta_title_candidate(primary_keyword, article_title=article_title, seo_title=seo_title):
        candidate = _clean_fragment(candidate)
        if not candidate:
            continue
        if not _contains_keyword(candidate, primary_keyword):
            continue
        candidate = _trim_to_limit(candidate, 60)
        if candidate and candidate.lower() != _normalize_whitespace(article_title).lower():
            return _clean_fragment(candidate)
    return _trim_to_limit(_clean_fragment(primary_keyword), 60)


def _build_meta_description(meta_description, primary_keyword, primary_entity="", article_title=""):
    candidates = _build_meta_description_candidate(
        primary_keyword,
        primary_entity=primary_entity,
        article_title=article_title,
        meta_description=meta_description,
    )

    best = ""
    for candidate in candidates:
        candidate = _ensure_terminal_punctuation(candidate)
        if not _contains_keyword(candidate, primary_keyword):
            continue
        if primary_entity and not _contains_keyword(candidate, primary_entity):
            continue
        candidate = _trim_to_limit(candidate, 155)
        candidate = _ensure_terminal_punctuation(candidate)
        if len(candidate) >= 145:
            return candidate
        if len(candidate) > len(best):
            best = candidate

    if best:
        filler = " Latest facts, analysis, and next steps."
        while len(best) < 145 and filler:
            expanded = _trim_to_limit(f"{best.rstrip('.! ')}.{filler}", 155)
            expanded = _ensure_terminal_punctuation(expanded)
            if len(expanded) <= len(best):
                break
            best = expanded
            filler = ""
        return best

    fallback = _ensure_terminal_punctuation(f"Get the latest {primary_keyword} update with confirmed facts and what to watch next")
    return _trim_to_limit(fallback, 155)


def _strip_html_tags(value):
    return html.unescape(re.sub(r"<[^>]+>", " ", value or ""))


def _clean_sentence_fragment(value, limit=180):
    text = _normalize_whitespace(_strip_html_tags(value))
    text = re.sub(r"^[\-:;,. ]+", "", text)
    if len(text) > limit:
        text = _trim_to_limit(text, limit)
    return text


def _derive_intro_facts(topic_title, source_texts=None):
    facts = []
    seen = set()
    for candidate in [topic_title] + [src.get("title", "") for src in (source_texts or [])[:3]]:
        cleaned = _clean_sentence_fragment(candidate, limit=140)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        facts.append(cleaned)
    return facts


def _derive_analysis_context(topic_title, primary_keyword, source_texts=None):
    entities = _extract_entities_from_topic(topic_title, primary_keyword, source_texts)
    focus = entities.get("primary_entity") or _clean_topic_label(topic_title) or primary_keyword
    team_or_comp = ""
    if entities.get("teams"):
        team_or_comp = entities["teams"][0]
    elif entities.get("competitions"):
        team_or_comp = entities["competitions"][0]

    source_fact = ""
    for src in source_texts or []:
        title = _clean_sentence_fragment(src.get("title", ""), limit=110)
        if title:
            source_fact = title
            break

    return {
        "focus": focus,
        "team_or_comp": team_or_comp,
        "source_fact": source_fact,
    }


# Banned openers that produce weak, non-engaging first paragraphs
_BANNED_OPENERS = (
    "in this article", "this article", "fans are asking",
    "let's", "here's", "today we", "read on", "we explore",
    "welcome to", "in today's", "are you", "have you",
    "if you're", "whether you",
)


def _ensure_intro_hook(content, primary_keyword, topic_title, primary_entity="", source_texts=None):
    """Ensure the first paragraph is substantive, entity-rich, and answers search intent.

    If the AI-generated intro is too short, lacks the keyword, or starts with a
    banned opener, inject a contextual hook that names the primary entity and
    states the key development. Never inject a generic spacer.
    """
    if not content:
        return content

    first_paragraph = re.search(r"<p[^>]*>(.*?)</p>", content, re.IGNORECASE | re.DOTALL)
    if not first_paragraph:
        # No <p> at all — prepend a contextual hook
        hook = _build_contextual_hook(
            primary_keyword,
            topic_title,
            primary_entity,
            source_texts=source_texts,
        )
        return hook + content

    first_text = html.unescape(re.sub(r"<[^>]+>", "", first_paragraph.group(1))).strip()
    word_count = len(first_text.split())

    is_too_short = word_count < 18
    lacks_keyword = not _contains_keyword(first_text, primary_keyword)
    weak_open = first_text.lower().startswith(_BANNED_OPENERS)

    if is_too_short or lacks_keyword or weak_open:
        hook = _build_contextual_hook(
            primary_keyword,
            topic_title,
            primary_entity,
            source_texts=source_texts,
        )
        return content[:first_paragraph.start()] + hook + content[first_paragraph.end():]
    return content


def _build_contextual_hook(primary_keyword, topic_title, primary_entity="", source_texts=None):
    """Build an entity-rich, search-intent-satisfying intro hook.

    Uses the primary entity and topic title to create a specific sentence
    rather than a generic filler paragraph.
    """
    entity = primary_entity or _clean_topic_label(topic_title) or primary_keyword

    facts = _derive_intro_facts(topic_title, source_texts=source_texts)
    primary_fact = facts[0] if facts else f"{entity} has emerged as a major talking point"
    secondary_fact = facts[1] if len(facts) > 1 else ""

    first_sentence = f"{entity} is driving the latest {primary_keyword} update as {primary_fact}."
    if secondary_fact and secondary_fact.lower() not in primary_fact.lower():
        second_sentence = (
            f"This matters because {secondary_fact[0].lower() + secondary_fact[1:]} could shift selection, momentum, "
            f"or the wider tournament picture."
        )
    else:
        second_sentence = (
            "This matters because the development changes the immediate outlook for fans, squads, and the wider tournament picture."
        )

    return f"<p>{_normalize_whitespace(first_sentence)} {_normalize_whitespace(second_sentence)}</p>"


def _ensure_value_add_paragraph(content, primary_keyword, topic_title, source_texts=None):
    if not content:
        return content

    if re.search(r"why this matters|why it matters|impact on|what this means", content, re.IGNORECASE):
        return content

    context = _derive_analysis_context(topic_title, primary_keyword, source_texts=source_texts)
    focus = context["focus"]
    team_or_comp = context["team_or_comp"]
    source_fact = context["source_fact"]
    heading_options = [
        "Why this matters",
        "Why the update matters",
        f"What {focus} changes next" if focus else "What changes next",
        f"The bigger picture for {team_or_comp}" if team_or_comp else "The bigger picture",
    ]
    heading = next((item for item in heading_options if item), "Why this matters")

    paragraph_options = [
        (
            f"<p>{focus} is now more than a one-cycle headline because it can alter selection decisions, match preparation, "
            f"and the way supporters read the broader tournament picture.</p>"
            f"<p>{source_fact or focus} gives this story weight beyond rumor, and the next confirmed update should clarify whether the momentum around {primary_keyword} becomes a lasting shift.</p>"
        ),
        (
            f"<p>{focus} matters because stories like this often reshape expectations before coaches, federations, and fans say so openly.</p>"
            f"<p>For {team_or_comp or 'the wider World Cup 2026 race'}, the real impact is whether this development changes planning, confidence, or the next round of decisions linked to {primary_keyword}.</p>"
        ),
        (
            f"<p>{focus} could quickly move from talking point to practical issue if the next fixtures, squad calls, or official statements reinforce the current direction.</p>"
            f"<p>That is why {primary_keyword} is worth tracking closely now rather than waiting for a final outcome.</p>"
        ),
    ]

    seed_text = f"{focus}|{primary_keyword}|{team_or_comp}|{source_fact}"
    variant_index = sum(ord(ch) for ch in seed_text) % len(paragraph_options)
    impact_block = f"<h2>{heading}</h2>{paragraph_options[variant_index]}"

    paragraphs = list(re.finditer(r"<p[^>]*>.*?</p>", content, re.IGNORECASE | re.DOTALL))
    if len(paragraphs) >= 2:
        insert_at = paragraphs[1].end()
        return content[:insert_at] + impact_block + content[insert_at:]
    if paragraphs:
        insert_at = paragraphs[0].end()
        return content[:insert_at] + impact_block + content[insert_at:]
    return impact_block + content


def _apply_seo_guards(article, primary_keyword, topic_title, source_texts=None):
    primary_keyword = _derive_focus_keyword(primary_keyword, topic_title)
    if not primary_keyword:
        return article

    article["focus_keyword"] = primary_keyword

    # Extract entities for use in meta and intro guards
    entities = _extract_entities_from_topic(topic_title, primary_keyword, source_texts)
    primary_entity = entities.get("primary_entity", "")

    title = _build_article_title(
        article.get("title") or topic_title,
        primary_keyword,
        topic_title,
        primary_entity=primary_entity,
    )
    article["title"] = title
    seo_title = article.get("seo_title") or article["title"]
    article["seo_title"] = _build_meta_title(seo_title, primary_keyword, article_title=article["title"])

    article["meta_description"] = _build_meta_description(
        article.get("meta_description"),
        primary_keyword,
        primary_entity=primary_entity,
        article_title=article["title"],
    )

    slug = _sanitize_slug(article.get("slug"))
    if not slug or primary_keyword.lower().replace(" ", "-") not in slug:
        slug = _sanitize_slug(primary_keyword)
    article["slug"] = slug

    content = article.get("content", "")
    content = _ensure_intro_hook(
        content,
        primary_keyword,
        topic_title,
        primary_entity=primary_entity,
        source_texts=source_texts,
    )
    content = _ensure_value_add_paragraph(content, primary_keyword, topic_title, source_texts=source_texts)
    content = _normalize_generated_ui_blocks(content)
    content = _sanitize_dark_theme_text_colors(content)
    article["content"] = content
    article["full_content"] = content
    return article


def _remove_search_trend_talk(content):
    """Strip low-value paragraphs about search buzz instead of the story itself."""
    if not content:
        return content

    patterns = [
        r"<p[^>]*>[^<]*(?:trending on google|rising search|search volume|search interest)[^<]*</p>",
        r"<p[^>]*>[^<]*(?:fans are searching|people are searching|searched a lot|being searched)[^<]*</p>",
        r"<h2[^>]*>[^<]*(?:why .* is trending|why .* is being searched)[^<]*</h2>\s*<p[^>]*>.*?</p>",
    ]
    cleaned = content
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def generate_article(topic, source_urls=None):
    """
    Generate a complete SEO-optimized article for a trending topic.

    Args:
        topic: dict from spike_detector with keys: topic, sources, stories, matched_keyword, top_url
        source_urls: optional list of URLs to fetch source material from.
                     If None, uses URLs from topic['stories'].

    Returns:
        dict with keys: title, meta_description, slug, tags, category,
                        content (HTML), faq_html, word_count, sources_used
        or None if generation fails
    """
    topic = dict(topic or {})
    topic["topic"] = _clean_topic_for_editorial_use(topic.get("topic", "Unknown"))
    logger.info(f"Generating article for: {topic.get('topic', 'Unknown')}")

    # Step 1: Gather source material
    if source_urls is None:
        source_urls = []
        for story in topic.get("stories", []):
            url = story.get("url", "")
            if url and url.startswith("http"):
                source_urls.append(url)

    # Also add the top_url if available
    top_url = topic.get("top_url", "")
    if top_url and top_url not in source_urls:
        source_urls.insert(0, top_url)

    # Trend-led topics should trigger a wider reporting search before drafting.
    is_pure_trend = (not source_urls) or all("trends.google.com" in url for url in source_urls)
    if is_pure_trend:
        keyword = topic.get("matched_keyword") or topic.get("topic", "")
        logger.info(f"  Trend-led topic detected. Expanding reporting search for: '{keyword}'")
        source_urls = _discover_additional_source_urls(topic, existing_urls=source_urls)

    logger.info(f"  Fetching {len(source_urls)} source URLs...")
    source_texts = fetch_multiple_sources(source_urls, max_sources=8)

    if len(source_texts) < getattr(config, "ARTICLE_MIN_SOURCES", 2):
        expanded_urls = _discover_additional_source_urls(topic, existing_urls=source_urls, source_texts=source_texts)
        if len(expanded_urls) > len(source_urls):
            logger.info(f"  Thin sourcing detected. Retrying extraction with {len(expanded_urls)} URLs.")
            source_urls = expanded_urls
            source_texts = fetch_multiple_sources(source_urls, max_sources=10)

    if not source_texts:
        logger.warning("  No source material could be extracted. Using topic summary only.")
        # Create minimal source from story summaries
        source_texts = [{
            "title": topic.get("topic", ""),
            "text": "\n".join(s.get("summary", "") for s in topic.get("stories", [])),
            "source_domain": "aggregated_summaries",
            "url": "",
        }]

    source_quality = _summarize_source_quality(source_texts)
    if source_quality["flags"]:
        logger.warning("  Source quality flags: " + " | ".join(source_quality["flags"]))

    keyword_strategy = _derive_keyword_strategy(
        topic.get("topic", "World Cup 2026 Update"),
        topic.get("matched_keyword", ""),
        source_texts=source_texts,
    )

    # Step 2: Build the prompt
    prompt = build_article_prompt(
        topic_title=topic.get("topic", "World Cup 2026 Update"),
        source_texts=source_texts,
        matched_keyword=topic.get("matched_keyword", ""),
        keyword_strategy=keyword_strategy,
    )

    # Step 3: Call Gemini (with retry)
    try:
        logger.info("  Calling Gemini API...")
        response = generate_content_with_fallback(
            model=config.GEMINI_MODEL,
            contents=prompt
        )
        raw_output = response.text
        logger.info(f"  Gemini responded ({len(raw_output)} chars)")

    except Exception as e:
        logger.error(f"  Gemini API error: {e}")
        raise

    # Step 4: Parse structured output
    article = _parse_article_output(raw_output)

    if article:
        article = _apply_seo_guards(
            article,
            topic.get("matched_keyword", ""),
            topic.get("topic", ""),
            source_texts=source_texts,
        )
        article["content"] = _remove_search_trend_talk(article.get("content", ""))
        article["full_content"] = article["content"]
        article["sources_used"] = [s.get("source_domain", "") for s in source_texts]
        article["source_urls"] = source_quality["source_urls"]
        article["source_quality"] = source_quality
        article["editorial_flags"] = source_quality["flags"]
        article["needs_manual_fact_check"] = source_quality["needs_manual_fact_check"]
        article["keyword_strategy"] = keyword_strategy
        article["word_count"] = len(article.get("content", "").split())
        logger.info(f"  Article generated: '{article['title']}' ({article['word_count']} words)")
    else:
        logger.error("  Failed to parse Gemini output")
        return None

    return article


def _extract_faqpage_json(text):
    """Extract FAQPage JSON-LD from text. Returns None if FAQPage is not present."""
    if not text:
        return None

    # Prefer script blocks with FAQPage schema.
    for m in re.finditer(
        r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>',
        text,
        re.DOTALL | re.IGNORECASE
    ):
        body = (m.group(1) or "").strip()
        if "FAQPage" in body:
            return body

    # Fallback: raw JSON objects (sometimes model emits JSON without script tags).
    for start_marker in ('{"@context"', '{ "@context"', "{'@context'"):
        search_from = 0
        while True:
            start = text.find(start_marker, search_from)
            if start == -1:
                break
            depth = 0
            in_string = False
            escape = False
            quote = None
            i = start
            while i < len(text):
                c = text[i]
                if escape:
                    escape = False
                    i += 1
                    continue
                if c == '\\' and in_string:
                    escape = True
                    i += 1
                    continue
                if in_string:
                    if c == quote:
                        in_string = False
                    i += 1
                    continue
                if c in ('"', "'"):
                    in_string = True
                    quote = c
                    i += 1
                    continue
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:i + 1].strip()
                        if "FAQPage" in candidate:
                            return candidate
                        search_from = i + 1
                        break
                i += 1
            else:
                break
    return None


def _extract_faq_pairs(content, max_pairs=4):
    """Extract FAQ Q/A pairs from HTML content."""
    if not content:
        return []

    faq_start = re.search(
        r'<h[23][^>]*>\s*(?:Frequently\s+Asked\s+Questions|FAQs?)\s*</h[23]>',
        content,
        re.IGNORECASE
    )
    segment = content[faq_start.start():] if faq_start else content

    pairs = []
    for q_html, a_html in re.findall(
        r'<h3[^>]*>\s*(.*?)\s*</h3>\s*<p[^>]*>\s*(.*?)\s*</p>',
        segment,
        re.IGNORECASE | re.DOTALL
    ):
        question = html.unescape(re.sub(r'<[^>]+>', '', q_html)).strip()
        answer = html.unescape(re.sub(r'<[^>]+>', '', a_html)).strip()
        if not question or not answer:
            continue
        if len(answer) < 20:
            continue
        if "?" not in question:
            question = question.rstrip(".:;") + "?"
        pairs.append({"q": question, "a": answer})
        if len(pairs) >= max_pairs:
            break
    return pairs


def _build_faqpage_json_from_content(content):
    """Build FAQPage JSON-LD from FAQ cards if schema is missing."""
    pairs = _extract_faq_pairs(content, max_pairs=4)
    if len(pairs) < 2:
        return None
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item["a"],
                },
            }
            for item in pairs
        ],
    }
    return json.dumps(schema, ensure_ascii=False, indent=2)


def _ensure_schema_in_html_block(faq_html):
    """Strip JSON-LD from visible FAQ and put it in a single wp:html block so it never displays as text."""
    if not faq_html:
        return faq_html
    schema_block = None
    # 1) Already in script tag: extract and wrap in wp:html
    script_match = re.search(
        r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>',
        faq_html, re.DOTALL | re.IGNORECASE
    )
    if script_match:
        json_content = script_match.group(1).strip()
        schema_block = '<!-- wp:html -->\n<script type="application/ld+json">\n' + json_content + '\n</script>\n<!-- /wp:html -->'
        faq_html = re.sub(r'<script\s+type=["\']application/ld\+json["\']\s*>.*?</script>', '', faq_html, flags=re.DOTALL | re.IGNORECASE)
    # 2) Raw JSON-LD (no script tag)
    json_str = _extract_faqpage_json(faq_html)
    if json_str:
        schema_block = '<!-- wp:html -->\n<script type="application/ld+json">\n' + json_str + '\n</script>\n<!-- /wp:html -->'
        idx = faq_html.find(json_str[:50])
        if idx != -1:
            end = idx + len(json_str)
            faq_html = (faq_html[:idx] + faq_html[end:]).strip()
        else:
            faq_html = faq_html.replace(json_str, "", 1).strip()
    faq_html = re.sub(r'\n{3,}', '\n\n', faq_html).strip()
    if schema_block:
        faq_html = (faq_html + "\n\n" + schema_block).strip()
    return faq_html


def _strip_faq_and_schema_from_content(content):
    """Remove FAQ section and JSON-LD schema if the model wrongly put them inside CONTENT."""
    if not content:
        return content
    while True:
        json_str = _extract_faqpage_json(content)
        if not json_str:
            break
        content = content.replace(json_str, "", 1).strip()
    content = re.sub(
        r'<script\s+type=["\']application/ld\+json["\']\s*>.*?</script>\s*',
        '',
        content, flags=re.DOTALL | re.IGNORECASE
    )
    content = re.sub(r'\n{3,}', '\n\n', content).strip()
    return content


def _wrap_content_with_padding(content):
    """Wrap article content in a Group block with padding for Kadence."""
    if not content or "wp:group" in content.strip()[:250]:
        return content
    return (
        '<!-- wp:group {"style":{"spacing":{"padding":{"top":"1.5rem","right":"2rem","bottom":"2.5rem","left":"2rem"}}}} -->\n'
        '<div class="wp-block-group" style="padding:1.5rem 2rem 2.5rem 2rem">\n\n'
        + content.strip() + "\n\n"
        + '</div>\n<!-- /wp:group -->'
    )


def _normalize_generated_ui_blocks(content):
    """Apply stable, responsive inline styles to generated callouts, CTA, and FAQ cards."""
    if not content:
        return content

    replacements = {
        "padding:1.5rem 2rem 2.5rem 2rem": ARTICLE_WRAPPER_STYLE,
        "border-left: 4px solid #e94560;padding: 1rem 1.25rem;margin: 1.5rem 0;border-radius: 0 8px 8px 0;background-color:#f9f9f9;color:#000000;": KEY_FACTS_STYLE,
        "padding: 1rem 1.25rem;margin: 1.5rem 0;border: 1px solid #ffc107;border-radius: 8px;background-color:#fffdf5;color:#000000;": IMPORTANT_UPDATE_STYLE,
        "display:block !important; padding:2rem !important; margin:2rem 0 !important; border-radius:12px !important; background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460) !important; text-align:center !important; box-shadow:0 10px 20px rgba(0,0,0,0.15) !important; border-left:5px solid #e94560 !important;": CTA_CONTAINER_STYLE,
        "margin: 1.5rem 0;padding: 1rem;background-color:#f9f9f9;border-radius: 8px;border:1px solid #ddd;overflow: hidden;color:#000000;": FAQ_CARD_STYLE,
    }
    for old_style, new_style in replacements.items():
        content = content.replace(old_style, new_style)

    content = re.sub(
        r'(<a[^>]*href=["\']https://fifa-worldcup26\.com/?["\'][^>]*style=["\'])[^"\']*(["\'])',
        lambda match: f"{match.group(1)}{CTA_BUTTON_STYLE}{match.group(2)}",
        content,
        flags=re.IGNORECASE,
    )
    return content


def _sanitize_dark_theme_text_colors(content):
    """Remove black inline text colors from normal article content on dark themes."""
    if not content:
        return content

    protected_blocks = []

    def _protect(match):
        protected_blocks.append(match.group(0))
        return f"__PROTECTED_BLOCK_{len(protected_blocks) - 1}__"

    light_box_pattern = re.compile(
        r"<div[^>]*style=[\"'][^\"']*(?:background-color:#f9f9f9|background-color:#fffdf5)[^\"']*[\"'][^>]*>.*?</div>",
        re.IGNORECASE | re.DOTALL,
    )
    content = light_box_pattern.sub(_protect, content)

    def _clean_tag_style(match):
        tag_name = match.group(1)
        attrs = match.group(2) or ""
        style_match = re.search(r'style=(["\'])(.*?)\1', attrs, re.IGNORECASE | re.DOTALL)
        if not style_match:
            return match.group(0)

        style_value = style_match.group(2)
        cleaned_style = re.sub(
            r"(?:^|;)\s*color\s*:\s*(?:#000|#000000|black)\s*;?",
            ";",
            style_value,
            flags=re.IGNORECASE,
        )
        cleaned_style = re.sub(r";{2,}", ";", cleaned_style).strip(" ;")

        if cleaned_style:
            new_attrs = attrs[:style_match.start()] + f'style="{cleaned_style}"' + attrs[style_match.end():]
        else:
            new_attrs = attrs[:style_match.start()] + attrs[style_match.end():]

        new_attrs = re.sub(r"\s{2,}", " ", new_attrs).rstrip()
        return f"<{tag_name}{new_attrs}>"

    content = re.sub(
        r"<(h[1-6]|p|ul|ol|li)([^>]*)>",
        _clean_tag_style,
        content,
        flags=re.IGNORECASE,
    )

    for idx, block in enumerate(protected_blocks):
        content = content.replace(f"__PROTECTED_BLOCK_{idx}__", block)

    return content


def _clean_hallucinated_links(content):
    """
    Find all internal links in the content, and if they do not exist
    in our verified links list, replace the <a> tag with just the anchor text.
    This prevents hallucinated URLs from hurting SEO.
    """
    if not content:
        return content

    verified = get_verified_internal_links()
    valid_urls = {_normalize_internal_url(item["url"]) for item in verified}

    def _replace_link(match):
        href = match.group(1)
        anchor_text = match.group(2)
        href_clean = href.strip()

        # External links are fine, only check our domain
        if "fifa-worldcup26.com" not in href_clean and not href_clean.startswith("/"):
            return match.group(0)

        href_clean = _normalize_internal_url(href_clean)
        if not href_clean or href_clean not in valid_urls:
            logger.warning(f"Stripped hallucinated link: {href}")
            return anchor_text

        return re.sub(
            r'href=["\'][^"\']+["\']',
            f'href="{href_clean}"',
            match.group(0),
            count=1,
            flags=re.IGNORECASE,
        )

    cleaned = re.sub(
        r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        _replace_link,
        content,
        flags=re.IGNORECASE | re.DOTALL
    )

    return cleaned


def _parse_article_output(raw_text):
    """
    Parse the structured output from Gemini into article components.
    """
    try:
        result = {}
        label_order = [
            ("TITLE", "title"),
            ("SEO_TITLE", "seo_title"),
            ("META_DESCRIPTION", "meta_description"),
            ("SLUG", "slug"),
            ("TAGS", "tags_raw"),
            ("CATEGORY", "category"),
        ]
        label_map = dict(label_order)
        metadata = {field: [] for field in label_map.values()}
        current_field = None
        in_content = False

        for raw_line in raw_text.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if stripped == "---CONTENT_START---":
                in_content = True
                current_field = None
                continue
            if stripped == "---CONTENT_END---":
                in_content = False
                current_field = None
                continue
            if in_content:
                continue

            matched_label = False
            for label, field_name in label_order:
                prefix = f"{label}:"
                if stripped.startswith(prefix):
                    current_field = field_name
                    metadata[field_name].append(stripped[len(prefix):].strip())
                    matched_label = True
                    break
            if matched_label:
                continue

            if current_field and stripped:
                metadata[current_field].append(stripped)

        result["title"] = _normalize_whitespace(" ".join(metadata["title"]))
        result["seo_title"] = _normalize_whitespace(" ".join(metadata["seo_title"]))
        result["meta_description"] = _normalize_whitespace(" ".join(metadata["meta_description"]))
        result["slug"] = _normalize_whitespace(" ".join(metadata["slug"]))
        tags_raw = _normalize_whitespace(" ".join(metadata["tags_raw"]))
        result["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
        result["category"] = _normalize_whitespace(" ".join(metadata["category"])) or "News"

        # Extract CONTENT
        content_match = re.search(r'---CONTENT_START---(.*?)---CONTENT_END---', raw_text, re.DOTALL)
        content = content_match.group(1).strip() if content_match else ""

        # Post-process: ensure FAQ schema is in <script> tags, not raw text.
        # 1) Extract FAQPage JSON-LD from content if present.
        schema_json = _extract_faqpage_json(content)
        # 2) Strip raw schema + any mis-placed <script> schema from body
        content = _strip_faq_and_schema_from_content(content)
        # 3) If FAQ cards exist but schema is missing, synthesize schema.
        if not schema_json:
            schema_json = _build_faqpage_json_from_content(content)
        # 4) Store schema in a separate field instead of appending to content.
        # This prevents it from displaying as text on the frontend.
        if schema_json:
            result["faq_schema"] = schema_json

        # 5) Clean out hallucinated internal URLs
        content = _clean_hallucinated_links(content)
        content = _normalize_generated_ui_blocks(content)

        result["content"] = content
        result["full_content"] = content
        result["faq_html"] = ""

        # Validate we got essential fields
        if not result["title"] or not result["content"]:
            logger.warning("Missing essential fields, attempting raw extraction...")
            if not result["title"]:
                first_line = raw_text.strip().split("\n")[0]
                result["title"] = re.sub(r'^#+\s*', '', first_line)[:60]
            if not result["content"]:
                result["content"] = raw_text
                result["full_content"] = raw_text

        return result

    except Exception as e:
        logger.error(f"Parse error: {e}")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Test with a sample topic
    test_topic = {
        "topic": "Italy defeats Northern Ireland 2-0 in World Cup 2026 qualifier",
        "matched_keyword": "italy world cup",
        "stories": [
            {
                "title": "Italy through to World Cup playoffs final",
                "summary": "Italy beat Northern Ireland 2-0 at the Stadio Olimpico",
                "url": "https://www.bbc.com/sport/football",
                "source": "BBC Sport",
            }
        ],
        "sources": ["BBC Sport", "ESPN"],
        "top_url": "https://www.bbc.com/sport/football",
    }

    article = generate_article(test_topic)
    if article:
        print(f"\n{'=' * 60}")
        print(f"TITLE: {article['title']}")
        print(f"SLUG: {article['slug']}")
        print(f"META: {article['meta_description']}")
        print(f"TAGS: {', '.join(article['tags'])}")
        print(f"WORDS: {article['word_count']}")
        print(f"SOURCES: {', '.join(article['sources_used'])}")
        print(f"\nCONTENT PREVIEW:\n{article['content'][:500]}...")
