import datetime
from datetime import timedelta
from unittest.mock import MagicMock, patch

from .bot import (
    _get_start_time,
    _create_streams,
    _check_revisit_submissions,
    _check_revisit_comments,
    _process_submission,
    _process_comment,
)
from .parse import SearchQuery, SearchQueryType


class TestGetStartTime:
    def test_with_existing_comment(self):
        mock_reddit = MagicMock()
        mock_me = MagicMock()
        mock_reddit.user.me.return_value = mock_me
        mock_me.name = "TestBot"

        mock_parent = MagicMock()
        mock_parent.created_utc = 1700000000.0
        mock_comment = MagicMock()
        mock_comment.parent.return_value = mock_parent
        mock_me.comments.new.return_value = iter([mock_comment])

        result = _get_start_time(mock_reddit)

        assert result == 1700000000.0
        mock_reddit.user.me.assert_called_once()
        mock_me.comments.new.assert_called_once_with(limit=1)

    def test_without_comments(self):
        mock_reddit = MagicMock()
        mock_me = MagicMock()
        mock_reddit.user.me.return_value = mock_me
        mock_me.name = "TestBot"
        mock_me.comments.new.return_value = iter([])

        with patch("crombird_reddit.bot.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value.timestamp.return_value = (
                1700000000.0
            )
            mock_datetime.datetime.fromtimestamp.return_value = (
                datetime.datetime.fromtimestamp(1700000000.0, datetime.UTC)
            )
            result = _get_start_time(mock_reddit)

        assert result == 1700000000.0


class TestCreateStreams:
    def test_creates_three_streams(self):
        mock_reddit = MagicMock()
        mock_submission_multi = MagicMock()
        mock_comment_multi = MagicMock()
        mock_reddit.subreddit.side_effect = [mock_submission_multi, mock_comment_multi]

        submission_stream = MagicMock()
        comment_stream = MagicMock()
        mock_submission_multi.stream.submissions.return_value = submission_stream
        mock_comment_multi.stream.comments.return_value = comment_stream

        with patch("crombird_reddit.bot.stream_generator") as mock_stream_gen:
            mention_stream = MagicMock()
            mock_stream_gen.return_value = mention_stream

            result = _create_streams(mock_reddit, ["sub1", "sub2"], ["comment_sub"])

        assert result == (submission_stream, comment_stream, mention_stream)
        mock_reddit.subreddit.assert_any_call("sub1+sub2")
        mock_reddit.subreddit.assert_any_call("comment_sub")
        mock_submission_multi.stream.submissions.assert_called_once_with(pause_after=1)
        mock_comment_multi.stream.comments.assert_called_once_with(pause_after=1)


class TestCheckRevisitSubmissions:
    def test_returns_edited_submissions(self):
        mock_reddit = MagicMock()

        # Create a submission that was made 3 minutes ago (should be checked)
        old_submission = MagicMock()
        old_submission.id = "abc123"
        old_submission.created_utc = (
            datetime.datetime.now() - timedelta(minutes=3)
        ).timestamp()
        old_submission.selftext = "Original text with SCP-173"
        old_submission.permalink = "/r/test/comments/abc123"

        old_reply = MagicMock()
        search_queries = [
            SearchQuery(
                SearchQueryType.FREEFORM, "SCP-173", "http://scp-wiki.wikidot.com"
            )
        ]

        # Updated submission has different text
        updated_submission = MagicMock()
        updated_submission.author = MagicMock()
        updated_submission.removed_by_category = None
        updated_submission.selftext = "Updated text with SCP-999"
        mock_reddit.submission.return_value = updated_submission

        replied_text_submissions = {
            "abc123": (old_submission, search_queries, old_reply)
        }

        result = _check_revisit_submissions(mock_reddit, replied_text_submissions)

        assert len(result) == 1
        assert result[0][0] == updated_submission
        assert result[0][1] == search_queries
        assert result[0][2] == old_reply
        assert "abc123" not in replied_text_submissions

    def test_deletes_reply_for_removed_submission(self):
        mock_reddit = MagicMock()

        old_submission = MagicMock()
        old_submission.id = "abc123"
        old_submission.created_utc = (
            datetime.datetime.now() - timedelta(minutes=3)
        ).timestamp()
        old_submission.permalink = "/r/test/comments/abc123"

        old_reply = MagicMock()

        # Updated submission was removed
        updated_submission = MagicMock()
        updated_submission.author = None
        mock_reddit.submission.return_value = updated_submission

        replied_text_submissions = {"abc123": (old_submission, [], old_reply)}

        result = _check_revisit_submissions(mock_reddit, replied_text_submissions)

        assert len(result) == 0
        old_reply.delete.assert_called_once()
        assert "abc123" not in replied_text_submissions

    def test_ignores_recent_submissions(self):
        mock_reddit = MagicMock()

        # Create a submission that was made 1 minute ago (should not be checked)
        recent_submission = MagicMock()
        recent_submission.id = "abc123"
        recent_submission.created_utc = (
            datetime.datetime.now() - timedelta(minutes=1)
        ).timestamp()

        replied_text_submissions = {"abc123": (recent_submission, [], MagicMock())}

        result = _check_revisit_submissions(mock_reddit, replied_text_submissions)

        assert len(result) == 0
        assert "abc123" in replied_text_submissions
        mock_reddit.submission.assert_not_called()


class TestCheckRevisitComments:
    def test_returns_edited_comments(self):
        mock_reddit = MagicMock()

        old_comment = MagicMock()
        old_comment.id = "xyz789"
        old_comment.created_utc = (
            datetime.datetime.now() - timedelta(minutes=3)
        ).timestamp()
        old_comment.body = "Original comment with [[SCP-173]]"
        old_comment.permalink = "/r/test/comments/abc123/comment/xyz789"

        old_reply = MagicMock()
        search_queries = [
            SearchQuery(
                SearchQueryType.FREEFORM, "SCP-173", "http://scp-wiki.wikidot.com"
            )
        ]

        updated_comment = MagicMock()
        updated_comment.author = MagicMock()
        updated_comment.banned_by = None
        updated_comment.body = "Edited comment with [[SCP-999]]"
        mock_reddit.comment.return_value = updated_comment

        replied_comments = {"xyz789": (old_comment, search_queries, old_reply)}

        result = _check_revisit_comments(mock_reddit, replied_comments)

        assert len(result) == 1
        assert result[0][0] == updated_comment
        assert "xyz789" not in replied_comments

    def test_deletes_reply_for_banned_author(self):
        mock_reddit = MagicMock()

        old_comment = MagicMock()
        old_comment.id = "xyz789"
        old_comment.created_utc = (
            datetime.datetime.now() - timedelta(minutes=3)
        ).timestamp()

        old_reply = MagicMock()

        updated_comment = MagicMock()
        updated_comment.author = MagicMock()
        updated_comment.banned_by = "ModeratorName"
        mock_reddit.comment.return_value = updated_comment

        replied_comments = {"xyz789": (old_comment, [], old_reply)}

        result = _check_revisit_comments(mock_reddit, replied_comments)

        assert len(result) == 0
        old_reply.delete.assert_called_once()


class TestProcessSubmission:
    @patch("crombird_reddit.bot.search")
    @patch("crombird_reddit.bot.generate_response")
    @patch("crombird_reddit.bot._log_request")
    @patch("crombird_reddit.bot._log_response")
    @patch("crombird_reddit.bot.responses_counter")
    def test_processes_wiki_url_submission(
        self, mock_counter, mock_log_resp, mock_log_req, mock_gen_resp, mock_search
    ):
        submission = MagicMock()
        submission.url = "http://scp-wiki.wikidot.com/scp-173"
        submission.is_self = False
        submission.title = "Check out this SCP"
        submission.id = "abc123"
        submission.permalink = "/r/test/comments/abc123"
        submission.subreddit.display_name = "SCP"
        submission.comments = []
        submission.created_utc = 1700000000.0

        mock_reply = MagicMock()
        mock_reply.permalink = "/r/test/comments/abc123/comment/reply1"
        submission.reply.return_value = mock_reply

        mock_search.return_value = [{"name": "SCP-173"}]
        mock_gen_resp.return_value = "Here is info about SCP-173"

        replied_text_submissions = {}

        result = _process_submission(
            submission=submission,
            start_time=submission.created_utc - 1,
            valid_netlocs=["scp-wiki.wikidot.com"],
            previous_search_queries=None,
            previous_reply=None,
            replied_text_submissions=replied_text_submissions,
        )

        assert result is True
        assert "abc123" in replied_text_submissions
        submission.reply.assert_called_once_with("Here is info about SCP-173")
        mock_counter.labels.assert_called_with(type="submission", subreddit="SCP")

    @patch("crombird_reddit.bot.search")
    @patch("crombird_reddit.bot.generate_response")
    @patch("crombird_reddit.bot._log_request")
    @patch("crombird_reddit.bot._log_response")
    @patch("crombird_reddit.bot.responses_counter")
    def test_ignores_old_submissions(
        self, mock_counter, mock_log_resp, mock_log_req, mock_gen_resp, mock_search
    ):
        submission = MagicMock()
        submission.created_utc = 1700000000.0
        submission.url = "http://scp-wiki.wikidot.com/scp-173"
        submission.is_self = False
        submission.title = "Check out this SCP"
        submission.id = "abc123"
        submission.permalink = "/r/test/comments/abc123"
        submission.subreddit.display_name = "SCP"
        submission.comments = []

        replied_text_submissions = {}

        result = _process_submission(
            submission=submission,
            start_time=submission.created_utc + 1,
            valid_netlocs=["scp-wiki.wikidot.com"],
            previous_search_queries=None,
            previous_reply=None,
            replied_text_submissions=replied_text_submissions,
        )

        assert result is False

    @patch("crombird_reddit.bot.search")
    def test_returns_false_when_no_search_results(self, mock_search):
        submission = MagicMock()
        submission.url = "http://example.com"
        submission.is_self = True
        submission.title = "Check out SCP-173"
        submission.selftext = ""
        submission.permalink = "/r/test/comments/abc123"
        submission.created_utc = 1700000000.0
        mock_search.return_value = []

        result = _process_submission(
            submission=submission,
            start_time=submission.created_utc - 1,
            valid_netlocs=["scp-wiki.wikidot.com"],
            previous_search_queries=None,
            previous_reply=None,
            replied_text_submissions={},
        )

        assert result is False

    def test_returns_false_when_no_queries(self):
        submission = MagicMock()
        submission.url = "http://example.com"
        submission.is_self = True
        submission.title = "Just a regular post"
        submission.selftext = "No SCP mentions here"
        submission.created_utc = 1700000000.0
        result = _process_submission(
            submission=submission,
            start_time=submission.created_utc - 1,
            valid_netlocs=["scp-wiki.wikidot.com"],
            previous_search_queries=None,
            previous_reply=None,
            replied_text_submissions={},
        )

        assert result is False


class TestProcessComment:
    @patch("crombird_reddit.bot.search")
    @patch("crombird_reddit.bot.generate_response")
    @patch("crombird_reddit.bot._log_request")
    @patch("crombird_reddit.bot._log_response")
    @patch("crombird_reddit.bot.responses_counter")
    def test_processes_comment_with_scp_mention(
        self, mock_counter, mock_log_resp, mock_log_req, mock_gen_resp, mock_search
    ):
        comment = MagicMock()
        comment.body = "Check out [[SCP-173]]"
        comment.id = "xyz789"
        comment.permalink = "/r/test/comments/abc123/comment/xyz789"
        comment.context = "/r/test/comments/abc123/comment/xyz789?context=3"
        comment.subreddit.display_name = "SCP"
        comment.created_utc = 1700000000.0
        comment.author.name = "regular_user"
        comment.banned_by = None

        mock_reply = MagicMock()
        mock_reply.permalink = "/r/test/comments/abc123/comment/reply1"
        comment.reply.return_value = mock_reply

        mock_search.return_value = [{"name": "SCP-173"}]
        mock_gen_resp.return_value = "Here is info about SCP-173"

        replied_comments = {}

        result = _process_comment(
            comment=comment,
            start_time=comment.created_utc - 1,
            bot_accounts=["somebot"],
            previous_search_queries=None,
            previous_reply=None,
            replied_comments=replied_comments,
            comment_type="comment",
        )

        assert result is True
        assert "xyz789" in replied_comments
        comment.reply.assert_called_once_with("Here is info about SCP-173")
        mock_counter.labels.assert_called_with(type="comment", subreddit="SCP")

    @patch("crombird_reddit.bot.search")
    @patch("crombird_reddit.bot.generate_response")
    @patch("crombird_reddit.bot._log_request")
    @patch("crombird_reddit.bot._log_response")
    @patch("crombird_reddit.bot.responses_counter")
    def test_processes_mention_with_different_comment_type(
        self, mock_counter, mock_log_resp, mock_log_req, mock_gen_resp, mock_search
    ):
        comment = MagicMock()
        comment.body = "Hey @crombot check out [[SCP-999]]"
        comment.id = "mention123"
        comment.permalink = "/r/other/comments/def456/comment/mention123"
        comment.context = "/r/other/comments/def456/comment/mention123?context=3"
        comment.subreddit.display_name = "other"
        comment.created_utc = 1700000000.0
        comment.author.name = "regular_user"

        mock_reply = MagicMock()
        mock_reply.permalink = "/r/other/comments/def456/comment/reply1"
        comment.reply.return_value = mock_reply

        mock_search.return_value = [{"name": "SCP-999"}]
        mock_gen_resp.return_value = "Here is info about SCP-999"

        replied_comments = {}

        result = _process_comment(
            comment=comment,
            start_time=comment.created_utc - 1,
            bot_accounts=["somebot"],
            previous_search_queries=None,
            previous_reply=None,
            replied_comments=replied_comments,
            comment_type="mention",
        )

        assert result is True
        mock_log_req.assert_called_once()
        # Check that "Mention" was used, not "Comment"
        assert mock_log_req.call_args[0][0] == "Mention"
        mock_counter.labels.assert_called_with(type="mention", subreddit="other")

    @patch("crombird_reddit.bot.search")
    @patch("crombird_reddit.bot.generate_response")
    @patch("crombird_reddit.bot._log_request")
    @patch("crombird_reddit.bot._log_response")
    @patch("crombird_reddit.bot.responses_counter")
    def test_edits_existing_reply_when_content_changed(
        self, mock_counter, mock_log_resp, mock_log_req, mock_gen_resp, mock_search
    ):
        comment = MagicMock()
        comment.body = "Check out [[SCP-999]]"  # Changed from SCP-173
        comment.id = "xyz789"
        comment.permalink = "/r/test/comments/abc123/comment/xyz789"
        comment.subreddit.display_name = "SCP"
        comment.created_utc = 1700000000.0
        comment.author.name = "regular_user"
        comment.banned_by = None

        previous_reply = MagicMock()
        previous_reply.body = "Here is info about SCP-173"
        previous_reply.permalink = "/r/test/comments/abc123/comment/reply1"

        previous_queries = [
            SearchQuery(
                SearchQueryType.FREEFORM, "SCP-173", "http://scp-wiki.wikidot.com"
            )
        ]

        mock_search.return_value = [{"name": "SCP-999"}]
        mock_gen_resp.return_value = "Here is info about SCP-999"

        replied_comments = {}

        result = _process_comment(
            comment=comment,
            start_time=comment.created_utc - 1,
            bot_accounts=["somebot"],
            previous_search_queries=previous_queries,
            previous_reply=previous_reply,
            replied_comments=replied_comments,
            comment_type="comment",
        )

        assert result is True
        previous_reply.edit.assert_called_once_with("Here is info about SCP-999")
        comment.reply.assert_not_called()

    def test_returns_false_when_no_queries(self):
        comment = MagicMock()
        comment.body = "Just a regular comment"
        comment.created_utc = 1700000000.0
        comment.author.name = "regular_user"
        comment.banned_by = None

        result = _process_comment(
            comment=comment,
            start_time=comment.created_utc - 1,
            bot_accounts=["somebot"],
            previous_search_queries=None,
            previous_reply=None,
            replied_comments={},
            comment_type="comment",
        )

        assert result is False

    def test_returns_false_when_queries_unchanged(self):
        comment = MagicMock()
        comment.body = "Check out [[SCP-173]]"
        comment.created_utc = 1700000000.0
        comment.author.name = "regular_user"
        comment.banned_by = None

        previous_queries = [
            SearchQuery(
                SearchQueryType.FREEFORM, "SCP-173", "http://scp-wiki.wikidot.com"
            )
        ]

        result = _process_comment(
            comment=comment,
            start_time=comment.created_utc - 1,
            bot_accounts=["somebot"],
            previous_search_queries=previous_queries,
            previous_reply=MagicMock(),
            replied_comments={},
            comment_type="comment",
        )

        assert result is False

    def test_ignores_old_comments(self):
        comment = MagicMock()
        comment.body = "Check out [[SCP-173]]"
        comment.created_utc = 1700000000.0
        comment.author.name = "regular_user"
        comment.banned_by = None

        result = _process_comment(
            comment=comment,
            start_time=comment.created_utc + 1,  # start_time is after comment
            bot_accounts=["somebot"],
            previous_search_queries=None,
            previous_reply=None,
            replied_comments={},
            comment_type="comment",
        )

        assert result is False

    def test_ignores_deleted_comments(self):
        comment = MagicMock()
        comment.body = "Check out [[SCP-173]]"
        comment.created_utc = 1700000000.0
        comment.author = None  # Deleted author

        result = _process_comment(
            comment=comment,
            start_time=comment.created_utc - 1,
            bot_accounts=["somebot"],
            previous_search_queries=None,
            previous_reply=None,
            replied_comments={},
            comment_type="comment",
        )

        assert result is False

    def test_ignores_bot_accounts(self):
        comment = MagicMock()
        comment.body = "Check out [[SCP-173]]"
        comment.created_utc = 1700000000.0
        comment.author.name = "SomeBot"  # Matches bot_accounts (case insensitive)
        comment.banned_by = None

        result = _process_comment(
            comment=comment,
            start_time=comment.created_utc - 1,
            bot_accounts=["somebot"],  # lowercase
            previous_search_queries=None,
            previous_reply=None,
            replied_comments={},
            comment_type="comment",
        )

        assert result is False

    def test_ignores_banned_comments(self):
        comment = MagicMock()
        comment.body = "Check out [[SCP-173]]"
        comment.created_utc = 1700000000.0
        comment.author.name = "regular_user"
        comment.banned_by = "ModeratorName"  # Comment author is banned

        result = _process_comment(
            comment=comment,
            start_time=comment.created_utc - 1,
            bot_accounts=["somebot"],
            previous_search_queries=None,
            previous_reply=None,
            replied_comments={},
            comment_type="comment",
        )

        assert result is False

    def test_ignores_mentions_in_monitored_subreddits(self):
        comment = MagicMock()
        comment.body = "Hey @crombot check out [[SCP-173]]"
        comment.created_utc = 1700000000.0
        comment.author.name = "regular_user"
        comment.subreddit.display_name = "SCP"  # In monitored subreddits

        result = _process_comment(
            comment=comment,
            start_time=comment.created_utc - 1,
            bot_accounts=["somebot"],
            previous_search_queries=None,
            previous_reply=None,
            replied_comments={},
            comment_type="mention",
            comment_subreddits=["scp"],  # lowercase, should match case-insensitively
        )

        assert result is False
