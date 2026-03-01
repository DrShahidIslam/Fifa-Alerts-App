# RankMath meta title & description via REST

The FIFA News Agent sets **RankMath SEO** fields (meta title, meta description, focus keyword) when publishing posts. By default, WordPress does not expose these meta keys over the REST API, so they stay empty unless you register them.

## What to do

1. Open **`rankmath-rest-snippet.php`** in this folder.
2. Copy its full contents.
3. In WordPress: **Appearance → Theme File Editor** (or use FTP/cPanel), open your theme’s **`functions.php`**.
4. Paste the snippet at the end of `functions.php` (before the closing `?>` if present) and save.

Alternatively, create a small **must-use plugin**: in `wp-content/mu-plugins/` create e.g. `fifa-rankmath-rest.php` with the same code (with no closing `?>`), so it loads on every request without depending on the theme.

## After adding

- When the agent creates or updates a post, it will send `rank_math_title`, `rank_math_description`, and `rank_math_focus_keyword`.
- RankMath will then show and use these values in its meta title and meta description fields.
- If you don’t add the snippet, the agent still sets the post **title** and **excerpt**; RankMath can use those as fallbacks, but the dedicated meta fields will stay empty until you expose them via this snippet.
