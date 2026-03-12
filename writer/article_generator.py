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


def _contains_keyword(text, keyword):
    return bool(keyword and text and keyword.lower() in text.lower())


def _clean_topic_label(value):
    value = _normalize_whitespace((value or "").replace("_", " "))
    value = re.sub(r"^(general football|football|soccer)\s*[:\-]\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*[|:,-]+\s*$", "", value).strip()
    return value


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


def _build_meta_title(seo_title, primary_keyword, article_title=""):
    seo_title = _normalize_whitespace(seo_title)
    if not _contains_keyword(seo_title, primary_keyword):
        seo_title = f"{primary_keyword}: {seo_title}" if seo_title else primary_keyword
    if article_title and seo_title.lower() == _normalize_whitespace(article_title).lower():
        seo_title = f"{primary_keyword}: impact and latest update"
    return _trim_to_limit(seo_title, 60)


def _build_meta_description(meta_description, primary_keyword, primary_entity=""):
    meta = _normalize_whitespace(meta_description)
    if not meta:
        entity_fragment = f" for {primary_entity}" if primary_entity and primary_entity.lower() != primary_keyword.lower() else ""
        meta = f"Get the latest on {primary_keyword}{entity_fragment}: confirmed facts, impact analysis, and what comes next."
    elif not _contains_keyword(meta, primary_keyword):
        meta = f"{primary_keyword}: {meta}"
    # Ensure entity presence for AEO
    if primary_entity and not _contains_keyword(meta, primary_entity):
        meta = meta.rstrip(".! ") + f" involving {primary_entity}."
    meta = _trim_to_limit(meta, 155)
    if len(meta) < 145:
        meta = _trim_to_limit(f"{meta} Key facts, timeline, and what to watch next.", 155)
    return meta


# Banned openers that produce weak, non-engaging first paragraphs
_BANNED_OPENERS = (
    "in this article", "this article", "fans are asking",
    "let's", "here's", "today we", "read on", "we explore",
    "welcome to", "in today's", "are you", "have you",
    "if you're", "whether you",
)


def _ensure_intro_hook(content, primary_keyword, topic_title, primary_entity=""):
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
        hook = _build_contextual_hook(primary_keyword, topic_title, primary_entity)
        return hook + content

    first_text = html.unescape(re.sub(r"<[^>]+>", "", first_paragraph.group(1))).strip()
    word_count = len(first_text.split())

    is_too_short = word_count < 18
    lacks_keyword = not _contains_keyword(first_text, primary_keyword)
    weak_open = first_text.lower().startswith(_BANNED_OPENERS)

    if is_too_short or lacks_keyword or weak_open:
        hook = _build_contextual_hook(primary_keyword, topic_title, primary_entity)
        return content[:first_paragraph.start()] + hook + content[first_paragraph.start():]
    return content


def _build_contextual_hook(primary_keyword, topic_title, primary_entity=""):
    """Build an entity-rich, search-intent-satisfying intro hook.

    Uses the primary entity and topic title to create a specific sentence
    rather than a generic filler paragraph.
    """
    entity = primary_entity or _clean_topic_label(topic_title) or primary_keyword

    # Derive what's happening from the topic title
    action = _clean_topic_label(topic_title)
    if not action or action.lower() == entity.lower():
        action = f"{entity} has emerged as a major talking point"
    else:
        # Shorten to something usable as a sentence fragment
        if len(action) > 80:
            action = action[:77].rsplit(" ", 1)[0]

    hook = (
        f"<p>{entity} is at the center of this {primary_keyword} development. "
        f"{action}, with immediate implications for fans, squads, and the wider tournament picture.</p>"
    )
    return hook


def _ensure_value_add_paragraph(content, primary_keyword, topic_title):
    if not content:
        return content

    if re.search(r"why this matters|why it matters|impact on|what this means", content, re.IGNORECASE):
        return content

    focus = _clean_topic_label(topic_title) or primary_keyword
    impact_block = (
        f"<h2>Why this matters</h2>"
        f"<p>Beyond the headline, {focus} could shape fan expectations, selection decisions, and the wider World Cup 2026 conversation. "
        f"The immediate effect will depend on how the story develops, but it already gives supporters and analysts a clearer signal about what to watch next.</p>"
    )

    paragraphs = list(re.finditer(r"<p[^>]*>.*?</p>", content, re.IGNORECASE | re.DOTALL))
    if len(paragraphs) >= 2:
        insert_at = paragraphs[1].end()
        return content[:insert_at] + impact_block + content[insert_at:]
    if paragraphs:
        insert_at = paragraphs[0].end()
        return content[:insert_at] + impact_block + content[insert_at:]
    return impact_block + content


def _apply_seo_guards(article, primary_keyword, topic_title):
    primary_keyword = _derive_focus_keyword(primary_keyword, topic_title)
    if not primary_keyword:
        return article

    article["focus_keyword"] = primary_keyword

    # Extract entities for use in meta and intro guards
    entities = _extract_entities_from_topic(topic_title, primary_keyword)
    primary_entity = entities.get("primary_entity", "")

    title = _clean_topic_label(article.get("title") or topic_title)
    if not title or title.lower() in {"general football", "football", "soccer"} or "_" in title:
        title = _clean_topic_label(topic_title) or primary_keyword
    if not _contains_keyword(title, primary_keyword):
        title = f"{primary_keyword}: {title}" if title else primary_keyword
    article["title"] = _trim_to_limit(title, 60)
    seo_title = article.get("seo_title") or article["title"]
    article["seo_title"] = _build_meta_title(seo_title, primary_keyword, article_title=article["title"])

    article["meta_description"] = _build_meta_description(
        article.get("meta_description"), primary_keyword, primary_entity=primary_entity
    )

    slug = _sanitize_slug(article.get("slug"))
    if not slug or primary_keyword.lower().replace(" ", "-") not in slug:
        slug = _sanitize_slug(primary_keyword)
    article["slug"] = slug

    content = article.get("content", "")
    content = _ensure_intro_hook(content, primary_keyword, topic_title, primary_entity=primary_entity)
    content = _ensure_value_add_paragraph(content, primary_keyword, topic_title)
    article["content"] = content
    article["full_content"] = content
    return article


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

    # Check if this is a pure trend alert (only trends.google.com URLs)
    is_pure_trend = True
    if not source_urls:
        is_pure_trend = True
    else:
        for url in source_urls:
            if "trends.google.com" not in url:
                is_pure_trend = False
                break

    if is_pure_trend:
        keyword = topic.get("matched_keyword") or topic.get("topic", "").replace("Rising search:", "").strip()
        logger.info(f"  Pure trend detected. Searching active news for: '{keyword}'")
        found_urls = _search_news_for_trend(keyword)
        if found_urls:
            source_urls.extend(found_urls)
            logger.info(f"  Found {len(found_urls)} background articles for context.")

    logger.info(f"  Fetching {len(source_urls)} source URLs...")
    source_texts = fetch_multiple_sources(source_urls, max_sources=8)

    if not source_texts:
        logger.warning("  No source material could be extracted. Using topic summary only.")
        # Create minimal source from story summaries
        source_texts = [{
            "title": topic.get("topic", ""),
            "text": "\n".join(s.get("summary", "") for s in topic.get("stories", [])),
            "source_domain": "aggregated_summaries",
            "url": "",
        }]

    # Step 2: Build the prompt
    prompt = build_article_prompt(
        topic_title=topic.get("topic", "World Cup 2026 Update"),
        source_texts=source_texts,
        matched_keyword=topic.get("matched_keyword", "")
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
        return None

    # Step 4: Parse structured output
    article = _parse_article_output(raw_output)

    if article:
        article = _apply_seo_guards(article, topic.get("matched_keyword", ""), topic.get("topic", ""))
        article["sources_used"] = [s.get("source_domain", "") for s in source_texts]
        article["word_count"] = len(article.get("content", "").split())
        logger.info(f"  Article generated: '{article['title']}' ({article['word_count']} words)")
    else:
        logger.error("  Failed to parse Gemini output")

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

        # Extract TITLE
        title_match = re.search(r'TITLE:\s*(.+?)(?:\n|SEO_TITLE:)', raw_text, re.DOTALL)
        result["title"] = title_match.group(1).strip() if title_match else ""

        # Extract SEO_TITLE
        seo_title_match = re.search(r'SEO_TITLE:\s*(.+?)(?:\n|META_DESCRIPTION:)', raw_text, re.DOTALL)
        result["seo_title"] = seo_title_match.group(1).strip() if seo_title_match else ""

        # Extract META_DESCRIPTION
        meta_match = re.search(r'META_DESCRIPTION:\s*(.+?)(?:\n|SLUG:)', raw_text, re.DOTALL)
        result["meta_description"] = meta_match.group(1).strip() if meta_match else ""

        # Extract SLUG
        slug_match = re.search(r'SLUG:\s*(.+?)(?:\n|TAGS:)', raw_text, re.DOTALL)
        result["slug"] = slug_match.group(1).strip() if slug_match else ""

        # Extract TAGS
        tags_match = re.search(r'TAGS:\s*(.+?)(?:\n|CATEGORY:)', raw_text, re.DOTALL)
        if tags_match:
            tags_raw = tags_match.group(1).strip()
            result["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            result["tags"] = []

        # Extract CATEGORY
        cat_match = re.search(r'CATEGORY:\s*(.+?)(?:\n|---)', raw_text, re.DOTALL)
        result["category"] = cat_match.group(1).strip() if cat_match else "News"

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
