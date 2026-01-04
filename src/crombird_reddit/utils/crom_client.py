import os
from typing import Any, TypedDict
from oauthlib.oauth2 import BackendApplicationClient, TokenExpiredError
from requests_oauthlib import OAuth2Session


API_ENDPOINT = os.environ["API_ENDPOINT"]
AUTH_ENDPOINT = os.environ["AUTH_ENDPOINT"]
CROM_CLIENT_ID = os.environ["CROM_CLIENT_ID"]
CROM_CLIENT_SECRET = os.environ["CROM_CLIENT_SECRET"]


class CromAPIException(Exception):
    pass


class GraphQLQuery(TypedDict):
    query: str
    variables: dict[str, Any] | None


class CromClient:
    def __init__(self):
        client = BackendApplicationClient(client_id=CROM_CLIENT_ID)
        self._session = OAuth2Session(client=client)

    def query(self, query: GraphQLQuery) -> dict:
        return self.query_batch([query])[0]

    def query_batch(self, queries: list[GraphQLQuery]) -> list[dict]:
        for i in range(2):
            try:
                response = self._session.post(API_ENDPOINT, json=queries)
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, list):
                    raise CromAPIException(body)
                for query_response in body:
                    if "errors" in query_response and len(query_response["errors"]) > 0:
                        raise CromAPIException(query_response["errors"])
                return [query_response["data"] for query_response in body]
            except TokenExpiredError:
                self._session.fetch_token(
                    token_url=AUTH_ENDPOINT,
                    client_id=CROM_CLIENT_ID,
                    client_secret=CROM_CLIENT_SECRET,
                )
