from unittest.mock import patch

from .parse import SearchQuery, SearchQueryType
from .search import search, _chunks, _uniq_by


class TestChunks:
    def test_empty_list(self):
        result = list(_chunks([], 5))
        assert result == []

    def test_list_smaller_than_chunk_size(self):
        result = list(_chunks([1, 2, 3], 5))
        assert result == [[1, 2, 3]]

    def test_list_equal_to_chunk_size(self):
        result = list(_chunks([1, 2, 3, 4, 5], 5))
        assert result == [[1, 2, 3, 4, 5]]

    def test_list_larger_than_chunk_size(self):
        result = list(_chunks([1, 2, 3, 4, 5, 6, 7], 3))
        assert result == [[1, 2, 3], [4, 5, 6], [7]]

    def test_chunk_size_one(self):
        result = list(_chunks([1, 2, 3], 1))
        assert result == [[1], [2], [3]]


class TestUniqBy:
    def test_empty_list(self):
        result = list(_uniq_by([], lambda x: x))
        assert result == []

    def test_no_duplicates(self):
        result = list(_uniq_by([1, 2, 3], lambda x: x))
        assert result == [1, 2, 3]

    def test_with_duplicates(self):
        result = list(_uniq_by([1, 2, 2, 3, 1], lambda x: x))
        assert result == [1, 2, 3]

    def test_preserves_order(self):
        result = list(_uniq_by([3, 1, 2, 1, 3], lambda x: x))
        assert result == [3, 1, 2]

    def test_with_mapper_function(self):
        items = [{"name": "alice"}, {"name": "bob"}, {"name": "Alice"}]
        result = list(_uniq_by(items, lambda x: x["name"].lower()))
        assert result == [{"name": "alice"}, {"name": "bob"}]

    def test_keeps_first_occurrence(self):
        items = [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}, {"id": 1, "val": "c"}]
        result = list(_uniq_by(items, lambda x: x["id"]))
        assert result == [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]


class TestSearchWithURLQuery:
    @patch("crombird_reddit.search._crom_client")
    def test_url_query_returns_page_result(self, mock_client):
        mock_client.query_batch.return_value = [
            {
                "wikidotPage": {
                    "url": "http://scp-wiki.wikidot.com/scp-173",
                    "title": "SCP-173",
                    "rating": 100,
                },
                "matchingPages": [],
            }
        ]

        queries = [
            SearchQuery(
                type=SearchQueryType.URL,
                value="http://scp-wiki.wikidot.com/scp-173",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]
        result = search(queries)

        assert len(result) == 1
        assert result[0]["wikidot_page"]["url"] == "http://scp-wiki.wikidot.com/scp-173"
        assert result[0]["matching_pages"] == []


class TestSearchWithBareQuery:
    @patch("crombird_reddit.search._crom_client")
    def test_bare_query_constructs_scp_url(self, mock_client):
        mock_client.query_batch.return_value = [
            {
                "wikidotPage": {
                    "url": "http://scp-wiki.wikidot.com/scp-173",
                    "title": "SCP-173",
                    "rating": 100,
                },
                "matchingPages": [],
            }
        ]

        queries = [
            SearchQuery(
                type=SearchQueryType.BARE,
                value="173",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]
        search(queries)

        # Verify the query was constructed with the SCP URL pattern
        call_args = mock_client.query_batch.call_args[0][0]
        assert call_args[0]["variables"]["url"] == "http://scp-wiki.wikidot.com/scp-173"

    @patch("crombird_reddit.search._crom_client")
    def test_bare_query_with_spaces_replaced_by_hyphens(self, mock_client):
        mock_client.query_batch.return_value = [
            {
                "wikidotPage": {
                    "url": "http://scp-wiki.wikidot.com/scp-173-j",
                    "title": "SCP-173-J",
                    "rating": 50,
                },
                "matchingPages": [],
            }
        ]

        queries = [
            SearchQuery(
                type=SearchQueryType.BARE,
                value="173 J",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]
        search(queries)

        call_args = mock_client.query_batch.call_args[0][0]
        assert (
            call_args[0]["variables"]["url"] == "http://scp-wiki.wikidot.com/scp-173-j"
        )


class TestSearchWithFreeformQuery:
    @patch("crombird_reddit.search._crom_client")
    def test_freeform_query_returns_user_when_exact_match(self, mock_client):
        mock_client.query_batch.return_value = [
            {
                "searchPages_v1": [],
                "searchUsers_v1": [
                    {
                        "displayName": "djkaktus",
                        "statistics": {"rank": 1, "totalRating": 10000},
                    }
                ],
            }
        ]

        queries = [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="djkaktus",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]
        result = search(queries)

        assert len(result) == 1
        assert "user" in result[0]
        assert result[0]["user"]["displayName"] == "djkaktus"

    @patch("crombird_reddit.search._crom_client")
    def test_freeform_query_returns_page_from_search_results(self, mock_client):
        mock_client.query_batch.return_value = [
            {
                "searchPages_v1": [{"url": "http://scp-wiki.wikidot.com/scp-173"}],
                "searchUsers_v1": [],
            }
        ]
        mock_client.query.return_value = {
            "wikidotPage": {
                "url": "http://scp-wiki.wikidot.com/scp-173",
                "title": "SCP-173",
                "rating": 100,
            },
            "matchingPages": [],
        }

        queries = [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="SCP-173",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]
        result = search(queries)

        assert len(result) == 1
        assert "wikidot_page" in result[0]
        assert result[0]["wikidot_page"]["title"] == "SCP-173"

    @patch("crombird_reddit.search._crom_client")
    def test_freeform_user_match_case_insensitive(self, mock_client):
        mock_client.query_batch.return_value = [
            {
                "searchPages_v1": [],
                "searchUsers_v1": [
                    {
                        "displayName": "DjKaktus",
                        "statistics": {"rank": 1, "totalRating": 10000},
                    }
                ],
            }
        ]

        queries = [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="djkaktus",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]
        result = search(queries)

        assert len(result) == 1
        assert "user" in result[0]


class TestSearchDeduplication:
    @patch("crombird_reddit.search._crom_client")
    def test_duplicate_page_results_are_removed(self, mock_client):
        mock_client.query_batch.return_value = [
            {
                "wikidotPage": {
                    "url": "http://scp-wiki.wikidot.com/scp-173",
                    "title": "SCP-173",
                    "rating": 100,
                },
                "matchingPages": [],
            },
            {
                "wikidotPage": {
                    "url": "http://scp-wiki.wikidot.com/scp-173",
                    "title": "SCP-173",
                    "rating": 100,
                },
                "matchingPages": [],
            },
        ]

        queries = [
            SearchQuery(
                type=SearchQueryType.URL,
                value="http://scp-wiki.wikidot.com/scp-173",
                site_url="http://scp-wiki.wikidot.com",
            ),
            SearchQuery(
                type=SearchQueryType.URL,
                value="http://scp-wiki.wikidot.com/scp-173",
                site_url="http://scp-wiki.wikidot.com",
            ),
        ]
        result = search(queries)

        assert len(result) == 1

    @patch("crombird_reddit.search._crom_client")
    def test_duplicate_user_results_are_removed(self, mock_client):
        mock_client.query_batch.return_value = [
            {
                "searchPages_v1": [],
                "searchUsers_v1": [
                    {"displayName": "djkaktus", "statistics": {"rank": 1}},
                ],
            },
            {
                "searchPages_v1": [],
                "searchUsers_v1": [
                    {"displayName": "djkaktus", "statistics": {"rank": 1}},
                ],
            },
        ]

        queries = [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="djkaktus",
                site_url="http://scp-wiki.wikidot.com",
            ),
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="djkaktus",
                site_url="http://scp-wiki.wikidot.com",
            ),
        ]
        result = search(queries)

        assert len(result) == 1


class TestSearchBatching:
    @patch("crombird_reddit.search._crom_client")
    def test_queries_batched_in_groups_of_25(self, mock_client):
        mock_client.query_batch.return_value = [
            {
                "wikidotPage": {
                    "url": f"http://scp-wiki.wikidot.com/scp-{i}",
                    "title": f"SCP-{i}",
                    "rating": 100,
                },
                "matchingPages": [],
            }
            for i in range(30)
        ]

        queries = [
            SearchQuery(
                type=SearchQueryType.URL,
                value=f"http://scp-wiki.wikidot.com/scp-{i}",
                site_url="http://scp-wiki.wikidot.com",
            )
            for i in range(30)
        ]
        search(queries)

        # Should be called twice: once with 25 queries, once with 5
        assert mock_client.query_batch.call_count == 2


class TestSearchNoResults:
    @patch("crombird_reddit.search._crom_client")
    def test_empty_response_returns_empty_list(self, mock_client):
        mock_client.query_batch.return_value = [
            {"wikidotPage": None, "matchingPages": []}
        ]

        queries = [
            SearchQuery(
                type=SearchQueryType.URL,
                value="http://scp-wiki.wikidot.com/nonexistent",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]
        result = search(queries)

        assert result == []

    @patch("crombird_reddit.search._crom_client")
    def test_freeform_no_users_no_pages(self, mock_client):
        mock_client.query_batch.return_value = [
            {"searchPages_v1": [], "searchUsers_v1": []}
        ]

        queries = [
            SearchQuery(
                type=SearchQueryType.FREEFORM,
                value="nonexistent",
                site_url="http://scp-wiki.wikidot.com",
            )
        ]
        result = search(queries)

        assert result == []

    @patch("crombird_reddit.search._crom_client")
    def test_empty_query_list(self, mock_client):
        result = search([])
        assert result == []
        mock_client.query_batch.assert_not_called()
