import re
from enum import Enum
from datetime import datetime
from collections import namedtuple

from .utils.sanitize_markdown import sanitize_markdown

ParseContext = Enum("ParseContext", "SUBMISSION_TITLE SUBMISSION_SELFTEXT COMMENT_BODY")
SearchQueryType = Enum("SearchQueryType", "URL FREEFORM BARE")
SearchQuery = namedtuple("SearchQuery", ["type", "value", "site_url"])

# Special regexes that tell the parser to focus on a particular INT wiki.
_INTERNATIONAL_REGEXES = (
    (r"(?i)SCP[- ]?(\d{3,4}[- ]FR)(?!\w)", "http://fondationscp.wikidot.com"),
    # Require a dash for IT because "it" also happens to be an english word.
    (r"(?i)SCP[- ]?(\d{3,4}-?IT)(?!\w)", "http://fondazionescp.wikidot.com"),
    (r"(?i)SCP[- ]?(ES[- ]\d{3,4})(?!\w)", "http://lafundacionscp.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]CS)(?!\w)", "http://scp-cs.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]SK)(?!\w)", "http://scp-cs.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]EL)(?!\w)", "http://scp-el.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]ID)(?!\w)", "http://scp-id.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]INT)(?!\w)", "http://scp-int.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]JP)(?!\w)", "http://scp-jp.wikidot.com"),
    (r"(?i)SCP[- ]?(PL[- ]\d{3,4})(?!\w)", "http://scp-pl.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]PT)(?!\w)", "http://scp-pt-br.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]RU)(?!\w)", "http://scp-ru.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]?TH)(?!\w)", "http://scp-th.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]UA)(?!\w)", "http://scp-ukrainian.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]VN)(?!\w)", "http://scp-vn.wikidot.com"),
    (r"(?i)SCP[- ]?(CN[- ]\d{3,4})(?!\w)", "http://scp-wiki-cn.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]DE)(?!\w)", "http://scp-wiki-de.wikidot.com"),
    (r"(?i)SCP[- ]?(ZH[- ]\d{3,4})(?!\w)", "http://scp-zh-tr.wikidot.com"),
    (r"(?i)SCP[- ]?(\d{3,4}[- ]KO)(?!\w)", "http://scpko.wikidot.com"),
)

# The syntax for matching non-international SCP mentions in comments and
# submissions. This one's treated specially
_BARE_MATCH_REGEX = r"(?i)((?:SCP)[- ]\d{3,4}(?:-[A-Z0-9]+)*)(?!\w)"

# The syntax for "modern" matching (i.e. "[[SCP-049]]")
_MODERN_MATCH_REGEX = r"\[\[([^\]]*?)\]\]"

# April fools feature
_SCP2_MATCH = r"(?:^|[^0-9])(2)(?:[^0-9]|$)"

# A list of regexes for false positives to find and remove before parsing.
# Applies to cautious and Marvin matches. Ordered from highest to lowest
# priority.
_FALSE_POSITIVES = [
    re.compile(r">!(.+?)!<", re.DOTALL),  # Spoiler tags
    r"(?i)(?:http|https)://[^ ]*",  # URLs
    r"(?i)\d+[.,]\d+",  # Decimal points
    r"(?i)/?u/[A-Z0-9_-]+",  # Username mentions
]


def parse(text: str, context: ParseContext) -> list[SearchQuery]:
    remaining_text = text
    queries = []

    # Clean up false positives using hints from markdown parsing.
    if context != ParseContext.SUBMISSION_TITLE:
        # Remove all links and code-blocks by parsing the mardown.
        remaining_text = sanitize_markdown(text)

    # Match [[...]] (the modern match syntax) everywhere.
    queries.extend(
        [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value=match.group(1),
                site_url=next(
                    (
                        site_url
                        for regexp, site_url in _INTERNATIONAL_REGEXES
                        if re.fullmatch(regexp, match.group(1))
                    ),
                    "http://scp-wiki.wikidot.com",
                ),
            )
            for match in re.finditer(_MODERN_MATCH_REGEX, remaining_text)
            if re.sub(r"\s", "", match.group(1))
        ]
    )
    remaining_text = re.sub(_MODERN_MATCH_REGEX, "", remaining_text)

    # Remove false positives. We do this after matching modern match syntax because
    # the modern match is very explicit as a command for Crom.
    for false_positive in _FALSE_POSITIVES:
        remaining_text = re.sub(false_positive, "", remaining_text)

    # Match international regexes by branch.
    for regexp, site_url in _INTERNATIONAL_REGEXES:
        matches = re.findall(regexp, remaining_text)
        if matches:
            queries.extend(
                [
                    SearchQuery(
                        type=SearchQueryType.BARE,
                        value=match.group(1),
                        site_url=site_url,
                    )
                    for match in re.finditer(regexp, remaining_text)
                ]
            )
            remaining_text = re.sub(regexp, "", remaining_text)

    # Match bare non-international mentions in text.
    # We do this as a separate step because -EN matches use a much more lenient regex.
    queries.extend(
        [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value=match.group(1),
                site_url="http://scp-wiki.wikidot.com",
            )
            for match in re.finditer(_BARE_MATCH_REGEX, remaining_text)
        ]
    )

    if context == ParseContext.COMMENT_BODY:
        # For april fools
        # https://www.reddit.com/r/SCP/comments/61u0mv/marvin_and_scp2/
        today = datetime.today()
        if today.day == 1 and today.month == 4:
            if re.search(_SCP2_MATCH, remaining_text):
                queries.append(
                    SearchQuery(
                        type=SearchQueryType.BARE,
                        value="2",
                        site_url="http://scp-wiki.wikidot.com",
                    )
                )

    return queries
