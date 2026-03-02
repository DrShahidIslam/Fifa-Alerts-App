# Troubleshooting WordPress API 403 Forbidden Errors (Wordfence & Cloudflare)

The agent runs from **GitHub Actions**, so requests to your site come from **GitHub’s IPs**. Firewalls (Wordfence, Cloudflare, host) often block those IPs or block “bot” requests, so publish can work one day and fail the next (e.g. after IP range changes). Two approaches:

---

## Option A: Foolproof — Publish via webhook (recommended)

**No REST API calls from the internet** = no firewall to block. The agent sends the article to a script on your server; the script creates the post locally.

1. **Copy the webhook script**  
   From this repo: `deploy/fifa-agent-webhook.php`. Copy it to your **WordPress site root** (same folder as `wp-config.php`).  
   Rename it to something unguessable, e.g. `fifa-publish-abc12xyz.php`.

2. **Define the secret in WordPress**  
   In `wp-config.php` add:
   ```php
   define('FIFA_AGENT_WEBHOOK_SECRET', 'your-long-random-secret-here');
   ```
   Use a long random string (e.g. 32+ characters).

3. **Set env vars in the agent** (GitHub Secrets or `.env`):
   - `WP_PUBLISH_WEBHOOK_URL` = `https://yoursite.com/fifa-publish-abc12xyz.php` (the URL to your renamed file)
   - `WP_PUBLISH_SECRET` = the **same** value as `FIFA_AGENT_WEBHOOK_SECRET`

4. **Optional: Restrict access**  
   In Wordfence (or .htaccess), you can allow only requests that have the header `X-FIFA-Agent-Token` with your secret, or allowlist only GitHub IPs for this path. The script itself rejects any request without the correct token.

After this, the agent uses the webhook instead of the REST API. Publishing no longer depends on firewall allowlists and is reliable from GitHub Actions.

---

## Option B: Allow the agent through the firewall (REST API)

If you prefer not to use the webhook, you can allow REST API requests from the agent. The agent now sends browser-like headers and retries on 403, but if your firewall blocks by IP, you must allowlist GitHub’s IPs (which can change).

## Step 1: Whitelist the Agent in Wordfence
Wordfence sees the Python `requests` module and assumes it's a malicious bot. You need to whitelist the REST API route or the IP address.

1. **Log in** to your WordPress Dashboard.
2. Go to **Wordfence > Firewall**.
3. Under the **Firewall Options**, find the section **Allowlisted URLs**.
4. Add the following rule to allow list the REST API endpoints:
   - **URL:** `/wp-json/wp/v2/`
   - **Param Type:** `Path`
   - **Match Type:** `Starts with`
5. Click **Add**, then click **Save Changes** in the top right corner.

*Alternative: If you have a static IP address for the server where your script runs (e.g., your Oracle VM), add it under **Advanced Firewall Options > Allowlisted IP addresses**.*

### Step 1b: When the agent runs on GitHub Actions (403 on publish)

Requests from GitHub Actions come from **GitHub’s IP ranges**, not a single IP. If you see **403 on media upload or post creation** only when the workflow runs (and it works from your PC), the firewall is blocking GitHub’s IPs.

1. Get the current **Actions runner IP ranges** (CIDR list):
   - Open: **https://api.github.com/meta**
   - Find the `"actions"` key in the JSON. It lists CIDR blocks (e.g. `"4.148.0.0/16"`, `"13.64.0.0/16"`, …).

2. In **Wordfence**:
   - Go to **Wordfence > Firewall** → **Advanced Firewall Options** → **Allowlisted IP addresses**.
   - Add each CIDR from the `actions` list (one per line).  
   - *Note: The list is long and can change. GitHub recommends re-checking the meta API periodically.*

3. **Cloudflare** (if you use it):  
   - Turn **Bot Fight Mode** off (free plan), or add a WAF rule to **Skip** all checks when **URI Path** starts with `/wp-json/` (see Step 3 below).

4. **Easier long-term option:** Use **Option A (webhook)** above, or run the agent from a machine with a **fixed IP** and allowlist only that IP.

## Step 2: Ensure Application Passwords are appropriately granted
1. Go to **Users > Profile**.
2. Scroll down to **Application Passwords**.
3. Ensure the password `Simon` generated here is the exact one you pasted into `.env`. Ensure that user has Author/Editor rights.

## Step 3: Cloudflare Settings (If Applicable)
If you are using Cloudflare, it aggressively blocks automated scripts like Python `requests` with a `403 Forbidden` response. 

**IMPORTANT: If you are on the Cloudflare Free Plan:**
Custom WAF rules **cannot** bypass the "Bot Fight Mode" challenge. If Bot Fight Mode is on, your script will always be blocked, regardless of the rules you set below.
1. Go to **Security > Bots**.
2. Toggle **Bot Fight Mode** to **Off**.

**If you are on a Paid Plan (Pro/Business):**
You can keep Bot Fight Mode on and bypass it with a Custom Rule:
1. Navigate to **Security > WAF** (Web Application Firewall) -> **Custom Rules**.
2. Create a rule to bypass security for the REST API:
   - **Field:** `URI Path`
   - **Operator:** `starts with`
   - **Value:** `/wp-json/`
   - **Choose action:** `Skip` 
   - Check **All remaining custom rules**
   - Check **Rate limiting rules**
   - Check **Browser Integrity Check**
   - Check **Bot Fight Mode** and **Super Bot Fight Mode**
3. Save and deploy the rule.
