from unittest.mock import MagicMock, patch

import pytest
from oauthlib.oauth2 import TokenExpiredError

from .crom_client import CromClient, CromAPIException, GraphQLQuery


class TestCromClientInit:
    @patch("crombird_reddit.utils.crom_client.OAuth2Session")
    @patch("crombird_reddit.utils.crom_client.BackendApplicationClient")
    def test_creates_oauth_session_with_client(
        self, mock_backend_client, mock_oauth_session
    ):
        mock_client_instance = MagicMock()
        mock_backend_client.return_value = mock_client_instance

        client = CromClient()

        mock_backend_client.assert_called_once_with(client_id="test-client-id")
        mock_oauth_session.assert_called_once_with(client=mock_client_instance)


class TestQuery:
    @patch("crombird_reddit.utils.crom_client.OAuth2Session")
    @patch("crombird_reddit.utils.crom_client.BackendApplicationClient")
    def test_query_calls_query_batch_and_returns_first_result(
        self, mock_backend_client, mock_oauth_session
    ):
        mock_session = MagicMock()
        mock_oauth_session.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = [{"data": {"result": "test"}}]
        mock_session.post.return_value = mock_response

        client = CromClient()
        result = client.query({"query": "test query", "variables": None})

        assert result == {"result": "test"}


class TestQueryBatch:
    @patch("crombird_reddit.utils.crom_client.OAuth2Session")
    @patch("crombird_reddit.utils.crom_client.BackendApplicationClient")
    def test_posts_queries_to_api_endpoint(
        self, mock_backend_client, mock_oauth_session
    ):
        mock_session = MagicMock()
        mock_oauth_session.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = [{"data": {"result": "test"}}]
        mock_session.post.return_value = mock_response

        client = CromClient()
        queries: list[GraphQLQuery] = [
            {"query": "test query", "variables": {"var": "value"}}
        ]
        client.query_batch(queries)

        mock_session.post.assert_called_once_with(
            "http://test-api-endpoint",
            json=queries,
        )

    @patch("crombird_reddit.utils.crom_client.OAuth2Session")
    @patch("crombird_reddit.utils.crom_client.BackendApplicationClient")
    def test_returns_data_from_each_query_response(
        self, mock_backend_client, mock_oauth_session
    ):
        mock_session = MagicMock()
        mock_oauth_session.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"data": {"page": "SCP-173"}},
            {"data": {"page": "SCP-999"}},
        ]
        mock_session.post.return_value = mock_response

        client = CromClient()
        result = client.query_batch(
            [
                {"query": "query1", "variables": None},
                {"query": "query2", "variables": None},
            ]
        )

        assert result == [{"page": "SCP-173"}, {"page": "SCP-999"}]

    @patch("crombird_reddit.utils.crom_client.OAuth2Session")
    @patch("crombird_reddit.utils.crom_client.BackendApplicationClient")
    def test_raises_exception_when_response_is_not_list(
        self, mock_backend_client, mock_oauth_session
    ):
        mock_session = MagicMock()
        mock_oauth_session.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "something went wrong"}
        mock_session.post.return_value = mock_response

        client = CromClient()

        with pytest.raises(CromAPIException) as exc_info:
            client.query_batch([{"query": "test", "variables": None}])

        assert exc_info.value.args[0] == {"error": "something went wrong"}

    @patch("crombird_reddit.utils.crom_client.OAuth2Session")
    @patch("crombird_reddit.utils.crom_client.BackendApplicationClient")
    def test_raises_exception_when_query_has_errors(
        self, mock_backend_client, mock_oauth_session
    ):
        mock_session = MagicMock()
        mock_oauth_session.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"data": None, "errors": [{"message": "Query failed"}]}
        ]
        mock_session.post.return_value = mock_response

        client = CromClient()

        with pytest.raises(CromAPIException) as exc_info:
            client.query_batch([{"query": "test", "variables": None}])

        assert exc_info.value.args[0] == [{"message": "Query failed"}]

    @patch("crombird_reddit.utils.crom_client.OAuth2Session")
    @patch("crombird_reddit.utils.crom_client.BackendApplicationClient")
    def test_does_not_raise_when_errors_list_is_empty(
        self, mock_backend_client, mock_oauth_session
    ):
        mock_session = MagicMock()
        mock_oauth_session.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = [{"data": {"result": "ok"}, "errors": []}]
        mock_session.post.return_value = mock_response

        client = CromClient()
        result = client.query_batch([{"query": "test", "variables": None}])

        assert result == [{"result": "ok"}]

    @patch("crombird_reddit.utils.crom_client.OAuth2Session")
    @patch("crombird_reddit.utils.crom_client.BackendApplicationClient")
    def test_refreshes_token_on_token_expired_error(
        self, mock_backend_client, mock_oauth_session
    ):
        mock_session = MagicMock()
        mock_oauth_session.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = [{"data": {"result": "success"}}]

        # First call raises TokenExpiredError, second succeeds
        mock_session.post.side_effect = [TokenExpiredError(), mock_response]

        client = CromClient()
        result = client.query_batch([{"query": "test", "variables": None}])

        # Should have fetched a new token
        mock_session.fetch_token.assert_called_once_with(
            token_url="http://test-auth-endpoint",
            client_id="test-client-id",
            client_secret="test-client-secret",
        )
        # Should have retried and succeeded
        assert result == [{"result": "success"}]
