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

**4. SCHEMA TAGS (CRITICAL):** The JSON-LD FAQ schema MUST be strictly wrapped in `<script type="application/ld+json">` and `</script>` tags. Without these tags, the schema will display visibly as text, which ruins the page layout. Do not forget the script tags!

─── ARTICLE STRUCTURE ───

1. TITLE: SEO-optimized, under 60 chars.
2. META_DESCRIPTION: 150-155 characters. Start with an action verb.
3. SLUG: Keyword-rich, lowercase, hyphens only.
4. ARTICLE BODY: Magazine-quality HTML (design details below).
5. FAQ: 3-4 schema-ready questions.

**1. NO WORDPRESS BLOCK COMMENTS**: Do NOT output any `<!-- wp:... -->` comments. Produce strictly raw HTML.

**2. FOLLOW THIS EXACT HTML TEMPLATE** (Copy the structure and inline styles exactly as shown here):

<div class="wp-block-group" style="padding:1.5rem 2rem 2.5rem 2rem">

<h2 class="wp-block-heading">[Your Main Heading]</h2>
<p>[Your introductory text goes here...]</p>
<p>[More text...]</p>

<div style="border-left: 4px solid #e94560;padding: 1rem 1.25rem;margin: 1.5rem 0;border-radius: 0 8px 8px 0;background-color:#f9f9f9;color:#000000;">
<h3 style="margin: 0 0 0.75rem 0;font-size: 1.1rem;color:#000000;">Key Facts</h3>
<ul style="margin: 0;padding-left: 1.25rem;line-height: 1.6;color:#000000;">
<li>[Fact 1]</li>
<li>[Fact 2]</li>
<li>[Fact 3]</li>
</ul>
</div>

<h2>[Next Section Heading]</h2>
<p>[Section text... example internal link: <a href="https://fifa-worldcup26.com/news/">latest World Cup news</a>...]</p>

<div style="padding: 1rem 1.25rem;margin: 1.5rem 0;border: 1px solid #ffc107;border-radius: 8px;background-color:#fffdf5;color:#000000;">
<strong>Important Update:</strong> [A crucial highlight or takeaway from the article.]
</div>

<h2>[Another Section Heading]</h2>
<p>[Content...]</p>

<div style="display:block !important; padding:2rem !important; margin:2rem 0 !important; border-radius:12px !important; background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460) !important; text-align:center !important; box-shadow:0 10px 20px rgba(0,0,0,0.15) !important; border-left:5px solid #e94560 !important;">
<p style="font-size:1.5rem !important; font-weight:800 !important; margin:0 0 0.5rem 0 !important; text-transform:uppercase !important; letter-spacing:1px !important; color:#ffffff !important;">Explore More on World Cup 2026</p>
<p style="font-size:1.1rem !important; color:#e2e8f0 !important; font-weight:400 !important; margin:0 0 1rem 0 !important;">Stay ahead with the latest news, guides, and ticket updates for the tournament</p>
<a href="https://fifa-worldcup26.com/" style="display:inline-block !important; padding:0.75rem 2rem !important; background:#e94560 !important; color:#ffffff !important; text-decoration:none !important; border-radius:8px !important; font-weight:700 !important; font-size:1rem !important; letter-spacing:0.5px !important;">Visit fifa-worldcup26.com &rarr;</a>
</div>

<h2>Frequently Asked Questions</h2>
<div style="margin: 1.5rem 0;border-radius: 8px;border:1px solid #ddd;overflow: hidden;color:#000000;">
<div style="padding: 1rem 1.25rem;background-color:#fafafa;">
<h3 style="margin: 0 0 0.5rem 0;font-size: 1.1rem;color:#000000;">[Question 1?]</h3>
<p style="margin: 0;color:#000000;">[Answer to Question 1.]</p>
</div>
</div>
<div style="margin: 1.5rem 0;border-radius: 8px;border:1px solid #ddd;overflow: hidden;color:#000000;">
<div style="padding: 1rem 1.25rem;background-color:#fafafa;">
<h3 style="margin: 0 0 0.5rem 0;font-size: 1.1rem;color:#000000;">[Question 2?]</h3>
<p style="margin: 0;color:#000000;">[Answer to Question 2.]</p>
</div>
</div>
<div style="margin: 1.5rem 0;border-radius: 8px;border:1px solid #ddd;overflow: hidden;color:#000000;">
<div style="padding: 1rem 1.25rem;background-color:#fafafa;">
<h3 style="margin: 0 0 0.5rem 0;font-size: 1.1rem;color:#000000;">[Question 3?]</h3>
<p style="margin: 0;color:#000000;">[Answer to Question 3.]</p>
</div>
</div>

<!-- CRITICAL: DO NOT FORGET THESE SCRIPT TAGS AROUND THE JSON! -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {{
      "@type": "Question",
      "name": "[Question 1?]",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "[Answer to Question 1.]"
      }}
    }},
    {{
      "@type": "Question",
      "name": "[Question 2?]",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "[Answer to Question 2.]"
      }}
    }},
    {{
      "@type": "Question",
      "name": "[Question 3?]",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "[Answer to Question 3.]"
      }}
    }}
  ]
}}
</script>
</div>

INTERNAL LINKING RULES (STRICT):
- The internal links MUST BE GENUINE. I mean ONLY use our original links from the list below. Do NOT invent, guess, or hallucinate any internal URL.
- Include 2-3 genuine internal links, naturally placed where they fit the topic.
- Use the exact URL and suggested anchor text from the list. Format: <a href="EXACT_URL">anchor text</a>

Allowed genuine internal links (copy URL and anchor exactly):
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
[Generate the entire HTML structure exactly as specified in the HTML template above, placing everything inside the main wp-block-group div. CRITICAL: the FAQ JSON-LD schema at the end MUST be inside <script type="application/ld+json">...</script> tags, or it will break the site! Output the RAW HTML directly without using ```html markdown tags!]
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
