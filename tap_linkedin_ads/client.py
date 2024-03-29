"""REST client handling, including LinkedInAdsStream base class."""

from __future__ import annotations

import typing as t
from datetime import datetime, timezone
from pathlib import Path

from singer_sdk.authenticators import BearerTokenAuthenticator
from singer_sdk.streams import RESTStream

if t.TYPE_CHECKING:
    import requests

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")
UTC = timezone.utc


class LinkedInAdsStream(RESTStream):
    """LinkedInAds stream class."""

    records_jsonpath = "$[*]"  # Or override `parse_response`.
    next_page_token_jsonpath = (
        "$.paging.start"  # Or override `get_next_page_token`.  # noqa: S105
    )

    @property
    def authenticator(self) -> BearerTokenAuthenticator:
        """Return a new authenticator object.

        Returns:
            An authenticator instance.
        """
        return BearerTokenAuthenticator.create_for_stream(
            self,
            token=self.config["access_token"],
        )

    @property
    def http_headers(self) -> dict:
        """Return the http headers needed.

        Returns:
            A dictionary of HTTP headers.
        """
        headers = {}
        if "user_agent" in self.config:
            headers["User-Agent"] = self.config["user_agent"]
        headers["LinkedIn-Version"] = "202305"
        headers["Content-Type"] = "application/json"
        headers["X-Restli-Protocol-Version"] = "1.0.0"

        return headers

    def get_next_page_token(
        self,
        response: requests.Response,
        previous_token: t.Any | None,
    ) -> t.Any | None:
        """Return a token for identifying next page or None if no more pages."""
        # If pagination is required, return a token which can be used to get the
        #       next page. If this is the final page, return "None" to end the
        #       pagination loop.
        resp_json = response.json()
        if previous_token is None:
            previous_token = 0

        elements = resp_json.get("elements")

        if elements is not None:
            if len(elements) == 0 or len(elements) == previous_token + 1:
                return None
        else:
            page = resp_json
            if len(page) == 0 or len(page) == previous_token + 1:
                return None

        return previous_token + 1

    def get_url_params(
        self,
        context: dict | None,  # noqa: ARG002
        next_page_token: t.Any | None,
    ) -> dict[str, t.Any]:
        """Return a dictionary of values to be used in URL parameterization.

        Args:
            context: The stream context.
            next_page_token: The next page index or value.

        Returns:
            A dictionary of URL query parameters.
        """
        params: dict = {}
        if next_page_token:
            params["start"] = next_page_token
        if self.replication_key:
            params["sort"] = "asc"
            params["order_by"] = self.replication_key

        return params

    def parse_response(  # noqa: PLR0912
        self,
        response: requests.Response,
    ) -> t.Iterable[dict]:
        """Parse the response and return an iterator of result records.

        Args:
            response: The HTTP ``requests.Response`` object.

        Yields:
            Each record from the source.
        """
        resp_json = response.json()
        if resp_json.get("elements") is not None:
            results = resp_json["elements"]
            try:
                columns = results[0]
            except:  # noqa: E722
                columns = results
                pass
            try:
                created_time = (
                    columns.get("changeAuditStamps").get("created").get("time")
                )
                last_modified_time = (
                    columns.get("changeAuditStamps").get("lastModified").get("time")
                )
                columns["created_time"] = datetime.fromtimestamp(
                    int(created_time) / 1000,
                    tz=UTC,
                ).isoformat()
                columns["last_modified_time"] = datetime.fromtimestamp(
                    int(last_modified_time) / 1000,
                    tz=UTC,
                ).isoformat()
            except:  # noqa: E722, S110
                pass
        else:
            results = resp_json
            try:
                columns = results
                created_time = (
                    columns.get("changeAuditStamps").get("created").get("time")
                )
                last_modified_time = (
                    columns.get("changeAuditStamps").get("lastModified").get("time")
                )
                columns["created_time"] = datetime.fromtimestamp(
                    int(created_time) / 1000,
                    tz=UTC,
                ).isoformat()
                columns["last_modified_time"] = datetime.fromtimestamp(
                    int(last_modified_time) / 1000,
                    tz=UTC,
                ).isoformat()
            except:  # noqa: E722
                columns = results
                pass

        try:
            account_column = columns.get("account")
            account_id = int(account_column.split(":")[3])
            columns["account_id"] = account_id
        except:  # noqa: E722, S110
            pass
        try:
            campaign_column = columns.get("campaignGroup")
            campaign = int(campaign_column.split(":")[3])
            columns["campaign_group_id"] = campaign
        except:  # noqa: E722, S110
            pass
        try:
            schedule_column = columns.get("runSchedule").get("start")
            columns["run_schedule_start"] = datetime.fromtimestamp(  # noqa: DTZ006
                int(schedule_column) / 1000,
            ).isoformat()
        except:  # noqa: E722, S110
            pass

        results = (
            resp_json["elements"]
            if resp_json.get("elements") is not None
            else [columns]
        )

        yield from results
