import os
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("PINTEREST_APP_ID")
APP_SECRET = os.getenv("PINTEREST_APP_SECRET")
REDIRECT_URI = "http://localhost:8080"

def get_auth_url():
    scopes = "boards:read,boards:write,pins:read,pins:write,user_accounts:read"
    url = (
        f"https://www.pinterest.com/oauth/?"
        f"client_id={APP_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={scopes}"
    )
    print("\n--- STEP 1: AUTHORIZATION ---")
    print("1. Ensure you have added 'http://localhost:8080' to Redirect URIs in the Pinterest Portal.")
    print("2. Visit this URL in your browser:\n")
    print(url)
    print("\n3. Click 'Authorize'.")
    print("4. You will be redirected to a page that fails to load.")
    print("5. Copy the 'code' parameter from the URL bar (e.g., ?code=abc123...)")

def exchange_code(code):
    print("\n--- STEP 2: EXCHANGING CODE FOR TOKENS ---")
    auth_header = base64.b64encode(f"{APP_ID}:{APP_SECRET}".encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    
    response = requests.post("https://api.pinterest.com/v5/oauth/token", headers=headers, data=data)
    
    if response.status_code == 200:
        tokens = response.json()
        print("\nSUCCESS!")
        print(f"Access Token: {tokens.get('access_token')[:10]}...")
        print(f"Refresh Token: {tokens.get('refresh_token')[:10]}...")
        
        # Update .env
        with open(".env", "r") as f:
            lines = f.readlines()
        
        with open(".env", "w") as f:
            for line in lines:
                if line.startswith("PINTEREST_ACCESS_TOKEN="):
                    f.write(f"PINTEREST_ACCESS_TOKEN={tokens.get('access_token')}\n")
                elif line.startswith("PINTEREST_REFRESH_TOKEN="):
                    f.write(f"PINTEREST_REFRESH_TOKEN={tokens.get('refresh_token')}\n")
                else:
                    f.write(line)
        
        print("\n.env file has been updated with your new tokens!")
    else:
        print(f"\nFAILED: {response.status_code}")
        print(response.text)

def list_boards():
    load_dotenv() # reload to get tokens
    access_token = os.getenv("PINTEREST_ACCESS_TOKEN")
    if not access_token:
        print("No access token found. Run the code exchange first.")
        return
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.get("https://api.pinterest.com/v5/boards", headers=headers)
    if response.status_code == 200:
        boards = response.json().get("items", [])
        print("\n--- YOUR PINTEREST BOARDS ---")
        if not boards:
            print("No boards found.")
        for b in boards:
            print(f"- {b['name']} (ID: {b['id']})")
    else:
        print(f"Failed to list boards: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list-boards":
            list_boards()
        else:
            exchange_code(sys.argv[1])
    else:
        get_auth_url()
