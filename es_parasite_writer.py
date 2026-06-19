import os
import re
import sys
import json
import time
import shutil
import subprocess
import argparse
import logging
from urllib.parse import quote

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add current directory to path to import config
sys.path.insert(0, os.path.dirname(__file__))
import config
from writer.es_seo_prompt import build_es_article_prompt
from google import genai

# Setup Gemini
if not config.GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY is not set in config.")
    sys.exit(1)

gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)

# Target Repositories
REPOSITORIES = [
    {
        "url": "github.com/DrShahidIslam/global-soccer-news.git",
        "base_url": "https://drshahidislam.github.io/global-soccer-news",
        "name": "global-soccer-news"
    },
    {
        "url": "github.com/DrShahidIslam/Fifa-Cloudlfare.git",
        "base_url": "https://fifa-cloudlfare.pages.dev",
        "name": "Fifa-Cloudlfare"
    },
    {
        "url": "github.com/DrShahidIslam/fifaworldcup-vercel.git",
        "base_url": "https://worldcupnews.vercel.app",
        "name": "fifaworldcup-vercel"
    }
]

# ... [Keep MATCHES list as is] ...

def format_slug(team_name):
    """Convert team name to URL slug format."""
    return re.sub(r'[^a-z0-9]+', '-', team_name.lower().strip()).strip('-')

def get_match_url(team1, team2):
    """Generate the main site match URL based on the user's pattern."""
    slug1 = format_slug(team1)
    slug2 = format_slug(team2)
    return f"https://fifa-worldcup26.com/match/{slug1}-vs-{slug2}/"

def fetch_context_for_match(team1, team2):
    """Fetch recent news context using Gemini search or a generic prompt if search fails."""
    logger.info(f"Fetching context for {team1} vs {team2}...")
    try:
        search_prompt = f"Dame un breve resumen de las últimas noticias, estado de forma y jugadores clave para las selecciones de fútbol de {team1} y {team2} de cara a sus próximos partidos internacionales o Copa Mundial."
        res = gemini_client.models.generate_content(model=config.GEMINI_MODEL, contents=search_prompt)
        return [{"title": f"Contexto {team1} vs {team2}", "text": res.text, "source_domain": "gemini"}]
    except Exception as e:
        logger.error(f"Failed to fetch context: {e}")
        return []

def generate_article(team1, team2, match_url, context):
    match_title = f"{team1} vs {team2}"
    prompt = build_es_article_prompt(match_title, team1, team2, match_url, context)
    
    logger.info("Generating Spanish article via Gemini...")
    response = gemini_client.models.generate_content(model=config.GEMINI_MODEL, contents=prompt)
    
    if not response.text:
        raise ValueError("Gemini returned empty response.")
        
    text = response.text
    
    # Parse output
    title_match = re.search(r"TITLE:\s*(.+)", text, re.IGNORECASE)
    seo_title_match = re.search(r"SEO_TITLE:\s*(.+)", text, re.IGNORECASE)
    meta_desc_match = re.search(r"META_DESCRIPTION:\s*(.+)", text, re.IGNORECASE)
    slug_match = re.search(r"SLUG:\s*(.+)", text, re.IGNORECASE)
    
    content_match = re.search(r"---CONTENT_START---\s*(.*?)\s*---CONTENT_END---", text, re.DOTALL | re.IGNORECASE)
    
    if not (title_match and seo_title_match and meta_desc_match and slug_match and content_match):
        logger.error("Failed to parse Gemini output structure.")
        logger.debug(f"Raw Output: {text}")
        raise ValueError("Missing required fields in Gemini output.")
        
    return {
        "title": title_match.group(1).strip(),
        "seo_title": seo_title_match.group(1).strip(),
        "meta_description": meta_desc_match.group(1).strip(),
        "slug": slug_match.group(1).strip(),
        "content": content_match.group(1).strip()
    }

def compile_html(article_data, team1, team2):
    template_path = os.path.join(os.path.dirname(__file__), "writer", "es_template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    html = html.replace("{{ TITLE }}", article_data["title"])
    html = html.replace("{{ SEO_TITLE }}", article_data["seo_title"])
    html = html.replace("{{ META_DESCRIPTION }}", article_data["meta_description"])
    html = html.replace("{{ CONTENT }}", article_data["content"])
    html = html.replace("{{ TEAM1 }}", team1)
    html = html.replace("{{ TEAM2 }}", team2)
    
    return html

def run_cmd(cmd, cwd=None):
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Command failed: {result.stderr}")
        raise Exception(f"Command failed: {' '.join(cmd)}")
    return result.stdout

def build_sitemap_and_index(repo_path, base_url):
    """Generates sitemap.xml and index.html based on all HTML files in es/partidos/"""
    es_dir = os.path.join(repo_path, "es", "partidos")
    if not os.path.exists(es_dir):
        return
        
    files = [f for f in os.listdir(es_dir) if f.endswith(".html")]
    if not files:
        return
        
    urls = []
    links_html = ""
    
    for file in files:
        url_path = f"{base_url}/es/partidos/{file}"
        urls.append(url_path)
        
        # Read the title from the file
        file_path = os.path.join(es_dir, file)
        title = file.replace("-", " ").replace(".html", "").title()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                title_match = re.search(r"<title>(.*?)</title>", content)
                if title_match:
                    title = title_match.group(1)
        except:
            pass
            
        links_html += f'            <a href="{url_path}" class="match-card"><h3>{title}</h3><p>Ver Pronóstico y Transmisión</p></a>\n'

    # Build sitemap.xml
    sitemap_content = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        sitemap_content += f'  <url>\n    <loc>{url}</loc>\n    <changefreq>daily</changefreq>\n    <priority>0.8</priority>\n  </url>\n'
    sitemap_content += '</urlset>'
    
    with open(os.path.join(repo_path, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap_content)
        
    # Build index.html
    index_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>World Cup 2026 - Transmisiones y Pronósticos en Vivo</title>
    <meta name="description" content="Sigue todos los partidos del Mundial 2026. Encuentra transmisiones en vivo, estadísticas y los mejores pronósticos.">
    <style>
        body {{ font-family: system-ui, sans-serif; background: #0a0e17; color: white; margin: 0; padding: 2rem; }}
        h1 {{ text-align: center; color: #f0f4f8; margin-bottom: 3rem; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.5rem; max-width: 1200px; margin: 0 auto; }}
        .match-card {{ background: rgba(20, 27, 45, 0.8); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 1.5rem; text-decoration: none; color: white; display: block; transition: transform 0.2s; }}
        .match-card:hover {{ transform: translateY(-5px); border-color: #e11d48; }}
        .match-card h3 {{ margin: 0 0 0.5rem 0; color: #cbd5e1; font-size: 1.1rem; }}
        .match-card p {{ margin: 0; color: #e11d48; font-weight: bold; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <h1>Cobertura de Partidos: Mundial 2026</h1>
    <div class="grid">
{links_html}
    </div>
</body>
</html>"""
    
    with open(os.path.join(repo_path, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

def deploy_to_repos(html_content, slug, is_dry_run=False):
    pat = config.GITHUB_PAT
    if not pat and not is_dry_run:
        raise ValueError("GITHUB_PAT is not set in environment or config. Cannot deploy.")
        
    tmp_dir = os.path.join(os.path.dirname(__file__), "tmp_repos")
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
        
    for repo_config in REPOSITORIES:
        repo_url = repo_config["url"]
        repo_name = repo_config["name"]
        base_url = repo_config["base_url"].rstrip("/")
        
        repo_path = os.path.join(tmp_dir, repo_name)
        
        # Clone or Pull
        if not os.path.exists(repo_path):
            clone_url = f"https://x-access-token:{pat}@{repo_url}" if pat else f"https://{repo_url}"
            logger.info(f"Cloning {repo_name}...")
            run_cmd(["git", "clone", clone_url, repo_path])
        else:
            logger.info(f"Pulling latest for {repo_name}...")
            run_cmd(["git", "pull"], cwd=repo_path)
            
        # Ensure 'es/partidos' directory exists
        es_dir = os.path.join(repo_path, "es", "partidos")
        if not os.path.exists(es_dir):
            os.makedirs(es_dir)
            
        file_path = os.path.join(es_dir, f"{slug}.html")
        
        # Write HTML
        logger.info(f"Writing to {file_path}...")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        # Build Sitemap and Index
        logger.info(f"Building sitemap and index for {repo_name}...")
        build_sitemap_and_index(repo_path, base_url)
            
        if is_dry_run:
            logger.info(f"[DRY RUN] Skipping git commit/push for {repo_name}.")
            continue
            
        # Commit and Push
        logger.info(f"Committing and pushing to {repo_name}...")
        run_cmd(["git", "add", "."], cwd=repo_path)
        
        status = run_cmd(["git", "status", "--porcelain"], cwd=repo_path)
        if not status.strip():
            logger.info(f"No changes to commit for {repo_name}.")
            continue
            
        run_cmd(["git", "config", "user.name", "Fifa Agent"], cwd=repo_path)
        run_cmd(["git", "config", "user.email", "agent@fifa-worldcup26.com"], cwd=repo_path)
        run_cmd(["git", "commit", "-m", f"Auto-publish Spanish preview: {slug} & update sitemap"], cwd=repo_path)
        run_cmd(["git", "push"], cwd=repo_path)
        logger.info(f"Successfully pushed to {repo_name}.")

def get_next_match():
    """Read a local tracking file to find the next match to process."""
    tracking_file = os.path.join(os.path.dirname(__file__), "es_processed_matches.json")
    processed = []
    if os.path.exists(tracking_file):
        with open(tracking_file, "r") as f:
            processed = json.load(f)
            
    for t1, t2 in MATCHES:
        match_id = f"{t1}-vs-{t2}".lower()
        if match_id not in processed:
            return t1, t2, processed, tracking_file
            
    return None, None, processed, tracking_file

def main():
    parser = argparse.ArgumentParser(description="Automate Spanish Parasite SEO Articles")
    parser.add_argument("--dry-run", action="store_true", help="Generate content but do not push to GitHub")
    parser.add_argument("--team1", type=str, help="Force specific Team 1")
    parser.add_argument("--team2", type=str, help="Force specific Team 2")
    args = parser.parse_args()

    team1 = args.team1
    team2 = args.team2
    processed = []
    tracking_file = ""

    if not team1 or not team2:
        team1, team2, processed, tracking_file = get_next_match()
        if not team1:
            logger.info("All configured matches have been processed!")
            return

    match_url = get_match_url(team1, team2)
    logger.info(f"Target Match: {team1} vs {team2}")
    logger.info(f"Backlink URL: {match_url}")

    # Fetch context
    context = fetch_context_for_match(team1, team2)

    # Generate content
    article_data = generate_article(team1, team2, match_url, context)
    logger.info(f"Generated Article: {article_data['title']}")

    # Compile HTML
    html_content = compile_html(article_data, team1, team2)

    # Deploy
    deploy_to_repos(html_content, article_data['slug'], is_dry_run=args.dry_run)

    # Mark as processed if not dry run
    if not args.dry_run and tracking_file:
        match_id = f"{team1}-vs-{team2}".lower()
        processed.append(match_id)
        with open(tracking_file, "w") as f:
            json.dump(processed, f)
        logger.info(f"Marked {match_id} as processed.")

if __name__ == "__main__":
    main()
