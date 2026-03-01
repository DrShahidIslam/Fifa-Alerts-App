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

─── HTML DESIGN (Kadence Pro + RankMath compatible) ───

Use semantic HTML that Kadence theme and Kadence Blocks will style correctly. Avoid heavy inline styles; let the theme handle appearance. Keep structure clear for RankMath and schema.

**KEY FACTS BOX** — Directly after the intro paragraph. Use a simple div with class for Kadence compatibility:
<div style="border-left: 4px solid #e94560; padding: 1rem 1.25rem; margin: 1.5rem 0; background: rgba(0,0,0,0.05); border-radius: 0 8px 8px 0;">
<h3 style="margin: 0 0 0.75rem 0; font-size: 1.1rem;">Key Facts</h3>
<ul style="margin: 0; padding-left: 1.25rem; line-height: 1.6;">
<li>[Factual insight 1]</li>
<li>[Factual insight 2]</li>
<li>[Factual insight 3]</li>
</ul>
</div>

**HEADINGS** — Use proper H2/H3 hierarchy for SEO. Kadence will style them:
<h2>Section Title</h2>

**PULL QUOTES** — Use blockquote. Kadence wp-block-quote styling will apply:
<blockquote>
"Direct quote or critical statistical insight."
</blockquote>

**HIGHLIGHT BOX** — For breaking or critical info:
<div style="padding: 1rem 1.25rem; margin: 1.5rem 0; border: 1px solid #ffc107; border-radius: 8px; background: rgba(255,193,7,0.08);">
<strong>Important Update:</strong> High-value summary text.
</div>

**FAQ SECTION** — Semantic structure for RankMath FAQ schema. Use details/summary or simple divs:
<div style="margin: 1.5rem 0; border: 1px solid rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden;">
<div style="padding: 1rem 1.25rem; border-bottom: 1px solid rgba(0,0,0,0.1);">
<h3 style="margin: 0 0 0.5rem 0;">Question?</h3>
<p style="margin: 0;">The direct, concise answer first, followed by detail.</p>
</div>
</div>

**CLOSING CTA** — Simple call-to-action. Keep minimal inline styles:
<div style="text-align: center; padding: 1.5rem; margin: 1.5rem 0; border-radius: 8px; background: rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.08);">
<p style="margin: 0 0 0.5rem 0; font-weight: 600;">Explore More on World Cup 2026</p>
<p style="margin: 0; font-size: 0.95rem;">Stay ahead with the latest news and guides for the tournament.</p>
</div>

INTERNAL LINKING RULES:
- Include 2-3 natural internal links.
- Use anchor text from the list below.
- Use clean links: <a href="URL">anchor text</a> (theme will style; avoid heavy inline link styles)
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

<!-- IMPORTANT: Include standard JSON-LD schema for these FAQs immediately after the FAQ HTML -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {{
      "@type": "Question",
      "name": "Insert Question 1",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "Insert detailed answer 1."
      }}
    }}
  ]
}}
</script>
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
