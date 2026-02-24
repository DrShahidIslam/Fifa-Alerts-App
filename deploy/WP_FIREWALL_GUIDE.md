# Troubleshooting WordPress API 403 Forbidden Errors (Wordfence & Cloudflare)

The agent runs an automated Python script, which lacks typical browser headers. Security plugins aggressively block these specific requests to protect against brute-force attacks and scraping. Here's how to allow the agent through.

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

*Alternative: If you have a static IP address for the server where your script runs (e.g., your Oracle VM or the GitHub Actions runner IP ranges), you can add those under **Advanced Firewall Options > Allowlisted IP addresses**.*

## Step 2: Ensure Application Passwords are appropriately granted
1. Go to **Users > Profile**.
2. Scroll down to **Application Passwords**.
3. Ensure the password `Simon` generated here is the exact one you pasted into `.env`. Ensure that user has Author/Editor rights.

## Step 3: Cloudflare Settings (If Applicable)
If you are using Cloudflare, it might be issuing a "Browser Integrity Check" challenge (the 502/403 errors we saw in the logs).

1. Go to your **Cloudflare Dashboard**.
2. Navigate to **Security > WAF** (Web Application Firewall) -> **Custom Rules**.
3. Create a rule to bypass security for the REST API:
   - **Field:** `URI Path`
   - **Operator:** `starts with`
   - **Value:** `/wp-json/`
   - **Choose action:** `Skip` or `Bypass` (select all security checks like Browser Integrity Check and Bot Fight Mode).
4. Save and deploy the rule.
