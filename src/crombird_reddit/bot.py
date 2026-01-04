import datetime
import logging
from datetime import timedelta
from typing import Iterator
from urllib.parse import urljoin, urlparse, urlsplit

import praw
import prawcore
from praw.models.util import stream_generator

from .search import search
from .parse import ParseContext, SearchQuery, SearchQueryType, parse
from .response import generate_response
from .utils.metrics import responses_counter

DEFAULT_REVISIT_AGE = timedelta(minutes=2)


def start_bot(
    *,
    reddit: praw.Reddit,
    submission_subreddits: list[str],
    comment_subreddits: list[str],
    bot_accounts: list[str],
    valid_netlocs: list[str],
):
    # To avoid double-posting on redeployments, we only reply to items posted
    # after the last comment the previous instance replied to. (We assume the
    # previous instance ended before this one started.)
    start_time = _get_start_time(reddit)

    # Requesting "latest" comments and submissions will return the same items
    # over and over again. Luckily, PRAW has an internal cache specifically
    # for streaming posts/comments. We create instances up-front and hold on
    # to them to leverage this cache.
    submission_stream, comment_stream, mention_stream = _create_streams(
        reddit, submission_subreddits, comment_subreddits
    )

    # After responding to a post, Crom will put it on a pile to check back
    # two minutes later. If it was stealth-edited in that duration, Crom will
    # re-evaluate and re-respond (unless it was changed to have no SCPs in it).
    # For any edits after that period, people will see an asterisk indicating
    # the item was edited, so it won't seem weird for Crom to be inaccurate.
    replied_text_submissions = dict()
    replied_comments = dict()

    while True:
        # Iterate through the next batch of tracked subreddit submissions.
        for submission in submission_stream:
            # Use the None object provided by pause_after to decide to end
            # this loop.
            if submission is None:
                break

            _process_submission(
                submission=submission,
                start_time=start_time,
                valid_netlocs=valid_netlocs,
                replied_text_submissions=replied_text_submissions,
                previous_search_queries=None,
                previous_reply=None,
            )

        # Iterate through the next batch of tracked subreddit comments.
        for comment in comment_stream:
            # Use the None object provided by pause_after to decide to end
            # this loop.
            if comment is None:
                break

            _process_comment(
                comment=comment,
                comment_type="comment",
                start_time=start_time,
                bot_accounts=bot_accounts,
                replied_comments=replied_comments,
                comment_subreddits=comment_subreddits,
                previous_search_queries=None,
                previous_reply=None,
            )

        # Check for edited text submissions that need re-processing.
        revisit_submissions = _check_revisit_submissions(
            reddit, replied_text_submissions
        )
        for submission, previous_search_queries, previous_reply in revisit_submissions:
            _process_submission(
                submission=submission,
                start_time=start_time,
                valid_netlocs=valid_netlocs,
                replied_text_submissions=replied_text_submissions,
                previous_search_queries=previous_search_queries,
                previous_reply=previous_reply,
            )

        # Check for edited comments that need re-processing.
        revisit_comments = _check_revisit_comments(reddit, replied_comments)
        for comment, previous_search_queries, previous_reply in revisit_comments:
            _process_comment(
                comment=comment,
                comment_type="comment",
                start_time=start_time,
                bot_accounts=bot_accounts,
                replied_comments=replied_comments,
                comment_subreddits=comment_subreddits,
                previous_search_queries=previous_search_queries,
                previous_reply=previous_reply,
            )

        # Scan through the next batch of username mentions outside of tracked
        # subreddits.
        for comment in mention_stream:
            # Use the None object provided by pause_after to decide to end
            # this loop.
            if comment is None:
                break

            _process_comment(
                comment=comment,
                comment_type="mention",
                start_time=start_time,
                bot_accounts=bot_accounts,
                replied_comments=replied_comments,
                comment_subreddits=comment_subreddits,
                previous_search_queries=None,
                previous_reply=None,
            )


def _get_start_time(reddit: praw.Reddit) -> float:
    """
    Get the creation time of the earliest comment or submission we will start
    replying to.
    """
    me = reddit.user.me()
    logging.info(f"Logged in as: u/{me.name}!")

    latest_comment = next(me.comments.new(limit=1), None)
    if latest_comment is not None:
        start_time = latest_comment.parent().created_utc
    else:
        start_time = datetime.datetime.now().timestamp()
    logging.info(
        f"Starting from: {datetime.datetime.fromtimestamp(start_time, datetime.UTC)}"
    )
    return start_time


def _create_streams(
    reddit: praw.Reddit,
    submission_subreddits: list[str],
    comment_subreddits: list[str],
) -> tuple[Iterator, Iterator, Iterator]:
    """
    Create the three PRAW stream instances for submissions, comments, and mentions.
    """
    # pause_after throws out a "None" when it's done sending one type of item
    # so that we can switch to the other kind intelligently.
    submission_multi = reddit.subreddit("+".join(submission_subreddits))
    submission_stream = submission_multi.stream.submissions(pause_after=1)
    comment_multi = reddit.subreddit("+".join(comment_subreddits))
    comment_stream = comment_multi.stream.comments(pause_after=1)
    mention_stream = stream_generator(reddit.inbox.mentions, pause_after=1)
    return submission_stream, comment_stream, mention_stream


def _check_revisit_submissions(
    reddit: praw.Reddit,
    replied_text_submissions: dict,
    revisit_age: timedelta = DEFAULT_REVISIT_AGE,
) -> list[tuple]:
    """
    Check submissions we replied to for edits or deletion.

    Walks through submissions replied to longer than revisit_age ago, checking
    if they were updated since we last looked at them. Removes items from the
    cache and deletes replies for removed/deleted submissions.
    """
    revisit_submissions = []
    cutoff_time = datetime.datetime.now() - revisit_age

    for submission, search_queries, reply in list(replied_text_submissions.values()):
        if datetime.datetime.fromtimestamp(submission.created_utc) < cutoff_time:
            # The wait time has passed, take it off the cache.
            del replied_text_submissions[submission.id]
            updated = reddit.submission(id=submission.id)
            if updated.author is None or updated.removed_by_category is not None:
                # The submission was removed or the author was banned, delete
                # the reply.
                reply.delete()
            elif updated.selftext != submission.selftext:
                # The submission was edited, let the caller know so it can be
                # re-processed.
                logging.info(
                    "Submission updated: https://www.reddit.com%s",
                    submission.permalink,
                )
                revisit_submissions.append((updated, search_queries, reply))

    return revisit_submissions


def _check_revisit_comments(
    reddit: praw.Reddit,
    replied_comments: dict,
    revisit_age: timedelta = DEFAULT_REVISIT_AGE,
) -> list[tuple]:
    """
    Check comments we replied to for edits or deletion.

    Walks through comments replied to longer than revisit_age ago, checking
    if they were updated since we last looked at them. Removes items from the
    cache and deletes replies for removed/banned comments.
    """
    revisit_comments = []
    cutoff_time = datetime.datetime.now() - revisit_age

    for comment, search_queries, reply in list(replied_comments.values()):
        if datetime.datetime.fromtimestamp(comment.created_utc) < cutoff_time:
            # The wait time has passed, take it off the cache.
            del replied_comments[comment.id]
            updated = reddit.comment(id=comment.id)
            if updated.author is None or updated.banned_by is not None:
                # The comment was removed or the author was banned, delete the
                # reply.
                reply.delete()
            elif updated.body != comment.body:
                # The comment was edited, let the caller know so it can be
                # re-processed.
                logging.info(
                    "Comment updated: https://www.reddit.com%s", comment.permalink
                )
                revisit_comments.append((updated, search_queries, reply))

    return revisit_comments


def _process_submission(
    *,
    submission,
    start_time: float,
    valid_netlocs: list[str],
    replied_text_submissions: dict,
    previous_search_queries: list | None,
    previous_reply,
) -> bool:
    """
    Process a single submission - parse, search, and reply.
    """
    # Ignore all submissions handled by the previous instance.
    if submission.created_utc <= start_time:
        return False

    # The Crom API only resolves URLs under the wikidot subdomain, so
    # normalize the URL first to maximise the chances of getting the page back.
    normalized_url = _normalize_permalink(submission.url)

    search_queries = []

    # If a submission links to a page on the SCP wiki, that also
    # warrants a mention under the submission.
    netloc = urlsplit(normalized_url).netloc.lower()
    if not submission.is_self and netloc in valid_netlocs:
        search_queries.append(
            SearchQuery(
                type=SearchQueryType.URL,
                value=_normalize_permalink(submission.url),
                site_url=None,
            )
        )

    # Secondly, parse the submission title for SCP numbers or Crom calls.
    search_queries.extend(
        parse(submission.title, context=ParseContext.SUBMISSION_TITLE)
    )

    # Parse the submission selftext if it's a text post.
    if submission.is_self:
        search_queries.extend(
            parse(submission.selftext, context=ParseContext.SUBMISSION_SELFTEXT)
        )

    if not search_queries or search_queries == previous_search_queries:
        return False

    _log_request("Submission", submission.permalink, search_queries)
    results = search(search_queries)
    if not results:
        return False

    try:
        # Reply to the submission. If the URL points to a wiki article,
        # we don't include the rating, because it's likely a fresh article
        # and the rating is going to be out of date quickly anyway. If there
        # was a previous reply already, edit it.
        reply_text = generate_response(
            results,
            is_submission=True,
            submission_url=normalized_url if not submission.is_self else None,
        )
        if not previous_reply:
            reply = submission.reply(reply_text)
            replied_text_submissions[submission.id] = (
                submission,
                search_queries,
                reply,
            )
        elif previous_reply.body != reply_text:
            previous_reply.edit(reply_text)
            reply = previous_reply
        else:
            return False
        _log_response(reply.permalink)

        # Done, increment the counter!
        responses_counter.labels(
            type="submission",
            subreddit=submission.subreddit.display_name,
        ).inc()

        # Optionally, try to sticky the comment at the top of the submission,
        # but fail safely if the bot isn't a moderator of the subreddit.
        try:
            comments = submission.comments
            # If AutoModerator already made a sticky comment on this submission,
            # don't override it.
            if len(comments) == 0 or not comments[0].stickied:
                reply.mod.distinguish(sticky=True)
        except prawcore.exceptions.Forbidden:
            pass

        return True
    except Exception as err:
        logging.exception(err)
        return False


def _process_comment(
    *,
    comment,
    comment_type: str = "comment",
    start_time: float,
    bot_accounts: list[str],
    comment_subreddits: list[str] | None = None,
    replied_comments: dict,
    previous_search_queries: list | None,
    previous_reply,
) -> bool:
    """
    Process a single comment - parse, search, and reply.
    """
    # Ignore all comments handled by the previous instance.
    if comment.created_utc <= start_time:
        return False

    # Ignore if the comment was quickly deleted/removed.
    if comment.author is None:
        return False

    # Ignore if the comment was made by a bot account.
    if comment.author.name.lower() in bot_accounts:
        return False

    # For regular comments (not mentions), ignore if banned.
    if comment_type == "comment" and comment.banned_by:
        return False

    # For mentions, ignore if the comment is in a subreddit we already monitor.
    # The other handler will take care of it.
    if (
        comment_type == "mention"
        and comment_subreddits
        and comment.subreddit.display_name.lower() in comment_subreddits
    ):
        return False

    search_queries = parse(comment.body, context=ParseContext.COMMENT_BODY)

    if not search_queries or search_queries == previous_search_queries:
        return False

    log_type = "Comment" if comment_type == "comment" else "Mention"
    log_location = comment.permalink if comment_type == "comment" else comment.context
    _log_request(log_type, log_location, search_queries)

    results = search(search_queries)
    if not results:
        return False

    try:
        reply_text = generate_response(results)
        if not previous_reply:
            reply = comment.reply(reply_text)
            replied_comments[comment.id] = (
                comment,
                search_queries,
                reply,
            )
        elif previous_reply.body != reply_text:
            previous_reply.edit(reply_text)
            reply = previous_reply
        else:
            return False
        _log_response(reply.permalink)

        responses_counter.labels(
            type=comment_type,
            subreddit=comment.subreddit.display_name,
        ).inc()

        return True
    except Exception as err:
        logging.exception(err)
        return False


def _normalize_permalink(input: str) -> str:
    """
    Normalize a page URL on reddit to make it more likely to match a page in
    the Crom API.
    """
    # Strip query parameters and force URL to be absolute relative to reddit.com
    clean_url = urljoin("https://www.reddit.com/", urljoin(input, urlparse(input).path))
    return (
        # Replace https: with http: since absolute URLs are stored as HTTP in Crom.
        clean_url.replace("https://", "http://")
        .replace("//scpwiki.com", "//scp-wiki.wikidot.com")
        .replace("//www.scpwiki.com", "//scp-wiki.wikidot.com")
        .replace("//www.scp-wiki.net", "//scp-wiki.wikidot.com")
    )


def _log_request(type: str, permalink: str, search_queries: list[SearchQuery]) -> None:
    formatted_queries = ", ".join(
        [f"{q.type}: {q.value} ({q.site_url})" for q in search_queries]
    )
    logging.info(f"{type}: https://www.reddit.com{permalink}, ({formatted_queries})")


def _log_response(permalink: str) -> None:
    logging.info(f"Replied: https://www.reddit.com{permalink}")
