from datetime import datetime
from unittest.mock import patch

from .parse import (
    parse,
    ParseContext,
    SearchQuery,
    SearchQueryType,
)


class TestModernMatchSyntax:
    def test_single_modern_match(self):
        result = parse("Check out [[SCP-173]]", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-173",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_multiple_modern_matches(self):
        result = parse("[[SCP-173]] and [[SCP-999]]", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-173",
                site_url="http://scp-wiki.wikidot.com",
            ),
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-999",
                site_url="http://scp-wiki.wikidot.com",
            ),
        ]

    def test_modern_match_with_freeform_text(self):
        result = parse("[[The Ouroboros Cycle]]", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="The Ouroboros Cycle",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_modern_match_with_author_name(self):
        result = parse("[[djkaktus]]", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="djkaktus",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_empty_modern_match_ignored(self):
        result = parse("[[]]", ParseContext.COMMENT_BODY)
        assert result == []

    def test_whitespace_only_modern_match_ignored(self):
        result = parse("[[   ]]", ParseContext.COMMENT_BODY)
        assert result == []

    def test_modern_match_international_jp(self):
        result = parse("[[SCP-173-JP]]", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-173-JP",
                site_url="http://scp-jp.wikidot.com",
            )
        ]

    def test_modern_match_international_fr(self):
        result = parse("[[SCP-173-FR]]", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-173-FR",
                site_url="http://fondationscp.wikidot.com",
            )
        ]


class TestBareSCPMentions:
    def test_single_bare_mention(self):
        result = parse("I love SCP-999", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-999",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_bare_mention_with_hyphen(self):
        result = parse("SCP-173 is scary", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-173",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_bare_mention_with_space(self):
        result = parse("SCP 173 is scary", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP 173",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_bare_mention_with_suffix(self):
        result = parse("SCP-049-J is funny", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-049-J",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_bare_mention_with_extended_suffix(self):
        result = parse("SCP-001-EX is declassified", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-001-EX",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_multiple_bare_mentions(self):
        result = parse("SCP-173 and SCP-682", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-173",
                site_url="http://scp-wiki.wikidot.com",
            ),
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-682",
                site_url="http://scp-wiki.wikidot.com",
            ),
        ]

    def test_bare_mention_case_insensitive(self):
        result = parse("scp-173 and SCP-999", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="scp-173",
                site_url="http://scp-wiki.wikidot.com",
            ),
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-999",
                site_url="http://scp-wiki.wikidot.com",
            ),
        ]

    def test_four_digit_scp(self):
        result = parse("SCP-3000 is deep", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-3000",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_five_digit_scp(self):
        result = parse("SCP-10000 is cool", ParseContext.COMMENT_BODY)
        assert result == []


class TestInternationalBranches:
    def test_jp_branch(self):
        result = parse("SCP-173-JP is cool", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.BARE,
                value="173-JP",
                site_url="http://scp-jp.wikidot.com",
            )
        ]

    def test_cn_branch_prefix(self):
        result = parse("SCP-CN-173", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.BARE,
                value="CN-173",
                site_url="http://scp-wiki-cn.wikidot.com",
            )
        ]

    def test_it_branch_suffix(self):
        result = parse("SCP 173-IT", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.BARE,
                value="173-IT",
                site_url="http://fondazionescp.wikidot.com",
            )
        ]

    def test_it_branch_suffix_negative(self):
        result = parse("SCP-173 IT IS SCARY", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-173",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_int_branch(self):
        result = parse("SCP-173 INT", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.BARE,
                value="173 INT",
                site_url="http://scp-int.wikidot.com",
            )
        ]


class TestFalsePositiveRemoval:
    def test_url_removed(self):
        result = parse(
            "Check https://example.com/SCP-173 for info", ParseContext.COMMENT_BODY
        )
        assert result == []

    def test_decimal_number_not_matched(self):
        result = parse("The value is 3.141 and SCP-173", ParseContext.COMMENT_BODY)
        # Should only match SCP-173, not treat 3.141 as SCP-related
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-173",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_username_mention_removed(self):
        result = parse("Hey u/SCP-173 check this out", ParseContext.COMMENT_BODY)
        assert result == []

    def test_username_mention_with_slash_removed(self):
        result = parse("Hey /u/SCP-173 check this out", ParseContext.COMMENT_BODY)
        assert result == []

    def test_spoiler_tag_content_removed(self):
        result = parse("Spoiler: >!SCP-173 is scary!<", ParseContext.COMMENT_BODY)
        assert result == []

    def test_code_block_removed(self):
        result = parse("Here is code `SCP-173`", ParseContext.COMMENT_BODY)
        assert result == []

    def test_link_text_removed(self):
        result = parse(
            "Check [SCP-173](https://example.com)", ParseContext.COMMENT_BODY
        )
        assert result == []

    def test_modern_match_not_affected_by_false_positives(self):
        # Modern match [[...]] should still work even with decimal numbers
        result = parse("[[3.141]]", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="3.141",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]


class TestContextBehavior:
    def test_submission_title_no_markdown_sanitization(self):
        # In SUBMISSION_TITLE context, markdown is NOT sanitized
        # So a link-like text would still be parsed
        result = parse("[SCP-173](url)", ParseContext.SUBMISSION_TITLE)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-173",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]

    def test_submission_selftext_sanitizes_markdown(self):
        result = parse(
            "[SCP-173](https://example.com)", ParseContext.SUBMISSION_SELFTEXT
        )
        assert result == []

    def test_comment_body_sanitizes_markdown(self):
        result = parse("[SCP-173](https://example.com)", ParseContext.COMMENT_BODY)
        assert result == []


class TestAprilFools:
    @patch("crombird_reddit.parse.datetime")
    def test_scp2_on_april_fools(self, mock_datetime):
        mock_datetime.today.return_value = datetime(2024, 4, 1)
        result = parse("The number 2 is interesting", ParseContext.COMMENT_BODY)
        assert (
            SearchQuery(
                type=SearchQueryType.BARE,
                value="2",
                site_url="http://scp-wiki.wikidot.com",
            )
            in result
        )

    @patch("crombird_reddit.parse.datetime")
    def test_scp2_not_on_regular_day(self, mock_datetime):
        mock_datetime.today.return_value = datetime(2024, 3, 15)
        result = parse("The number 2 is interesting", ParseContext.COMMENT_BODY)
        assert result == []

    @patch("crombird_reddit.parse.datetime")
    def test_scp2_only_in_comment_body(self, mock_datetime):
        mock_datetime.today.return_value = datetime(2024, 4, 1)
        result = parse("The number 2 is interesting", ParseContext.SUBMISSION_TITLE)
        # Should not match because it's not COMMENT_BODY context
        scp2_query = SearchQuery(
            type=SearchQueryType.BARE,
            value="2",
            site_url="http://scp-wiki.wikidot.com",
        )
        assert scp2_query not in result


class TestMixedContent:
    def test_modern_and_bare_together(self):
        result = parse("[[djkaktus]] wrote SCP-173", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="djkaktus",
                site_url="http://scp-wiki.wikidot.com",
            ),
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-173",
                site_url="http://scp-wiki.wikidot.com",
            ),
        ]

    def test_international_and_english_together(self):
        result = parse("SCP-173-JP and SCP-999", ParseContext.COMMENT_BODY)
        assert result == [
            SearchQuery(
                type=SearchQueryType.BARE,
                value="173-JP",
                site_url="http://scp-jp.wikidot.com",
            ),
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-999",
                site_url="http://scp-wiki.wikidot.com",
            ),
        ]

    def test_empty_text(self):
        result = parse("", ParseContext.COMMENT_BODY)
        assert result == []

    def test_no_matches(self):
        result = parse("Just some regular text", ParseContext.COMMENT_BODY)
        assert result == []
