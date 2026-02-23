"""
Article Generator — Uses Gemini to write SEO-optimized articles
from source material gathered by the source fetcher.
"""
import logging
import re

from google import genai

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from writer.source_fetcher import fetch_multiple_sources
from writer.seo_prompt import build_article_prompt

logger = logging.getLogger(__name__)


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
    logger.info(f"📝 Generating article for: {topic.get('topic', 'Unknown')}")

    # ── Step 1: Gather source material ────────────────────────────
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

    logger.info(f"  Fetching {len(source_urls)} source URLs...")
    source_texts = fetch_multiple_sources(source_urls, max_sources=5)

    if not source_texts:
        logger.warning("  ⚠️ No source material could be extracted. Using topic summary only.")
        # Create minimal source from story summaries
        source_texts = [{
            "title": topic.get("topic", ""),
            "text": "\n".join(s.get("summary", "") for s in topic.get("stories", [])),
            "source_domain": "aggregated_summaries",
            "url": "",
        }]

    # ── Step 2: Build the prompt ──────────────────────────────────
    prompt = build_article_prompt(
        topic_title=topic.get("topic", "World Cup 2026 Update"),
        source_texts=source_texts,
        matched_keyword=topic.get("matched_keyword", "")
    )

    # ── Step 3: Call Gemini ───────────────────────────────────────
    try:
        logger.info("  🤖 Calling Gemini API...")
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
        )
        raw_output = response.text
        logger.info(f"  ✅ Gemini responded ({len(raw_output)} chars)")

    except Exception as e:
        logger.error(f"  ❌ Gemini API error: {e}")
        return None

    # ── Step 4: Parse structured output ───────────────────────────
    article = _parse_article_output(raw_output)

    if article:
        article["sources_used"] = [s.get("source_domain", "") for s in source_texts]
        article["word_count"] = len(article.get("content", "").split())
        logger.info(f"  ✅ Article generated: '{article['title']}' ({article['word_count']} words)")
    else:
        logger.error("  ❌ Failed to parse Gemini output")

    return article


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
        result["content"] = content_match.group(1).strip() if content_match else ""

        # Extract FAQ
        faq_match = re.search(r'---FAQ_START---(.*?)---FAQ_END---', raw_text, re.DOTALL)
        result["faq_html"] = faq_match.group(1).strip() if faq_match else ""

        # Combine content + FAQ
        if result["faq_html"]:
            result["full_content"] = result["content"] + "\n\n<h2>Frequently Asked Questions</h2>\n" + result["faq_html"]
        else:
            result["full_content"] = result["content"]

        # Validate we got essential fields
        if not result["title"] or not result["content"]:
            logger.warning("Missing essential fields, attempting raw extraction...")
            # Fallback: use the entire output as content
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
