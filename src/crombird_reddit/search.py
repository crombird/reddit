import re

from .parse import SearchQuery, SearchQueryType
from .utils.crom_client import CromClient

_WIKIDOT_PAGE_INFO_FRAGMENT = """
fragment WikidotPageInfo on WikidotPage {
  __typename
  url
  title
  rating
  createdAt
  alternateTitles {
    title
  }
  attributions {
    type
    user {
      displayName
    }
  }
}
"""

_USER_INFO_FRAGMENT = """
fragment UserInfo on User {
  __typename
  displayName
  statistics(siteUrl: $siteUrl) {
    rank
    totalRating
    meanRating
    pageCount
  }
  ... on WikidotUser {
    userPage(siteUrl: $siteUrl) {
      url
    }
  }
  ... on UserWikidotNameReference {
    userPage(siteUrl: $siteUrl) {
      url
    }
  }
}
"""

_PAGE_BY_URL_QUERY = _WIKIDOT_PAGE_INFO_FRAGMENT + (
    """
query PageByUrl($pageUrl: URL!) {
  wikidotPage(url: $pageUrl) {
    ...WikidotPageInfo
  }
  matchingPages(url: $pageUrl) {
    __typename
    ...on WikidotPage {
      ...WikidotPageInfo
    }
  }
}
"""
)


_PAGE_BY_FREEFORM_TEXT_QUERY = _USER_INFO_FRAGMENT + (
    """
query PageByFreeformText($text: String!, $siteUrl: URL!) {
  searchPages_v1(query: $text, siteUrl: $siteUrl) {
    url
  }
  searchUsers_v1(query: $text, siteUrl: $siteUrl) {
    ...UserInfo
  }
}
"""
)

_crom_client = CromClient()


def search(search_queries: list[SearchQuery]) -> list[dict]:
    responses = []
    for group in _chunks(search_queries, 25):
        gql_queries = []
        for i, search_query in enumerate(group):
            if search_query.type == SearchQueryType.URL:
                gql_queries.append(
                    {
                        "query": _PAGE_BY_URL_QUERY,
                        "variables": {"url": search_query.value.lower()},
                    }
                )
            elif search_query.type == SearchQueryType.BARE:
                url_segment = re.sub(" ", "-", search_query.value.lower())
                gql_queries.append(
                    {
                        "query": _PAGE_BY_URL_QUERY,
                        "variables": {
                            "url": f"{search_query.site_url}/scp-{url_segment}"
                        },
                    }
                )
            elif search_query.type == SearchQueryType.FREEFORM:
                gql_queries.append(
                    {
                        "query": _PAGE_BY_FREEFORM_TEXT_QUERY,
                        "variables": {
                            "text": search_query.value.lower(),
                            "siteUrl": search_query.site_url,
                        },
                    }
                )
        responses.extend(_crom_client.query_batch(gql_queries))

    results: list[dict] = []
    for i, response in enumerate(responses):
        wikidot_page = response.get("wikidotPage", None)
        matching_pages = response.get("matchingPages", None)

        search_pages = response.get("searchPages_v1", None)
        search_users = response.get("searchUsers_v1", None)

        if search_users and (
            search_users[0]["displayName"].lower() == search_queries[i].value.lower()
        ):
            results.append({"user": search_users[0]})
        elif wikidot_page:
            results.append(
                {"wikidot_page": wikidot_page, "matching_pages": matching_pages}
            )
        elif search_pages:
            full_page = _crom_client.query(
                {
                    "query": _PAGE_BY_URL_QUERY,
                    "variables": {"pageUrl": search_pages[0]["url"]},
                }
            )
            results.append(
                {
                    "wikidot_page": full_page["wikidotPage"],
                    "matching_pages": full_page["matchingPages"],
                }
            )

    return list(
        _uniq_by(
            results,
            lambda x: (
                x["wikidot_page"]["url"]
                if "wikidot_page" in x and x["wikidot_page"] is not None
                else x["user"]["displayName"]
            ),
        )
    )


def _chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _uniq_by(items, mapper):
    """
    Remove duplicates from a list based on a mapping function.
    Also, the order is preserved.
    """
    tracking = set()
    for item in items:
        key = mapper(item)
        if key not in tracking:
            tracking.add(key)
            yield item
