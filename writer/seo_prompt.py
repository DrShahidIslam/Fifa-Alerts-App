"""
SEO Prompt Template — Master prompt used for Gemini article generation.
Enforces SEO best practices, your site's editorial style, and internal linking.
All URLs below are real pages on fifa-worldcup26.com; do not add or invent others.
"""

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

─── OUTPUT FORMAT: GUTENBERG BLOCKS (REQUIRED) ───

**1. WRAP THE ENTIRE ARTICLE BODY in a Group block with padding** (top 1.5rem, sides 2rem, bottom 2.5rem). Start the ARTICLE BODY with:
<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"1.5rem","right":"2rem","bottom":"2.5rem","left":"2rem"}}}}}}}} -->
<div class="wp-block-group" style="padding:1.5rem 2rem 2.5rem 2rem">
Then place all your blocks inside, and close with:
</div>
<!-- /wp:group -->

**2. Wrap every element** in block comments as follows:
- **Paragraphs:** <!-- wp:paragraph -->
<p>Your text.</p>
<!-- /wp:paragraph -->
- **Headings:** <!-- wp:heading -->
<h2>Section Title</h2>
<!-- /wp:heading --> (or h3)
- **Blockquotes:** <!-- wp:quote -->
<blockquote><p>Quote text.</p></blockquote>
<!-- /wp:quote -->
- **Lists:** <!-- wp:list -->
<ul><li>Item</li></ul>
<!-- /wp:list -->
- **Custom HTML (Key Facts box, FAQ, CTA divs):** <!-- wp:html -->
<div>...</div>
<!-- /wp:html -->

Do NOT output raw HTML without block wrappers. Every paragraph, heading, blockquote, and standalone div must have its opening <!-- wp:... --> and closing <!-- /wp:... -->. This ensures the post uses blocks in the editor and works with Kadence Blocks.

─── HTML DESIGN (Kadence Pro + RankMath compatible) ───

Use semantic HTML inside the blocks. Avoid heavy inline styles; let the theme handle appearance. Keep structure clear for RankMath and schema.

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

INTERNAL LINKING RULES (STRICT):
- You MUST use ONLY the URLs in the list below. Do NOT invent, guess, or hallucinate any internal URL.
- Include 2-3 internal links, naturally placed where they fit the topic (e.g. link to tickets when discussing attendance, to a team page when that team is central, to a related blog post when relevant).
- Use the exact URL and suggested anchor text from the list. Format: <a href="EXACT_URL">anchor text</a>
- If no link from the list fits naturally, use one or two that are closest (e.g. news hub or beginner guide). Never add a link that is not in this list.

Allowed internal links (copy URL and anchor exactly):
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
[ONLY the main article body: intro, Key Facts box, body sections, closing CTA. Use GUTENBERG BLOCK MARKUP. Do NOT put "Frequently Asked Questions", FAQ Q&A, or any JSON-LD schema here. Those go ONLY in FAQ_START below. Order: wp:group with padding, then paragraphs, Key Facts (wp:html), headings, quotes, highlight boxes, closing CTA (wp:html), then close the group.]
---CONTENT_END---

---FAQ_START---
[ONLY the FAQ Q&A blocks and the JSON-LD schema. Do NOT repeat the article body. Put each FAQ answer in <!-- wp:html -->. Then put the schema inside a single <!-- wp:html --> block with <script type="application/ld+json">...</script> so it is hidden from readers:]

<!-- wp:html -->
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
<!-- /wp:html -->
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
