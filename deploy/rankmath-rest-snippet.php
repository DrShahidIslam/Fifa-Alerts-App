<?php
/**
 * RankMath REST API — Allow FIFA News Agent to set meta title & description via REST.
 *
 * Add this to your theme's functions.php (or use a small must-use plugin) so that
 * the WordPress REST API accepts rank_math_title, rank_math_description, and
 * rank_math_focus_keyword when creating/updating posts. Without this, those meta
 * keys are not exposed to REST and RankMath fields stay empty when publishing via API.
 *
 * After adding: the agent's _set_rankmath_meta() will populate RankMath's meta
 * title, meta description, and focus keyword automatically.
 */

add_action( 'init', 'fifa_agent_register_rankmath_meta_for_rest', 20 );

function fifa_agent_register_rankmath_meta_for_rest() {
	$post_types = array( 'post' );

	foreach ( $post_types as $post_type ) {
		register_post_meta(
			$post_type,
			'rank_math_title',
			array(
				'show_in_rest'  => true,
				'single'        => true,
				'type'          => 'string',
				'auth_callback' => function() {
					return current_user_can( 'edit_posts' );
				},
			)
		);

		register_post_meta(
			$post_type,
			'rank_math_description',
			array(
				'show_in_rest'  => true,
				'single'        => true,
				'type'          => 'string',
				'auth_callback' => function() {
					return current_user_can( 'edit_posts' );
				},
			)
		);

		register_post_meta(
			$post_type,
			'rank_math_focus_keyword',
			array(
				'show_in_rest'  => true,
				'single'        => true,
				'type'          => 'string',
				'auth_callback' => function() {
					return current_user_can( 'edit_posts' );
				},
			)
		);
	}
}
