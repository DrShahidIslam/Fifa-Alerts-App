"""
SEO Prompt Template — Master prompt used for Gemini article generation.
Enforces SEO best practices, your site's editorial style, and internal linking.
"""

# Internal pages on fifa-worldcup26.com for natural linking
INTERNAL_LINKS = {
    "tickets": {"url": "https://fifa-worldcup26.com/tickets/", "anchor": "World Cup 2026 tickets"},
    "venues": {"url": "https://fifa-worldcup26.com/venues/", "anchor": "host stadiums and venues"},
    "travel": {"url": "https://fifa-worldcup26.com/worldcup-travel-flights-hotels-visa/", "anchor": "travel and hotel planning guide"},
    "broadcasting": {"url": "https://fifa-worldcup26.com/how-to-watch-worldcup/", "anchor": "how to watch World Cup 2026"},
    "qualifiers": {"url": "https://fifa-worldcup26.com/qualifiers/", "anchor": "World Cup 2026 qualifiers"},
    "matches": {"url": "https://fifa-worldcup26.com/matches/", "anchor": "full match schedule"},
    "standings": {"url": "https://fifa-worldcup26.com/standings/", "anchor": "current group standings"},
    "teams": {"url": "https://fifa-worldcup26.com/teams/", "anchor": "all 48 qualified teams"},
    "news": {"url": "https://fifa-worldcup26.com/news/", "anchor": "latest World Cup news"},
    "beginner_guide": {"url": "https://fifa-worldcup26.com/world-cup-2026-beginner-guide/", "anchor": "beginner's guide to World Cup 2026"},
    "messi": {"url": "https://fifa-worldcup26.com/is-messi-playing-world-cup-2026/", "anchor": "Messi's World Cup 2026 plans"},
    "jerseys": {"url": "https://fifa-worldcup26.com/world-cup-2026-jerseys-kits/", "anchor": "official World Cup 2026 jerseys"},
    "visa": {"url": "https://fifa-worldcup26.com/us-visa-guide-world-cup-2026/", "anchor": "US visa guide for World Cup fans"},
    "cheapest_cities": {"url": "https://fifa-worldcup26.com/cheapest-world-cup-2026-host-cities/", "anchor": "cheapest host cities to visit"},
    "bracket": {"url": "https://fifa-worldcup26.com/fifa-world-cup-2026-bracket/", "anchor": "World Cup 2026 bracket and wall chart"},
    "opening_match": {"url": "https://fifa-worldcup26.com/world-cup-2026-opening-match/", "anchor": "World Cup 2026 opening match details"},
}


def build_article_prompt(topic_title, source_texts, matched_keyword=""):
    """
    Build the master SEO prompt for Gemini article generation.

    Args:
        topic_title: The trending topic headline
        source_texts: List of source article texts (from source_fetcher)
        matched_keyword: The primary keyword that triggered detection

    Returns:
        str: The complete prompt for Gemini
    """
    # Build source context block
    sources_block = ""
    for i, src in enumerate(source_texts[:5], 1):
        sources_block += f"""
--- SOURCE {i} ({src.get('source_domain', 'Unknown')}) ---
{src.get('text', '')[:2000]}
"""

    # Build internal links suggestion
    links_suggestion = "\n".join([
        f"  - [{info['anchor']}]({info['url']})"
        for key, info in INTERNAL_LINKS.items()
    ])

    prompt = f"""You are an expert sports journalist and SEO writer for fifa-worldcup26.com, an unofficial FIFA World Cup 2026 guide.

TASK: Write a complete, publish-ready article about the following trending topic.

TRENDING TOPIC: {topic_title}
PRIMARY KEYWORD: {matched_keyword or topic_title}

─── SOURCE MATERIAL (use ONLY these facts, do NOT fabricate) ───
{sources_block}

─── ARTICLE REQUIREMENTS ───

STRUCTURE (use this exact format):
1. TITLE: Create an SEO-optimized title using the primary keyword. Under 60 characters. Include a hook or number if natural.
2. META_DESCRIPTION: A compelling 150-155 character description that creates urgency. Start with an action word.
3. SLUG: A keyword-rich URL slug (lowercase, hyphens, no stop words). Example: world-cup-2026-italy-qualifies
4. ARTICLE BODY in HTML format:
   - Opening paragraph (2-3 sentences, includes primary keyword naturally, hooks the reader)
   - H2 sections (3-5 sections covering different angles of the story)
   - Each H2 has 2-3 paragraphs of body text
   - Include specific facts: dates, scores, player names, stadium names from the sources
   - One H2 should tie into fan planning (tickets, travel, or viewing) — this is where affiliate/commercial value lives
   - Closing paragraph with forward-looking statement
5. FAQ: Write 3-4 FAQ questions and answers in this exact HTML format:
   <div class="schema-faq">
   <div class="faq-item">
   <h3>Question here?</h3>
   <p>Answer here.</p>
   </div>
   </div>
6. TAGS: Suggest 5-8 WordPress tags (comma-separated)
7. CATEGORY: Always "News"

INTERNAL LINKING RULES:
- Include 2-3 natural internal links to existing pages on our site
- Use contextual anchor text, not "click here"
- Available pages for linking:
{links_suggestion}

EDITORIAL GUIDELINES:
- Tone: Authoritative but conversational. Write like a knowledgeable friend, not a textbook.
- Word count: 800-1500 words
- NEVER fabricate facts, quotes, scores, or dates. Only use information from the provided sources.
- If sources conflict, mention both perspectives.
- Use short paragraphs (2-3 sentences max per paragraph).
- Include transition words for SEO readability.
- Reference "the tournament" or "the 2026 World Cup" naturally — don't keyword-stuff.
- This is an UNOFFICIAL fan guide. Never claim to represent FIFA.

OUTPUT FORMAT:
Return your response in this exact structured format:

TITLE: [your title]
META_DESCRIPTION: [your meta description]
SLUG: [your-slug]
TAGS: [tag1, tag2, tag3, ...]
CATEGORY: News

---CONTENT_START---
[Your full HTML article body here, starting with the first <p> tag]
---CONTENT_END---

---FAQ_START---
[Your FAQ HTML here]
---FAQ_END---
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
    prompt = f"""Create a photorealistic editorial sports photograph for a World Cup 2026 article.

Topic: {topic_title}

Style guidelines:
- Photorealistic sports editorial photography
- Dynamic and energetic composition
- World Cup / international football atmosphere
- Stadium or football field setting where appropriate
- Vibrant and high-contrast colors
- No text overlays, watermarks, or logos
- Professional sports photography look (as if from Getty Images or AFP)
- 16:9 aspect ratio, landscape orientation
- The image should evoke excitement and anticipation for the World Cup

Do NOT include: real faces of actual players, FIFA logos, real team crests, or trademarked designs."""

    return prompt
