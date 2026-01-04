import re
import datetime
from urllib.parse import urlparse
import timeago

ATTRIBUTION_ORDER = ["SUBMITTER", "TRANSLATOR", "REWRITE", "AUTHOR", "MAINTAINER"]


def generate_response(
    results: list[dict],
    is_submission: bool = False,
    submission_url: str | None = None,
) -> str:
    if len(results) > 10 and not is_submission:
        return _format_short(results)

    comment = ""

    if is_submission:
        comment += "**Articles mentioned in this submission**\n\n"

    for result in results:
        if "wikidot_page" in result:
            comment += _generate_page_response(
                result["wikidot_page"],
                result.get("matching_pages", []),
                is_submission_url=(result["wikidot_page"]["url"] == submission_url),
                as_list_item=(len(results) > 1),
            )
        elif "user" in result:
            comment += _generate_user_response(
                result["user"], as_list_item=(len(results) > 1)
            )

    return comment


def _format_short(results: list[dict]) -> str:
    parts: list[str] = []

    for result in results:
        if "wikidot_page" in result:
            page_url = result["wikidot_page"]["url"]
            page_title = result["wikidot_page"]["title"]
            parts.append(f"[{page_title}]({_httpsify(page_url)})")

        elif "user" in result:
            username = result["user"]["displayName"]
            user_page_url = result["user"].get("userPage", {}).get("url", None)
            if user_page_url:
                parts.append(f"[*{username}*]({_httpsify(user_page_url)})")
            else:
                parts.append(username)

    return ", ".join(parts) + "."


def _generate_page_response(
    wikidot_page: dict,
    matching_pages: list[dict],
    as_list_item: bool,
    is_submission_url: bool,
    is_translation: bool = False,
):
    comment = ""

    # Define variables
    page_url = wikidot_page["url"]
    page_title = wikidot_page["title"]
    page_rating = wikidot_page["rating"]
    created_at = datetime.datetime.fromisoformat(wikidot_page["createdAt"][:-1])
    alternate_title = next(
        (
            alternate_title["title"]
            for alternate_title in wikidot_page["alternateTitles"]
        ),
        None,
    )
    attributions = sorted(
        wikidot_page["attributions"],
        key=lambda a: ATTRIBUTION_ORDER.index(a["type"]),
    )

    # Format string
    if as_list_item:
        comment += "- "
    comment += f"[**{page_title}"
    if alternate_title and alternate_title != page_title:
        comment += f" ⁠- {alternate_title}"
    comment += f"**]({_httpsify(page_url)})"
    if not is_submission_url:
        comment += f" ({_format_rating(page_rating)})"
    if attributions:
        comment += " "

        if datetime.datetime.now() - created_at < datetime.timedelta(weeks=1):
            formatted = timeago.format(created_at, datetime.datetime.now())
            comment += f"posted {formatted} "

        # dict keys are insertion ordered (python 3.7+)
        uniq_attribution_names = dict()

        if is_translation:
            # If this is a translation on an English wiki and we have
            # attribution metadata, just pick out the translators (the
            # original authors would have been credited in the previous line).
            for attribution in (a for a in attributions if a["type"] == "TRANSLATOR"):
                uniq_attribution_names[attribution["user"]["displayName"]] = None
        if not uniq_attribution_names:
            # Otherwise (or if there's no translators in the metadata), use
            # all the attributions.
            for attribution in attributions:
                uniq_attribution_names[attribution["user"]["displayName"]] = None

        comment += "by *" + ", ".join(uniq_attribution_names.keys()) + "*"

    if (
        urlparse(page_url).netloc != "scp-wiki.wikidot.com"
        and matching_pages is not None
    ):
        english_translation = next(
            (
                translation
                for translation in matching_pages
                if urlparse(translation["url"]).netloc == "scp-wiki.wikidot.com"
            ),
            next(
                (
                    translation
                    for translation in matching_pages
                    if urlparse(translation["url"]).netloc == "scp-int.wikidot.com"
                ),
                None,
            ),
        )
        if english_translation is not None:
            comment += "\n"
            if as_list_item:
                comment += "  - "  # indentation so that it's an inner list
            else:
                comment += "\n"  # start a new paragraph
            comment += "Translated: "
            comment += _generate_page_response(
                wikidot_page=english_translation,
                matching_pages=None,
                as_list_item=False,
                is_submission_url=False,
                is_translation=True,
            )

    comment += "\n"
    return comment


def _generate_user_response(user: dict, as_list_item: bool) -> str:
    comment = ""

    # Define variables
    username = user["displayName"]
    total_rating = user["statistics"]["totalRating"]
    rank = user["statistics"]["rank"]
    mean_rating = user["statistics"]["meanRating"]
    user_page_url = user.get("userPage", {}).get("url", None)
    # Format string
    if as_list_item:
        comment += "- "
    comment += "**"
    if user_page_url:
        comment += f"[{username}]({_httpsify(user_page_url)})"
    else:
        comment += username
    comment += f"** (*ranked #{rank}, total rating: {_format_rating(total_rating)}, mean rating: {_format_rating(mean_rating)})*"

    comment += "\n"
    return comment


def _format_rating(rating: int) -> str:
    if rating >= 0:
        return f"+{rating}"
    return f"{rating}"


def _httpsify(url: str) -> str:
    return re.sub(r"^http://", "https://", url)
