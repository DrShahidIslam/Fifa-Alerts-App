import os
import sys
import json
import random
import sqlite3

# Adjust paths to point to the parent Fifa Alerts App directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(PARENT_DIR, "agent.db")
CACHE_PATH = os.path.join(PARENT_DIR, "internal_links_cache.json")

def get_article_context(url):
    """
    Attempts to retrieve article summary or topic details from the agent.db 
    using the URL slug as a lookup.
    """
    try:
        if not os.path.exists(DB_PATH):
            return None

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Extract keywords from slug for fuzzy search
        slug = url.rstrip('/').split('/')[-1].replace('-', ' ')
        
        # Search in topic_cache which contains JSON summaries
        c.execute("SELECT topic_json FROM topic_cache WHERE topic_json LIKE ? LIMIT 1", (f'%{slug}%',))
        row = c.fetchone()
        conn.close()
        
        if row:
            data = json.loads(row[0])
            # The topic_json usually has a 'topic' and a list of 'stories' with summaries
            topic = data.get('topic', '')
            summary = ""
            if data.get('stories'):
                summary = data['stories'][0].get('summary', '')
            
            return summary or topic
    except Exception as e:
        print(f"   [Linker] DB Lookup error: {e}")
    return None

def get_random_site_article():
    """
    Selects a random content-heavy URL from the internal links cache 
    and prepares a context object for the Pinterest bot.
    """
    print(f"\nPhase 0: Sourcing article from WordPress Library...")
    
    if not os.path.exists(CACHE_PATH):
        print(f"   FAILED: Cache not found at {CACHE_PATH}")
        return None
        
    try:
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            links = json.load(f).get('links', [])
    except Exception as e:
        print(f"   FAILED: Error reading cache: {e}")
        return None
        
    # Filter out utility pages to focus on articles/venues/teams
    exclude_patterns = [
        'contact', 'privacy', 'policy', 'about', 'editorial', 
        'disclosure', 'sitemap', 'tickets', '/venues/', '/team/'
    ]
    # We allow some specific categories if they are content-rich
    content_links = [l for l in links if not any(x in l for x in exclude_patterns) and len(l.split('/')) > 3]
    
    # Fallback to venues or teams if no articles found (to ensure we always have content)
    if not content_links:
        content_links = [l for l in links if any(x in l for x in ['/venues/', '/team/'])]

    if not content_links:
        print("   FAILED: No suitable content links found in cache.")
        return None
        
    url = random.choice(content_links)
    
    # Generate a clean topic from the slug
    raw_slug = url.rstrip('/').split('/')[-1]
    topic = raw_slug.replace('-', ' ').title()
    
    # Try to get extra context from the DB
    summary = get_article_context(url)
    
    bridge_url = f"https://DrShahidIslam.github.io/?article={raw_slug}"
    
    print(f"   Selected: {topic}")
    print(f"   Bridge URL: {bridge_url}")
    print(f"   Original URL: {url}")
    
    return {
        "url": bridge_url,
        "topic": topic,
        "summary": summary or topic,
        "slug": raw_slug
    }

if __name__ == "__main__":
    # Test script
    res = get_random_site_article()
    if res:
        print("\nValidated Context:")
        print(json.dumps(res, indent=2))
