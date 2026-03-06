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
from writer.seo_prompt import build_article_prompt, get_verified_internal_links
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


def _clean_hallucinated_links(content):
    """
    Find all internal links in the content, and if they do not exist
    in our verified links list, replace the <a> tag with just the anchor text.
    This prevents hallucinated URLs from hurting SEO.
    """
    if not content:
        return content

    verified = get_verified_internal_links()
    valid_urls = [item["url"] for item in verified]

    def _replace_link(match):
        href = match.group(1)
        anchor_text = match.group(2)
        href_clean = href.strip()

        # External links are fine, only check our domain
        if "fifa-worldcup26.com" not in href_clean and not href_clean.startswith("/"):
            return match.group(0)

        # Build absolute if relative
        if href_clean.startswith("/"):
            href_clean = f"https://fifa-worldcup26.com{href_clean}"

        # If the generated URL isn't in our valid list, strip the link tag
        if href_clean not in valid_urls:
            logger.warning(f"Stripped hallucinated link: {href_clean}")
            return anchor_text

        return match.group(0)

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
        title_match = re.search(r'TITLE:\s*(.+?)(?:\n|META_DESCRIPTION:)', raw_text, re.DOTALL)
        result["title"] = title_match.group(1).strip() if title_match else ""

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
        # 4) Re-attach schema wrapped in a wp:html + script block
        if schema_json:
            schema_block = (
                '<!-- wp:html -->\n'
                '<script type="application/ld+json">\n'
                + schema_json +
                '\n</script>\n'
                '<!-- /wp:html -->'
            )
            content = content.strip() + "\n\n" + schema_block

        # 5) Clean out hallucinated internal URLs
        content = _clean_hallucinated_links(content)

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
