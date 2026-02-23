# Deploy to GitHub Actions — Beginner Guide

> Your agent will run every 30 minutes on GitHub's servers, completely free.
> No credit card. No server. No maintenance. Just push code to GitHub.

---

## PART 1: Create a GitHub Account (skip if you have one)

1. Go to **https://github.com** → Click **Sign up**
2. Enter your email, create a password, pick a username
3. Verify your email — done!

---

## PART 2: Create a Repository (2 minutes)

### Step 2.1 — Create new repo
1. Go to **https://github.com/new**
2. Fill in:

| Field | What to enter |
|-------|--------------|
| **Repository name** | `fifa-news-agent` |
| **Description** | `Automated FIFA World Cup 2026 news tracker` |
| **Visibility** | **Public** (required for free GitHub Actions minutes) |

3. Do NOT check "Add a README file"
4. Click **Create repository**

### Step 2.2 — You'll see a page with setup instructions. Keep this page open!

---

## PART 3: Add Your API Keys as Secrets (3 minutes)

> GitHub Secrets keep your API keys safe — they're encrypted and never visible in logs.

### Step 3.1 — Go to Settings
1. On your new repo page, click the **Settings** tab (top right, with gear icon)
2. In the left sidebar, click **Secrets and variables** → **Actions**
3. Click **New repository secret**

### Step 3.2 — Add each secret one by one

Click **"New repository secret"** for each of these (7 total):

| Name (copy exactly) | Value (from your .env file) |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `NEWS_API_KEY` | Your NewsAPI key |
| `GEMINI_API_KEY` | Your Gemini API key |
| `WP_URL` | `https://fifa-worldcup26.com` |
| `WP_USERNAME` | Your WordPress username |
| `WP_APP_PASSWORD` | Your WordPress app password |

For each one:
1. Click **New repository secret**
2. Paste the **Name** in the "Name" field
3. Paste the **Value** in the "Secret" field
4. Click **Add secret**
5. Repeat for all 7

---

## PART 4: Push Your Code to GitHub (3 minutes)

### Step 4.1 — Install Git (if not installed)
- Open PowerShell → type `git --version`
- If it says "not recognized", download Git from: **https://git-scm.com/download/win**
- Install with all defaults → restart PowerShell

### Step 4.2 — Push your code
Open **PowerShell** and run these commands one by one:

```powershell
cd "G:\Fifa Alerts App"
```

```powershell
git init
```

```powershell
git add .
```

```powershell
git commit -m "Initial commit - FIFA News Agent"
```

Now connect to your GitHub repo (replace YOUR_USERNAME with your GitHub username):

```powershell
git remote add origin https://github.com/YOUR_USERNAME/fifa-news-agent.git
```

```powershell
git branch -M main
```

```powershell
git push -u origin main
```

> **If asked to log in:** A browser window will open. Log into GitHub and authorize.

---

## PART 5: Verify It Works (2 minutes)

### Step 5.1 — Check the Actions tab
1. Go to your repo on GitHub: `https://github.com/YOUR_USERNAME/fifa-news-agent`
2. Click the **Actions** tab (near the top)
3. You should see **"FIFA News Agent - Scan"** listed

### Step 5.2 — Run it manually for the first time
1. Click on **"FIFA News Agent - Scan"** (the workflow name)
2. Click the **"Run workflow"** dropdown button (right side)
3. Click the green **"Run workflow"** button
4. Wait about 1-2 minutes → refresh the page
5. You should see a green checkmark ✅

### Step 5.3 — Check your Telegram
You should receive your first trending alerts! 🎉

---

## PART 6: You're Done!

The agent will now **automatically run every 30 minutes**, 24/7, for free.

### How it works
- GitHub starts a fresh server every 30 minutes
- Installs Python + your packages (takes ~30 seconds)
- Runs your scan (`main.py --once`)
- Sends Telegram alerts if anything is trending
- Server shuts down → costs you nothing

### Useful info

| What | Where to find it |
|------|------------------|
| See all runs | GitHub → Actions tab |
| See logs of a run | Click on any run → click "scan" → expand steps |
| Run manually | Actions → "FIFA News Agent - Scan" → "Run workflow" |
| Disable the agent | Actions → click workflow → three dots (...) → "Disable workflow" |
| Re-enable | Same place → "Enable workflow" |

### How to update code later
When you change any file:

```powershell
cd "G:\Fifa Alerts App"
git add .
git commit -m "Updated scan logic"
git push
```

That's it — next run will use your new code automatically.

---

## Troubleshooting

**"Run workflow" button is greyed out:**
- Make sure you're on the correct branch (main)
- Try refreshing the page

**Workflow fails with red X:**
- Click on the failed run → click "scan" → read the error log
- Most common: a secret name is misspelled. Double-check all 7 secret names.

**Not getting Telegram messages:**
- Check that TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID secrets are correct
- Make sure you've started a chat with your bot on Telegram first

**"No module named X" error:**
- Check that `requirements.txt` is in the root of your repo and has all packages listed
