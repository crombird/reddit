import os
import logging

import praw
from prometheus_client import start_http_server
from crombird_reddit.bot import start_bot

# Prometheus metrics port.
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9091"))

# Subreddits enrolled in the "articles mentioned in this submission" feature.
SUBMISSION_SUBREDDITS = [
    "dankmemesfromsite19",
    "scp",
    "tale",
]

# Subreddits enrolled for comment replies.
COMMENT_SUBREDDITS = [
    "dankmemesfromsite19",
    "nuscp",
    "okbubbyredacted",
    "okbuddyredacted",
    "scp",
    "scp682",
    "scpart",
    "scpbertstrips",
    "scpcontainmentbreach",
    "scpeuclid",
    "scpostcrusaders",
    "tale",
]

# Reddit users that the bot will not reply to.
BOT_ACCOUNTS = [
    "automoderator",
    "magic_eye_bot",
    "maximagebot",
    "repostsleuthbot",
    "sneakpeekbot",
    "the-noided-android",
    "the-paranoid-android",
]

# Domains that trigger a URL lookup for submissions.
VALID_NETLOCS = [
    "fondationscp.wikidot.com",
    "fondazionescp.wikidot.com",
    "lafundacionscp.wikidot.com",
    "scp-cs.wikidot.com",
    "scp-el.wikidot.com",
    "scp-id.wikidot.com",
    "scp-int.wikidot.com",
    "scp-jp.wikidot.com",
    "scp-pl.wikidot.com",
    "scp-pt-br.wikidot.com",
    "scp-ru.wikidot.com",
    "scp-th.wikidot.com",
    "scp-ukrainian.wikidot.com",
    "scp-vn.wikidot.com",
    "scp-wiki-cn.wikidot.com",
    "scp-wiki-de.wikidot.com",
    "scp-wiki.wikidot.com",
    "scp-zh-tr.wikidot.com",
    "scpko.wikidot.com",
    "wanderers-library-cs.wikidot.com",
    "wanderers-library-jp.wikidot.com",
    "wanderers-library-ko.wikidot.com",
    "wanderers-library-pl.wikidot.com",
    "wanderers-library-vn.wikidot.com",
    "wanderers-library.wikidot.com",
]

if __name__ == "__main__":
    # The default logging level is WARNING, so we set it to INFO.
    logging.getLogger().setLevel(logging.INFO)

    # Start the Prometheus metrics server.
    # Metrics are automatically collected by Fly.io.
    start_http_server(METRICS_PORT)

    # Initialize the Reddit API client.
    # PRAW is configured using environment variables (praw_*)
    # https://praw.readthedocs.io/en/stable/getting_started/configuration/environment_variables.html
    reddit = praw.Reddit(user_agent="Crom, by u/SoManyLostThrowaways")

    start_bot(
        reddit=reddit,
        submission_subreddits=SUBMISSION_SUBREDDITS,
        comment_subreddits=COMMENT_SUBREDDITS,
        bot_accounts=BOT_ACCOUNTS,
        valid_netlocs=VALID_NETLOCS,
    )
