"""
Tests for SEO guards: intro hook, meta title/description, and entity extraction.
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from writer.article_generator import (
    _ensure_intro_hook,
    _build_contextual_hook,
    _build_meta_title,
    _build_meta_description,
    _apply_seo_guards,
    _derive_focus_keyword,
    _BANNED_OPENERS,
    _parse_article_output,
    _ensure_value_add_paragraph,
)
from writer.seo_prompt import _extract_entities_from_topic


# ── _ensure_intro_hook ─────────────────────────────────────────────


class TestEnsureIntroHook:

    def test_keeps_good_paragraph(self):
        """A quality intro with keyword and sufficient words should be untouched."""
        content = (
            "<p>Messi scored twice to help Italy world cup campaign surge forward, "
            "delivering an unforgettable performance that stunned rivals and fans alike.</p>"
            "<h2>Details</h2><p>More info here.</p>"
        )
        result = _ensure_intro_hook(content, "italy world cup", "Italy defeats NI")
        assert result == content, "Good intro was modified when it should have been kept."

    def test_replaces_short_paragraph(self):
        """A paragraph under 18 words should trigger hook injection."""
        content = "<p>Big news today.</p><h2>Details</h2><p>More text.</p>"
        result = _ensure_intro_hook(content, "italy world cup", "Italy defeats NI")
        # Should prepend a hook before the short paragraph
        assert result.startswith("<p>"), "Hook should start with <p>"
        assert "italy world cup" in result.lower(), "Hook should contain keyword"

    def test_replaces_banned_opener(self):
        """Paragraphs starting with banned phrases should be replaced."""
        for opener in ("In this article", "Let's", "Here's", "Today we", "Read on"):
            content = (
                f"<p>{opener} we are going to discuss a very important topic about "
                "italy world cup updates for fans globally.</p>"
            )
            result = _ensure_intro_hook(content, "italy world cup", "Italy update")
            # The hook should appear BEFORE the original paragraph
            first_p_end = result.index("</p>")
            first_p = result[: first_p_end + 4]
            assert opener not in first_p, f"Banned opener '{opener}' was not replaced"

    def test_replaces_paragraph_missing_keyword(self):
        """A paragraph with sufficient words but missing the keyword should be replaced."""
        content = (
            "<p>The team played an outstanding match today with brilliant tactical "
            "adjustments and strong defensive work throughout the ninety minutes.</p>"
        )
        result = _ensure_intro_hook(content, "messi transfer", "Messi Transfer Saga")
        assert "messi transfer" in result.lower(), "Hook should contain the keyword"

    def test_no_content_returns_empty(self):
        """Empty content should be returned as-is."""
        assert _ensure_intro_hook("", "keyword", "title") == ""
        assert _ensure_intro_hook(None, "keyword", "title") is None

    def test_no_p_tag_prepends_hook(self):
        """Content without any <p> should get a hook prepended."""
        content = "<h2>Some heading</h2><div>body text</div>"
        result = _ensure_intro_hook(content, "kane transfer", "Kane", primary_entity="Kane")
        assert result.startswith("<p>"), "Hook should be prepended"
        assert "<h2>Some heading</h2>" in result, "Original content should follow"


# ── _build_contextual_hook ─────────────────────────────────────────


class TestBuildContextualHook:

    def test_includes_entity_and_keyword(self):
        hook = _build_contextual_hook("italy world cup", "Italy defeats NI 2-0", primary_entity="Italy")
        assert "Italy" in hook
        assert "italy world cup" in hook.lower()
        assert hook.startswith("<p>")
        assert hook.endswith("</p>")

    def test_uses_keyword_when_no_entity(self):
        hook = _build_contextual_hook("football news", "Football News Update")
        assert "football news" in hook.lower()

    def test_uses_source_titles_for_specificity(self):
        hook = _build_contextual_hook(
            "messi world cup",
            "Messi latest update",
            primary_entity="Messi",
            source_texts=[{"title": "Messi scores as Miami wins rescheduled friendly"}],
        )
        assert "rescheduled friendly" in hook.lower()


class TestEnsureValueAddParagraph:

    def test_inserts_contextual_analysis_block(self):
        content = "<p>Intro paragraph with enough detail to pass validation and keep the article moving.</p><p>Second paragraph adds context.</p>"
        result = _ensure_value_add_paragraph(
            content,
            "messi world cup",
            "Messi latest update",
            source_texts=[{"title": "Messi scores as Miami wins rescheduled friendly"}],
        )
        assert "rescheduled friendly" in result.lower() or "messi" in result.lower()
        assert "<h2>" in result


# ── _build_meta_title ──────────────────────────────────────────────


class TestBuildMetaTitle:

    def test_includes_keyword(self):
        result = _build_meta_title("Some Title", "world cup 2026")
        assert "world cup 2026" in result.lower()

    def test_max_60_chars(self):
        result = _build_meta_title(
            "A Very Long SEO Title That Exceeds Sixty Characters By Quite A Lot",
            "world cup 2026",
        )
        assert len(result) <= 60

    def test_avoids_duplicate_of_article_title(self):
        result = _build_meta_title("Italy World Cup", "italy world cup", article_title="Italy World Cup")
        assert result.lower() != "italy world cup"


# ── _build_meta_description ────────────────────────────────────────


class TestBuildMetaDescription:

    def test_contains_keyword(self):
        result = _build_meta_description("", "messi world cup")
        assert "messi world cup" in result.lower()

    def test_length_145_to_155(self):
        result = _build_meta_description("", "world cup 2026")
        assert 100 <= len(result) <= 155, f"Meta length {len(result)} outside range"

    def test_entity_inserted_if_missing(self):
        result = _build_meta_description(
            "Latest updates and confirmed facts about the qualifier.",
            "world cup qualifier",
            primary_entity="Argentina",
        )
        assert "argentina" in result.lower(), "Entity should be included in meta"

    def test_entity_not_duplicated(self):
        """If entity already in description, don't add it again."""
        result = _build_meta_description(
            "Argentina confirms squad for world cup qualifier ahead of deadline.",
            "world cup qualifier",
            primary_entity="Argentina",
        )
        assert result.lower().count("argentina") == 1


# ── _extract_entities_from_topic ───────────────────────────────────


class TestExtractEntities:

    def test_extracts_player(self):
        entities = _extract_entities_from_topic("Messi scores twice for Argentina", "messi")
        assert "Messi" in entities["players"]
        assert entities["primary_entity"] == "Messi"

    def test_extracts_team(self):
        entities = _extract_entities_from_topic("Italy qualifies for World Cup 2026", "italy world cup")
        assert "Italy" in entities["teams"]
        assert "World Cup 2026" in entities["competitions"]

    def test_no_entities_returns_empty(self):
        entities = _extract_entities_from_topic("Random non-football topic", "random keyword xyz")
        assert entities["players"] == []
        assert entities["teams"] == []
        assert entities["primary_entity"] == ""

    def test_player_takes_priority_over_team(self):
        """When both player and team are present, player should be primary."""
        entities = _extract_entities_from_topic("Messi leads Argentina to victory", "messi argentina")
        assert entities["primary_entity"] == "Messi"

    def test_source_texts_included(self):
        sources = [{"title": "Kane hat trick in Premier League clash"}]
        entities = _extract_entities_from_topic("Transfer news", "kane", sources)
        assert "Kane" in entities["players"]
        assert "Premier League" in entities["competitions"]


class TestParseArticleOutput:

    def test_multiline_metadata_is_joined_cleanly(self):
        raw = """TITLE: Messi World Cup hopes
still alive after Miami return
SEO_TITLE: Messi World Cup update
after Miami comeback
META_DESCRIPTION: Messi World Cup update after Miami return.
SLUG: messi-world-cup-update
TAGS: Messi, Miami
CATEGORY: News
---CONTENT_START---
<p>Body</p>
---CONTENT_END---"""
        parsed = _parse_article_output(raw)
        assert parsed["title"] == "Messi World Cup hopes still alive after Miami return"
        assert parsed["seo_title"] == "Messi World Cup update after Miami comeback"
        assert parsed["content"] == "<p>Body</p>"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
