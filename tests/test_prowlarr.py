import io
import json
from urllib.error import HTTPError

import pytest

from prowlarr import (
    INDEXER_OPERATION_TIMEOUT,
    ProwlarrClient,
    ProwlarrError,
    split_indexer_url,
)


class Response:
    def __init__(self, payload, status=200, headers=None):
        self.body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.status = status
        self.headers = headers or {}
        self.offset = 0

    def read(self, size=-1):
        if size < 0:
            size = len(self.body) - self.offset
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def generic_schema():
    return {
        "name": "Generic Torznab",
        "implementationName": "Torznab",
        "implementation": "Torznab",
        "enable": True,
        "priority": 25,
        "appProfileId": 1,
        "fields": [
            {"name": "baseUrl", "value": "", "type": "textbox"},
            {"name": "apiPath", "value": "/api", "type": "textbox"},
            {"name": "apiKey", "value": "", "type": "textbox"},
            {"name": "seedCriteria", "value": {"seeders": 1}},
        ],
    }


def app_profiles():
    return [{"id": 1, "name": "Standard"}]


def http_error(status, payload):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return HTTPError("http://prowlarr", status, "error", {}, io.BytesIO(body))


def client(responses, *, max_response_bytes=1024 * 1024):
    opener = FakeOpener(responses)
    return (
        ProwlarrClient(
            "http://prowlarr:9696/",
            "secret-key",
            "http://icvdb-torznab:8000/api",
            opener=opener,
            max_response_bytes=max_response_bytes,
        ),
        opener,
    )


def test_connection_uses_authenticated_schema_endpoint():
    subject, opener = client([Response([generic_schema()])])

    subject.test_connection()

    request, timeout = opener.requests[0]
    assert request.full_url == "http://prowlarr:9696/api/v1/indexer/schema"
    assert request.get_header("X-api-key") == "secret-key"
    assert 0 < timeout <= 30


def test_schema_response_above_default_limit_is_accepted():
    schema = generic_schema()
    schema["largePayload"] = "x" * (1024 * 1024)
    subject, _ = client([Response([schema])])

    subject.test_connection()


def test_normal_response_above_default_limit_is_rejected():
    subject, _ = client([Response([{"largePayload": "x" * (1024 * 1024)}])])

    with pytest.raises(ProwlarrError) as captured:
        subject._indexers()

    assert captured.value.code == "prowlarr_response_too_large"


def test_schema_response_above_schema_limit_is_rejected():
    subject, _ = client([Response([{"largePayload": "x" * (16 * 1024 * 1024)}])])

    with pytest.raises(ProwlarrError) as captured:
        subject.test_connection()

    assert captured.value.code == "prowlarr_response_too_large"


@pytest.mark.parametrize(
    "response",
    [
        Response(b""),
        Response(b"not-json"),
        Response(b"x" * 33, headers={"Content-Length": "33"}),
        Response(b"x" * 33),
    ],
)
def test_invalid_or_oversized_responses_are_rejected(response):
    subject, _ = client([response], max_response_bytes=32)

    with pytest.raises(ProwlarrError):
        subject.test_connection()


def test_transport_error_is_classified_without_exposing_api_key():
    subject, _ = client([OSError("failed secret-key")])

    with pytest.raises(ProwlarrError) as captured:
        subject.test_connection()

    assert captured.value.code == "prowlarr_unreachable"
    assert captured.value.stage == "connect"
    assert "secret-key" not in str(captured.value)
    assert "secret-key" not in json.dumps(captured.value.as_detail())


def test_authentication_error_is_classified_and_keeps_safe_upstream_message():
    subject, _ = client([http_error(401, {"message": "Unauthorized"})])

    with pytest.raises(ProwlarrError) as captured:
        subject.test_connection()

    error = captured.value
    assert error.code == "prowlarr_auth_failed"
    assert error.stage == "connect"
    assert error.upstream_status == 401
    assert error.upstream_message == "Unauthorized"


def test_upstream_error_message_redacts_api_key_and_traceback():
    subject, _ = client(
        [
            http_error(
                500,
                {"message": "secret-key Traceback (most recent call last): private"},
            )
        ]
    )

    with pytest.raises(ProwlarrError) as captured:
        subject.test_connection()

    detail = captured.value.as_detail()
    assert "secret-key" not in json.dumps(detail)
    assert "Traceback" not in json.dumps(detail)


def test_schema_is_deep_copied_and_named_fields_are_updated():
    schema = generic_schema()
    subject, opener = client(
        [
            Response([schema]),
            Response(app_profiles()),
        ]
    )

    resource = subject.build_indexer_resource()

    assert resource["name"] == "Violarr"
    assert resource["priority"] == 25
    assert resource["appProfileId"] == 1
    assert {field["name"]: field.get("value") for field in resource["fields"]} == {
        "baseUrl": "http://icvdb-torznab:8000",
        "apiPath": "/api",
        "apiKey": "",
        "seedCriteria": {"seeders": 1},
    }
    assert schema["fields"][0]["value"] == ""

    assert [request.full_url for request, _ in opener.requests] == [
        "http://prowlarr:9696/api/v1/indexer/schema",
        "http://prowlarr:9696/api/v1/appprofile",
    ]


def test_missing_generic_schema_or_required_fields_is_rejected():
    wrong = generic_schema()
    wrong["implementation"] = "Newznab"
    subject, _ = client([Response([wrong])])
    with pytest.raises(ProwlarrError) as captured:
        subject.build_indexer_resource()
    assert captured.value.code == "prowlarr_schema_unavailable"

    incomplete = generic_schema()
    incomplete["fields"] = incomplete["fields"][:-1]
    incomplete["fields"] = [f for f in incomplete["fields"] if f["name"] != "apiPath"]
    subject, _ = client([Response([incomplete])])
    with pytest.raises(ProwlarrError) as captured:
        subject.build_indexer_resource()
    assert captured.value.code == "prowlarr_invalid_schema"


def test_existing_indexer_is_detected_by_implementation_and_normalized_endpoint():
    existing = generic_schema()
    existing["name"] = "Renamed by user"
    existing["fields"][0]["value"] = "http://icvdb-torznab:8000/"

    subject, opener = client(
        [
            Response([generic_schema()]),
            Response(app_profiles()),
            Response([existing]),
        ]
    )

    result = subject.ensure_indexer()

    assert result == {
        "created": False,
        "already_installed": True,
        "indexer_id": None,
    }
    assert len(opener.requests) == 3


def test_indexer_test_failure_is_distinguished_from_prowlarr_connection_failure():
    subject, _ = client(
        [
            Response([generic_schema()]),
            Response(app_profiles()),
            Response([]),
            http_error(
                400,
                [
                    {
                        "propertyName": "BaseUrl",
                        "errorMessage": "Unable to connect to indexer",
                    }
                ],
            ),
        ]
    )

    with pytest.raises(ProwlarrError) as captured:
        subject.ensure_indexer()

    error = captured.value
    assert error.code == "indexer_test_failed"
    assert error.stage == "indexer_test"
    assert error.upstream_status == 400
    assert error.upstream_message == "Unable to connect to indexer"


def test_create_tests_resource_before_posting_and_preserves_template_defaults():
    subject, opener = client(
        [
            Response([generic_schema()]),
            Response(app_profiles()),
            Response([]),
            Response({}),
            Response({"id": 42}),
        ]
    )

    result = subject.ensure_indexer()

    assert result == {
        "created": True,
        "already_installed": False,
        "indexer_id": 42,
    }

    assert [request.method for request, _ in opener.requests] == [
        "GET",
        "GET",
        "GET",
        "POST",
        "POST",
    ]

    assert [request.full_url for request, _ in opener.requests] == [
        "http://prowlarr:9696/api/v1/indexer/schema",
        "http://prowlarr:9696/api/v1/appprofile",
        "http://prowlarr:9696/api/v1/indexer",
        "http://prowlarr:9696/api/v1/indexer/test",
        "http://prowlarr:9696/api/v1/indexer",
    ]

    assert [timeout for _, timeout in opener.requests] == [
        subject.timeout,
        subject.timeout,
        subject.timeout,
        INDEXER_OPERATION_TIMEOUT,
        INDEXER_OPERATION_TIMEOUT,
    ]

    tested = json.loads(opener.requests[-2][0].data)
    created = json.loads(opener.requests[-1][0].data)

    assert tested == created
    assert created["appProfileId"] == 1


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://host:8000/api", ("http://host:8000", "/api")),
        ("https://host/root/api/", ("https://host", "/root/api/")),
        ("https://host", ("https://host", "/api")),
        ("https://host/", ("https://host", "/api")),
        ("http://[2001:db8::1]:8000/api", ("http://[2001:db8::1]:8000", "/api")),
    ],
)
def test_indexer_url_is_split_into_origin_and_api_path(url, expected):
    assert split_indexer_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://host/root/api?t=caps",
        "https://host/root/api#caps",
    ],
)
def test_indexer_url_rejects_query_and_fragment(url):
    with pytest.raises(ProwlarrError) as captured:
        split_indexer_url(url)

    assert captured.value.code == "invalid_indexer_url"


def test_status_reports_connection_failure_without_secret():
    subject, _ = client([OSError("failed secret-key")])

    status = subject.status()

    assert status["configured"] is True
    assert status["connected"] is False
    assert status["indexer_installed"] is False
    assert status["error"] == "Unable to connect to Prowlarr"
    assert "secret-key" not in json.dumps(status)
