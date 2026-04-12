# FIFA 2026 Pinterest Bot — Production Ready 🚀

This bot is now fully integrated with your WordPress site content and ready for high-volume automation.

## GitHub Actions Deployment
The bot is configured to run every 4 hours via GitHub Actions. To go live:
1.  **Add Secrets:** Go to your GitHub Repository -> Settings -> Secrets and Variables -> Actions.
2.  **Required Secrets:** Create the following secrets using the values from your `.env`:
    - `GEMINI_API_KEYS`
    - `SILICONFLOW_API_KEY`
    - `PINTEREST_ACCESS_TOKEN` (The fresh one)
    - `PINTEREST_REFRESH_TOKEN` (The Production JWK)
    - `PINTEREST_BOARD_MATCH_PREVIEWS` (and other board IDs)

## Switching from Sandbox to Production
1.  In `main.py`, change `PINTEREST_API_BASE` from `api-sandbox` to `api.pinterest.com`.
2.  Update the `PINTEREST_ACCESS_TOKEN` with your final Production token.
3.  Ensure your Board IDs in `.env` or GitHub Secrets are the **Real IDs** (not Sandbox).

## Content Mode
The bot defaults to **Site-Mode**. It intelligently picks an article from your library and creates a Pin linking back to it.
-   To change this, edit the `.github/workflows/fifa-pinterest-bot.yml` command to `--mode trends`.

---
*Developed for DrShahidIslam/Fifa-Alerts-App*
