<?php
/**
 * FIFA News Agent — Publish webhook (foolproof; no firewall blocking).
 *
 * The agent sends the article JSON to this URL instead of calling the REST API.
 * This script runs on your server, so WordPress is accessed locally (no 403).
 *
 * SETUP:
 * 1. Copy this file to your WordPress site root (same folder as wp-config.php).
 * 2. Rename to something unguessable, e.g. fifa-publish-abc12xyz.php
 * 3. Set WP_PUBLISH_WEBHOOK_URL in your .env to https://yoursite.com/fifa-publish-abc12xyz.php
 * 4. In wp-config.php add: define('FIFA_AGENT_WEBHOOK_SECRET', 'your-long-random-secret');
 *    Use the same value for WP_PUBLISH_SECRET in the agent's .env.
 * 5. Optional — set the WordPress user used as post author and for publish_draft:
 *    define('FIFA_AGENT_WEBHOOK_AUTHOR', 'Simon');  // by login name
 *    or define('FIFA_AGENT_WEBHOOK_USER_ID', 2);     // by user ID (default 1)
 *
 * SECURITY: Only requests with the correct X-FIFA-Agent-Token are accepted.
 */

header('Content-Type: application/json');

// GET = ping only (no WordPress). Use to confirm the file is reachable; no secret needed.
if (!empty($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] === 'GET') {
    http_response_code(200);
    echo json_encode(['ok' => true, 'message' => 'FIFA webhook endpoint']);
    exit;
}

// Read and validate JSON before loading WordPress (avoids 502 from WP/plugins on bad requests)
$raw = file_get_contents('php://input');
$data = json_decode($raw, true);
if (!is_array($data)) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => 'Invalid JSON']);
    exit;
}

// Load WordPress (this file should be in the site root next to wp-config.php)
$wp_load = __DIR__ . '/wp-load.php';
if (!is_file($wp_load)) {
    $wp_load = dirname(__DIR__) . '/wp-load.php';
}
if (!is_file($wp_load)) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => 'WordPress not found']);
    exit;
}
require_once $wp_load;

// Author for new posts and for publish_draft (must be able to edit posts). Default 1.
$webhook_author_id = 1;
if (defined('FIFA_AGENT_WEBHOOK_USER_ID')) {
    $webhook_author_id = (int) FIFA_AGENT_WEBHOOK_USER_ID;
} elseif (defined('FIFA_AGENT_WEBHOOK_AUTHOR')) {
    $u = get_user_by('login', FIFA_AGENT_WEBHOOK_AUTHOR);
    if ($u) {
        $webhook_author_id = (int) $u->ID;
    }
}

$secret = isset($_SERVER['HTTP_X_FIFA_AGENT_TOKEN']) ? $_SERVER['HTTP_X_FIFA_AGENT_TOKEN'] : '';
$expected = defined('FIFA_AGENT_WEBHOOK_SECRET') ? FIFA_AGENT_WEBHOOK_SECRET : '';
if ($expected === '' || $secret !== $expected) {
    http_response_code(403);
    echo json_encode(['success' => false, 'message' => 'Invalid or missing token']);
    exit;
}

// Action: publish draft (change post status without going through REST API)
if (!empty($data['action']) && $data['action'] === 'publish_draft' && isset($data['post_id'])) {
    $post_id = (int) $data['post_id'];
    $new_status = isset($data['status']) && in_array($data['status'], ['draft', 'pending', 'publish'], true) ? $data['status'] : 'publish';
    if ($post_id > 0) {
        // Webhook runs with no logged-in user; WordPress blocks wp_update_post. Use the configured author.
        wp_set_current_user($webhook_author_id);
        $updated = wp_update_post(['ID' => $post_id, 'post_status' => $new_status], true);
        if (!is_wp_error($updated) && $updated > 0) {
            echo json_encode(['success' => true, 'post_id' => $post_id, 'post_url' => get_permalink($post_id), 'status' => $new_status]);
            exit;
        }
        $err_msg = is_wp_error($updated) ? $updated->get_error_message() : 'Update returned 0';
        http_response_code(400);
        echo json_encode(['success' => false, 'message' => $err_msg]);
        exit;
    }
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => 'Invalid post_id']);
    exit;
}

$title = isset($data['title']) ? sanitize_text_field($data['title']) : 'Untitled';
$content = isset($data['content']) ? $data['content'] : '';
$excerpt = isset($data['excerpt']) ? sanitize_textarea_field($data['excerpt']) : '';
$slug = isset($data['slug']) ? sanitize_title($data['slug']) : '';
$status = isset($data['status']) && in_array($data['status'], ['draft', 'pending', 'publish'], true) ? $data['status'] : 'draft';
$tags = isset($data['tags']) && is_array($data['tags']) ? $data['tags'] : [];
$category = isset($data['category']) ? sanitize_text_field($data['category']) : 'Blog';
$rank_title = isset($data['rank_math_title']) ? sanitize_text_field($data['rank_math_title']) : $title;
$rank_desc = isset($data['rank_math_description']) ? sanitize_textarea_field($data['rank_math_description']) : $excerpt;
$rank_kw = isset($data['rank_math_focus_keyword']) ? sanitize_text_field($data['rank_math_focus_keyword']) : '';
$faq_schema = isset($data['faq_schema']) ? $data['faq_schema'] : '';

// Create or get category
$cat_id = 0;
$terms = get_terms(['taxonomy' => 'category', 'name' => $category, 'hide_empty' => false]);
if (!empty($terms)) {
    $cat_id = (int) $terms[0]->term_id;
} else {
    $c = wp_insert_term($category, 'category');
    if (!is_wp_error($c)) {
        $cat_id = (int) $c['term_id'];
    }
}

// Create or get tags
$tag_ids = [];
foreach ($tags as $tag_name) {
    $tag_name = sanitize_text_field($tag_name);
    if ($tag_name === '')
        continue;
    $t = get_term_by('name', $tag_name, 'post_tag');
    if ($t) {
        $tag_ids[] = (int) $t->term_id;
    } else {
        $res = wp_insert_term($tag_name, 'post_tag');
        if (!is_wp_error($res)) {
            $tag_ids[] = (int) $res['term_id'];
        }
    }
}

// Featured image from base64
$featured_id = 0;
if (!empty($data['featured_image_base64']) && !empty($data['featured_image_filename'])) {
    $filename = sanitize_file_name(basename($data['featured_image_filename']));
    $mime = 'image/webp';
    if (preg_match('/\.(jpe?g|png)$/i', $filename)) {
        $mime = 'image/jpeg';
        if (preg_match('/\.png$/i', $filename))
            $mime = 'image/png';
    }
    $bytes = base64_decode($data['featured_image_base64'], true);
    if ($bytes !== false && strlen($bytes) > 0) {
        $upload = wp_upload_bits($filename, null, $bytes);
        if (empty($upload['error']) && !empty($upload['file'])) {
            $file_path = $upload['file'];
            $attachment = [
                'post_mime_type' => $upload['type'],
                'post_title' => $title,
                'post_content' => '',
                'post_status' => 'inherit',
            ];
            $attach_id = wp_insert_attachment($attachment, $file_path);
            if (!is_wp_error($attach_id)) {
                require_once ABSPATH . 'wp-admin/includes/image.php';
                wp_generate_attachment_metadata($attach_id, $file_path);
                $featured_id = (int) $attach_id;

                // Set the alt text for the featured image
                $alt_text = isset($data['featured_image_alt']) ? sanitize_text_field($data['featured_image_alt']) : $title;
                update_post_meta($featured_id, '_wp_attachment_image_alt', $alt_text);
            }
        }
    }
}

$post_arr = [
    'post_title' => $title,
    'post_content' => $content,
    'post_excerpt' => $excerpt,
    'post_name' => $slug,
    'post_status' => $status,
    'post_type' => 'post',
    'post_author' => $webhook_author_id,
    'comment_status' => 'open',
];
$post_id = wp_insert_post($post_arr, true);
if (is_wp_error($post_id)) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => $post_id->get_error_message()]);
    exit;
}

if ($post_id && $cat_id) {
    wp_set_post_terms($post_id, [$cat_id], 'category');
}
if ($post_id && !empty($tag_ids)) {
    wp_set_post_terms($post_id, $tag_ids, 'post_tag');
}
if ($post_id && $featured_id) {
    set_post_thumbnail($post_id, $featured_id);
}

// RankMath meta
update_post_meta($post_id, 'rank_math_title', $rank_title);
update_post_meta($post_id, 'rank_math_description', $rank_desc);
update_post_meta($post_id, 'rank_math_focus_keyword', $rank_kw);

// FAQ Schema meta (for Ultimate Event Schema Injector plugin)
if (!empty($faq_schema)) {
    // The plugin adds <script> tags automatically, so we need to strip them if they were included
    $clean_schema = preg_replace('#<script(.*?)>|</script>#is', '', $faq_schema);
    update_post_meta($post_id, '_ssi_schema_faq', wp_slash(trim($clean_schema)));
}

$post_url = get_permalink($post_id);
echo json_encode([
    'success' => true,
    'post_id' => (int) $post_id,
    'post_url' => $post_url,
    'status' => $status,
]);
