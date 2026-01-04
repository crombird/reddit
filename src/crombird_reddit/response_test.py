import datetime
from unittest.mock import patch

from .response import (
    _format_short,
    _generate_page_response,
    _generate_user_response,
    generate_response,
)


class TestFormatShort:
    def test_single_page_result(self):
        results = [
            {
                "wikidot_page": {
                    "url": "http://scp-wiki.wikidot.com/scp-173",
                    "title": "SCP-173",
                },
            }
        ]
        output = _format_short(results)
        assert output == "[SCP-173](https://scp-wiki.wikidot.com/scp-173)."

    def test_multiple_page_results(self):
        results = [
            {
                "wikidot_page": {
                    "url": "http://scp-wiki.wikidot.com/scp-173",
                    "title": "SCP-173",
                },
            },
            {
                "wikidot_page": {
                    "url": "http://scp-wiki.wikidot.com/scp-999",
                    "title": "SCP-999",
                },
            },
        ]
        output = _format_short(results)
        assert output == (
            "[SCP-173](https://scp-wiki.wikidot.com/scp-173), "
            "[SCP-999](https://scp-wiki.wikidot.com/scp-999)."
        )

    def test_user_result_with_author_page(self):
        results = [
            {
                "user": {
                    "displayName": "djkaktus",
                    "userPage": {"url": "http://scp-wiki.wikidot.com/djkaktus"},
                },
            }
        ]
        output = _format_short(results)
        assert output == "[*djkaktus*](https://scp-wiki.wikidot.com/djkaktus)."

    def test_user_result_without_author_page(self):
        results = [
            {
                "user": {
                    "displayName": "someuser",
                },
            }
        ]
        output = _format_short(results)
        assert output == "someuser."


class TestGeneratePageResponse:
    def _make_page_result(
        self,
        url="http://scp-wiki.wikidot.com/scp-173",
        title="SCP-173",
        rating=500,
        created_at="2024-01-01T00:00:00Z",
        alternate_titles=None,
        attributions=None,
    ):
        return {
            "url": url,
            "title": title,
            "rating": rating,
            "createdAt": created_at,
            "alternateTitles": alternate_titles or [],
            "attributions": attributions or [],
        }

    def test_basic_page_response(self):
        result = self._make_page_result()
        output = _generate_page_response(
            result, matching_pages=[], as_list_item=False, is_submission_url=False
        )
        assert output == "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+500)\n"

    def test_page_as_list_item(self):
        result = self._make_page_result()
        output = _generate_page_response(
            result, matching_pages=[], as_list_item=True, is_submission_url=False
        )
        assert (
            output == "- [**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+500)\n"
        )

    def test_submission_url_hides_rating(self):
        result = self._make_page_result()
        output = _generate_page_response(
            result, matching_pages=[], as_list_item=False, is_submission_url=True
        )
        assert output == "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173)\n"

    def test_alternate_title_shown(self):
        result = self._make_page_result(alternate_titles=[{"title": "The Sculpture"}])
        output = _generate_page_response(
            result, matching_pages=[], as_list_item=False, is_submission_url=False
        )
        assert (
            output
            == "[**SCP-173 ⁠- The Sculpture**](https://scp-wiki.wikidot.com/scp-173) (+500)\n"
        )

    def test_alternate_title_same_as_title_not_shown(self):
        result = self._make_page_result(
            title="SCP-173", alternate_titles=[{"title": "SCP-173"}]
        )
        output = _generate_page_response(
            result, matching_pages=[], as_list_item=False, is_submission_url=False
        )
        # Should only appear once (in the link), not twice
        assert output == "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+500)\n"

    def test_attributions_shown(self):
        result = self._make_page_result(
            attributions=[
                {"type": "AUTHOR", "user": {"displayName": "djkaktus"}},
            ]
        )
        output = _generate_page_response(
            result, matching_pages=[], as_list_item=False, is_submission_url=False
        )
        assert output == (
            "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+500) by *djkaktus*\n"
        )

    def test_multiple_attributions(self):
        result = self._make_page_result(
            attributions=[
                {"type": "AUTHOR", "user": {"displayName": "author1"}},
                {"type": "AUTHOR", "user": {"displayName": "author2"}},
            ]
        )
        output = _generate_page_response(
            result, matching_pages=[], as_list_item=False, is_submission_url=False
        )
        assert output == (
            "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+500) "
            "by *author1, author2*\n"
        )

    def test_multiple_attributions_ordering(self):
        result = self._make_page_result(
            attributions=[
                {"type": "AUTHOR", "user": {"displayName": "author1"}},
                {"type": "REWRITE", "user": {"displayName": "author2"}},
            ]
        )
        output = _generate_page_response(
            result, matching_pages=[], as_list_item=False, is_submission_url=False
        )
        assert output == (
            "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+500) "
            "by *author2, author1*\n"
        )

    def test_negative_rating_formatted(self):
        result = self._make_page_result(rating=-50)
        output = _generate_page_response(
            result, matching_pages=[], as_list_item=False, is_submission_url=False
        )
        assert output == "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (-50)\n"

    @patch("crombird_reddit.response.datetime")
    def test_recent_page_shows_timeago(self, mock_datetime):
        # Mock datetime.now() to return a fixed time
        fixed_now = datetime.datetime(2024, 1, 5, 12, 0, 0)
        mock_datetime.datetime.now.return_value = fixed_now
        mock_datetime.datetime.fromisoformat = datetime.datetime.fromisoformat
        mock_datetime.timedelta = datetime.timedelta

        result = self._make_page_result(
            created_at="2024-01-04T00:00:00Z",  # 1 day ago
            attributions=[{"type": "AUTHOR", "user": {"displayName": "author1"}}],
        )
        output = _generate_page_response(
            result, matching_pages=[], as_list_item=False, is_submission_url=False
        )
        assert output == (
            "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+500) "
            "posted 1 day ago by *author1*\n"
        )

    def test_translation_filters_translators(self):
        result = self._make_page_result(
            attributions=[
                {"type": "AUTHOR", "user": {"displayName": "original_author"}},
                {"type": "TRANSLATOR", "user": {"displayName": "translator1"}},
            ]
        )
        output = _generate_page_response(
            result,
            matching_pages=[],
            as_list_item=False,
            is_submission_url=False,
            is_translation=True,
        )
        assert output == (
            "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+500) "
            "by *translator1*\n"
        )

    def test_translation_fallback_when_no_translators(self):
        result = self._make_page_result(
            attributions=[
                {"type": "AUTHOR", "user": {"displayName": "original_author"}},
            ]
        )
        output = _generate_page_response(
            result,
            matching_pages=[],
            as_list_item=False,
            is_submission_url=False,
            is_translation=True,
        )
        # Falls back to all attributions when no translators
        assert output == (
            "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+500) "
            "by *original_author*\n"
        )

    def test_foreign_page_with_english_translation(self):
        result = self._make_page_result(
            url="http://scp-jp.wikidot.com/scp-173-jp",
            title="SCP-173-JP",
        )
        matching_pages = [
            {
                "url": "http://scp-wiki.wikidot.com/scp-173-jp",
                "title": "SCP-173-JP (English)",
                "rating": 100,
                "createdAt": "2024-01-01T00:00:00Z",
                "alternateTitles": [],
                "attributions": [],
            }
        ]
        output = _generate_page_response(
            result,
            matching_pages=matching_pages,
            as_list_item=False,
            is_submission_url=False,
        )
        assert output == (
            "[**SCP-173-JP**](https://scp-jp.wikidot.com/scp-173-jp) (+500)\n"
            "\n"
            "Translated: [**SCP-173-JP (English)**]"
            "(https://scp-wiki.wikidot.com/scp-173-jp) (+100)\n"
            "\n"
        )


class TestGenerateUserResponse:
    def _make_user_result(
        self,
        display_name="djkaktus",
        total_rating=50000,
        rank=1,
        mean_rating=100,
        user_page_url=None,
    ):
        result = {
            "displayName": display_name,
            "statistics": {
                "totalRating": total_rating,
                "rank": rank,
                "meanRating": mean_rating,
            },
        }
        if user_page_url:
            result["userPage"] = {"url": user_page_url}
        return result

    def test_basic_user_response(self):
        result = self._make_user_result()
        output = _generate_user_response(result, as_list_item=False)
        assert output == (
            "**djkaktus** (*ranked #1, total rating: +50000, mean rating: +100)*\n"
        )

    def test_user_with_author_page(self):
        result = self._make_user_result(
            user_page_url="http://scp-wiki.wikidot.com/djkaktus"
        )
        output = _generate_user_response(result, as_list_item=False)
        assert output == (
            "**[djkaktus](https://scp-wiki.wikidot.com/djkaktus)** "
            "(*ranked #1, total rating: +50000, mean rating: +100)*\n"
        )

    def test_user_as_list_item(self):
        result = self._make_user_result()
        output = _generate_user_response(result, as_list_item=True)
        assert output == (
            "- **djkaktus** (*ranked #1, total rating: +50000, mean rating: +100)*\n"
        )

    def test_negative_mean_rating(self):
        result = self._make_user_result(mean_rating=-10)
        output = _generate_user_response(result, as_list_item=False)
        assert output == (
            "**djkaktus** (*ranked #1, total rating: +50000, mean rating: -10)*\n"
        )


class TestGenerateResponse:
    def _make_page_result(self, url, title, rating=100):
        return {
            "wikidot_page": {
                "url": url,
                "title": title,
                "rating": rating,
                "createdAt": "2024-01-01T00:00:00Z",
                "alternateTitles": [],
                "attributions": [],
            },
        }

    def _make_user_result(self, name):
        return {
            "user": {
                "displayName": name,
                "statistics": {
                    "totalRating": 1000,
                    "rank": 10,
                    "meanRating": 50,
                },
            },
        }

    def test_single_page_not_list_item(self):
        results = [
            self._make_page_result("http://scp-wiki.wikidot.com/scp-173", "SCP-173")
        ]
        output = generate_response(results)
        assert output == (
            "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+100)\n"
        )

    def test_multiple_pages_are_list_items(self):
        results = [
            self._make_page_result("http://scp-wiki.wikidot.com/scp-173", "SCP-173"),
            self._make_page_result("http://scp-wiki.wikidot.com/scp-999", "SCP-999"),
        ]
        output = generate_response(results)
        assert output == (
            "- [**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+100)\n"
            "- [**SCP-999**](https://scp-wiki.wikidot.com/scp-999) (+100)\n"
        )

    def test_submission_adds_header(self):
        results = [
            self._make_page_result("http://scp-wiki.wikidot.com/scp-173", "SCP-173")
        ]
        output = generate_response(results, is_submission=True)
        assert output == (
            "**Articles mentioned in this submission**\n\n"
            "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+100)\n"
        )

    def test_submission_url_hides_rating_for_matching_url(self):
        url = "http://scp-wiki.wikidot.com/scp-173"
        results = [self._make_page_result(url, "SCP-173", rating=500)]
        output = generate_response(results, submission_url=url)
        assert output == "[**SCP-173**](https://scp-wiki.wikidot.com/scp-173)\n"

    def test_more_than_10_results_uses_short_format(self):
        results = [
            self._make_page_result(
                f"http://scp-wiki.wikidot.com/scp-{i:03d}", f"SCP-{i:03d}"
            )
            for i in range(11)
        ]
        output = generate_response(results, is_submission=False)
        assert output == (
            "[SCP-000](https://scp-wiki.wikidot.com/scp-000), "
            "[SCP-001](https://scp-wiki.wikidot.com/scp-001), "
            "[SCP-002](https://scp-wiki.wikidot.com/scp-002), "
            "[SCP-003](https://scp-wiki.wikidot.com/scp-003), "
            "[SCP-004](https://scp-wiki.wikidot.com/scp-004), "
            "[SCP-005](https://scp-wiki.wikidot.com/scp-005), "
            "[SCP-006](https://scp-wiki.wikidot.com/scp-006), "
            "[SCP-007](https://scp-wiki.wikidot.com/scp-007), "
            "[SCP-008](https://scp-wiki.wikidot.com/scp-008), "
            "[SCP-009](https://scp-wiki.wikidot.com/scp-009), "
            "[SCP-010](https://scp-wiki.wikidot.com/scp-010)."
        )

    def test_more_than_10_results_in_submission_uses_long_format(self):
        results = [
            self._make_page_result(
                f"http://scp-wiki.wikidot.com/scp-{i:03d}", f"SCP-{i:03d}"
            )
            for i in range(11)
        ]
        output = generate_response(results, is_submission=True)
        assert output == (
            "**Articles mentioned in this submission**\n\n"
            "- [**SCP-000**](https://scp-wiki.wikidot.com/scp-000) (+100)\n"
            "- [**SCP-001**](https://scp-wiki.wikidot.com/scp-001) (+100)\n"
            "- [**SCP-002**](https://scp-wiki.wikidot.com/scp-002) (+100)\n"
            "- [**SCP-003**](https://scp-wiki.wikidot.com/scp-003) (+100)\n"
            "- [**SCP-004**](https://scp-wiki.wikidot.com/scp-004) (+100)\n"
            "- [**SCP-005**](https://scp-wiki.wikidot.com/scp-005) (+100)\n"
            "- [**SCP-006**](https://scp-wiki.wikidot.com/scp-006) (+100)\n"
            "- [**SCP-007**](https://scp-wiki.wikidot.com/scp-007) (+100)\n"
            "- [**SCP-008**](https://scp-wiki.wikidot.com/scp-008) (+100)\n"
            "- [**SCP-009**](https://scp-wiki.wikidot.com/scp-009) (+100)\n"
            "- [**SCP-010**](https://scp-wiki.wikidot.com/scp-010) (+100)\n"
        )

    def test_mixed_page_and_user_results(self):
        results = [
            self._make_page_result("http://scp-wiki.wikidot.com/scp-173", "SCP-173"),
            self._make_user_result("djkaktus"),
        ]
        output = generate_response(results)
        assert output == (
            "- [**SCP-173**](https://scp-wiki.wikidot.com/scp-173) (+100)\n"
            "- **djkaktus** (*ranked #10, total rating: +1000, mean rating: +50)*\n"
        )

    def test_empty_results(self):
        output = generate_response([])
        assert output == ""
