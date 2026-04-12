import http.server
import socketserver
import os
import json
import urllib.parse
import sys
import tempfile
from dotenv import load_dotenv

# Add current directory to path so we can import main.py
sys.path.append(os.getcwd())
import main as bot
import wordpress_linker

PORT = 8080
DIRECTORY = "demo_ui"

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_POST(self):
        if self.path.startswith('/api/publish'):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                print("\n[SERVER] Received publish request...")
                
                # Fetch board info based on category
                category = payload.get("board_category", "match_previews")
                board_info = bot.BOARD_MAP.get(category, bot.BOARD_MAP["match_previews"])
                
                # Use the specific URL from the payload (important for Site Mode)
                destination_link = payload.get("url", board_info["link"])
                
                with tempfile.TemporaryDirectory() as tmp_dir:
                    raw_img, _ = bot.generate_image_with_siliconflow(payload["image_prompt"], tmp_dir)
                    final_img = bot.design_pin_image(raw_img, payload["topic"], tmp_dir)
                    
                    result = bot.publish_to_pinterest(
                        image_path=final_img,
                        title=payload["topic"],
                        description=payload["desc"],
                        board_id=board_info["board_id"],
                        link=destination_link
                    )
                
                if result:
                    response = {"status": "success", "pin_id": result.get("id")}
                else:
                    response = {"status": "error", "message": "API Failure"}
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                print(f"[SERVER] Error: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
            return

    def do_GET(self):
        # ENDPOINT: Site-Linker Generation (Pulls real WordPress content)
        if self.path.startswith('/api/generate'):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                print("\n[SERVER] Generating Pin for a live Site Article...")
                
                # 1. Fetch a real article context
                article_context = wordpress_linker.get_random_site_article()
                
                # 2. Generate content with Gemini
                content = bot.generate_content_with_gemini(article_context)
                
                # 3. SiliconFlow image URL for preview
                with tempfile.TemporaryDirectory() as tmp_dir:
                    _, real_image_url = bot.generate_image_with_siliconflow(content["image_prompt"], tmp_dir)
                
                response = {
                    "status": "success",
                    "topic": content["title"],
                    "desc": content["description"],
                    "image_prompt": content["image_prompt"],
                    "category": content["board_category"],
                    "real_image_url": real_image_url,
                    "url": article_context["url"] if article_context else "https://fifa-worldcup26.com"
                }
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                print(f"[SERVER] Error: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
            return

        return super().do_GET()

def run_server():
    # Kill any existing process on port 8080 (Windows)
    os.system(f"stop-process -Id (Get-NetTCPConnection -LocalPort {PORT}).OwningProcess -Force 2>$null")
    
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"\n🚀 FIFA Pinterest Dashboard (SITE LINKER) started at http://localhost:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
