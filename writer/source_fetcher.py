"""
Source Fetcher — Downloads and extracts clean text from news article URLs.
Used to gather factual information before generating AI articles.
"""
import logging
import re
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Request headers to avoid blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def fetch_article_text(url, max_chars=3000):
    """
    Fetch and extract clean text from a news article URL.
    Uses trafilatura as primary extractor, falls back to basic HTML parsing.

    Returns:
        dict with keys: title, text, source_domain, url
    """
    if not url:
        return None

    domain = urlparse(url).netloc.replace("www.", "")

    # Try trafilatura first (best quality extraction)
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            if text and len(text) > 200:
                # Also try to get metadata
                metadata = trafilatura.extract_metadata(downloaded)
                title = metadata.title if metadata and metadata.title else ""

                return {
                    "title": title,
                    "text": text[:max_chars],
                    "source_domain": domain,
                    "url": url,
                    "method": "trafilatura",
                }
    except ImportError:
        logger.debug("trafilatura not installed, trying fallback")
    except Exception as e:
        logger.warning(f"trafilatura failed for {url}: {e}")

    # Fallback: basic requests + regex extraction
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        html = response.text

        # Extract title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""

        # Remove script and style tags
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)

        # Extract text from <p> tags (most article content)
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', clean, flags=re.DOTALL | re.IGNORECASE)
        text_parts = []
        for p in paragraphs:
            # Strip HTML tags from paragraph content
            text = re.sub(r'<[^>]+>', '', p).strip()
            if len(text) > 40:  # Skip short nav/footer elements
                text_parts.append(text)

        full_text = "\n\n".join(text_parts)

        if full_text and len(full_text) > 200:
            return {
                "title": title,
                "text": full_text[:max_chars],
                "source_domain": domain,
                "url": url,
                "method": "fallback_regex",
            }

    except Exception as e:
        logger.warning(f"Fallback extraction failed for {url}: {e}")

    return None


def fetch_multiple_sources(urls, max_sources=5):
    """
    Fetch text from multiple source URLs.
    Returns a list of successfully extracted source dicts.
    """
    sources = []

    for url in urls[:max_sources]:
        try:
            result = fetch_article_text(url)
            if result:
                sources.append(result)
                logger.info(f"  ✅ Extracted {len(result['text'])} chars from {result['source_domain']}")
            else:
                logger.warning(f"  ⚠️ Could not extract from: {url[:80]}")
        except Exception as e:
            logger.error(f"  ❌ Error fetching {url[:80]}: {e}")

    return sources


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    test_urls = [
        "https://www.bbc.com/sport/football",
        "https://www.espn.com/soccer/",
    ]

    for url in test_urls:
        print(f"\nFetching: {url}")
        result = fetch_article_text(url)
        if result:
            print(f"  Title: {result['title'][:80]}")
            print(f"  Text: {result['text'][:200]}...")
            print(f"  Method: {result['method']}")
        else:
            print("  ❌ Failed to extract")
