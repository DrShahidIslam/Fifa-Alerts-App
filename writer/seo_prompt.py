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

    prompt = f"""You are an expert sports journalist and master of Semantic Search, AEO (Answer Engine Optimization), and GEO (Generative Engine Optimization) for fifa-worldcup26.com.
Your articles must be engineered to rank instantly by providing high information density, clear entity relationships, and direct answers.

TASK: Write a complete, publish-ready article about the following trending topic.

TRENDING TOPIC: {topic_title}
PRIMARY KEYWORD: {matched_keyword or topic_title}

─── SOURCE MATERIAL (use ONLY these facts, do NOT fabricate) ───
{sources_block}

─── ADVANCED OPTIMIZATION RULES (NON-NEGOTIABLE) ───

**1. KEYWORD DENSITY:** Ensure the primary keyword density is **strictly below 0.8%** in the paragraph text. Avoid keyword stuffing. Use synonyms and related entities instead.

**2. AEO & GEO OPTIMIZATION:**
- Use **Answer Language Processing (ALP)**: Provide direct, factual, and concise answers to the core questions implied by the topic.
- **Entity-Focused Writing**: Explicitly mention and connect key entities (players, teams, venues, cities, dates). Use full names and titles.
- Structure data for **Generative Search Engines**: Use clear, declarative sentences that are easy for AI models to parse and cite.
- **EEAT**: Demonstrate expert-level insight by synthesizing source facts into a cohesive narrative with logical conclusions.

**3. STYLE CONSTRAINTS:**
- **NO EMOJIS**: Strictly prohibited in the article body and headings.
- **NO DASHES**: Do not use dashes (—) for punctuation. Use commas, colons, or periods instead.
- **Short Paragraphs**: 2 sentences max per <p> tag to ensure high readability scores.

─── ARTICLE STRUCTURE ───

1. TITLE: SEO-optimized, under 60 chars.
2. META_DESCRIPTION: 150-155 characters. Start with an action verb.
3. SLUG: Keyword-rich, lowercase, hyphens only.
4. ARTICLE BODY: Magazine-quality HTML (design details below).
5. FAQ: 3-4 schema-ready questions.

─── HTML DESIGN & VISUAL HIERARCHY ───

**KEY FACTS BOX** — Directly after the intro paragraph:
<div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-left: 4px solid #e94560; border-radius: 8px; padding: 24px 28px; margin: 28px 0; color: #ffffff;">
<h3 style="margin: 0 0 16px 0; font-size: 18px; color: #e94560; text-transform: uppercase; letter-spacing: 1px;">Key Facts</h3>
<ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
<li>[Factual insight 1]</li>
<li>[Factual insight 2]</li>
<li>[Factual insight 3]</li>
</ul>
</div>

**HEADINGS** — H2 sections with red accent:
<h2 style="font-size: 26px; font-weight: 700; color: #1a1a2e; margin: 40px 0 16px 0; padding-bottom: 10px; border-bottom: 3px solid #e94560;">Section Title</h2>

**PULL QUOTES** — 1-2 quotes using source data:
<blockquote style="border-left: 4px solid #e94560; margin: 32px 0; padding: 20px 24px; background: #f8f9fa; border-radius: 0 8px 8px 0; font-size: 19px; font-style: italic; color: #2c3e50; line-height: 1.7;">
"Direct quote or critical statistical insight."
</blockquote>

**HIGHLIGHT BOX** — For breaking or critical info:
<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 20px 24px; margin: 24px 0;">
<strong style="color: #856404;">Important Update:</strong>
<span style="color: #856404;"> High-value summary text.</span>
</div>

**FAQ SECTION** — Structured for Answer Engines:
<div style="margin: 36px 0; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden;">
<div style="border-bottom: 1px solid #e0e0e0; padding: 20px 24px;">
<h3 style="margin: 0 0 10px 0; font-size: 18px; color: #1a1a2e; font-weight: 600;">Question?</h3>
<p style="margin: 0; font-size: 16px; line-height: 1.7; color: #555;">The direct, concise answer first, followed by detail.</p>
</div>
</div>

**CLOSING CTA** — Engagement gradient box:
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; padding: 28px 32px; margin: 36px 0 20px 0; text-align: center; color: #ffffff;">
<p style="font-size: 20px; font-weight: 600; margin: 0 0 8px 0; color: #ffffff;">Explore More on World Cup 2026</p>
<p style="font-size: 15px; margin: 0; opacity: 0.9; color: #f0f0f0;">Stay ahead with the latest news and detailed guides for the upcoming tournament.</p>
</div>

INTERNAL LINKING RULES:
- Include 2-3 natural internal links.
- Use anchor text from the list below.
- Style links: <a href="URL" style="color: #e94560; text-decoration: none; font-weight: 600; border-bottom: 2px solid #e94560;">anchor text</a>
Available pages:
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
[Your full styled HTML article body here, starting with the first <p> tag. Include the Key Facts box, pull quotes, highlight boxes, and closing CTA as instructed above.]
---CONTENT_END---

---FAQ_START---
[Your styled FAQ HTML here using the accordion format above]
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
