import json
import socket
from copy import deepcopy
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 10.0
INDEXER_OPERATION_TIMEOUT = 30.0
DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024
PROWLARR_SCHEMA_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
PROWLARR_ERROR_MAX_RESPONSE_BYTES = 64 * 1024
PROWLARR_ERROR_MESSAGE_MAX_CHARS = 1000


class ProwlarrError(RuntimeError):
    """A structured, secret-safe Prowlarr integration error."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "prowlarr_request_failed",
        stage: str = "request",
        hint: str | None = None,
        upstream_status: int | None = None,
        upstream_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.hint = hint
        self.upstream_status = upstream_status
        self.upstream_message = upstream_message

    def as_detail(self) -> dict[str, Any]:
        detail: dict[str, Any] = {
            "code": self.code,
            "message": str(self),
            "stage": self.stage,
        }
        if self.hint:
            detail["hint"] = self.hint
        if self.upstream_status is not None:
            detail["upstream_status"] = self.upstream_status
        if self.upstream_message:
            detail["upstream_message"] = self.upstream_message
        return detail


def _url_error_code(name: str) -> str:
    return "invalid_prowlarr_url" if name == "Prowlarr URL" else "invalid_indexer_url"


def _absolute_http_url(value: str, name: str) -> tuple[str, str, str]:
    try:
        parsed = urlsplit(value)
        parsed.port
    except (TypeError, ValueError) as exc:
        raise ProwlarrError(
            f"{name} is not a valid HTTP URL",
            code=_url_error_code(name),
            stage="configuration",
        ) from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ProwlarrError(
            f"{name} is not a valid HTTP URL",
            code=_url_error_code(name),
            stage="configuration",
        )
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    return origin, parsed.path, parsed.query


def normalize_base_url(value: str) -> str:
    origin, path, query = _absolute_http_url(value, "Prowlarr URL")
    parsed = urlsplit(value)
    if query or parsed.fragment:
        raise ProwlarrError(
            "Prowlarr URL must not include a query or fragment",
            code="invalid_prowlarr_url",
            stage="configuration",
        )
    suffix = path.rstrip("/")
    return f"{origin}{suffix}"


def split_indexer_url(value: str) -> tuple[str, str]:
    origin, path, query = _absolute_http_url(value, "Indexer URL")
    parsed = urlsplit(value)
    if query or parsed.fragment:
        raise ProwlarrError(
            "Indexer URL must not include a query or fragment",
            code="invalid_indexer_url",
            stage="configuration",
        )
    api_path = f"/{path.lstrip('/')}" if path not in {"", "/"} else "/api"
    return origin, api_path


def _field_values(resource: dict[str, Any]) -> dict[str, Any]:
    fields = resource.get("fields")
    if not isinstance(fields, list):
        return {}
    return {
        field.get("name"): field.get("value")
        for field in fields
        if isinstance(field, dict) and isinstance(field.get("name"), str)
    }


def _first_error_message(value: Any) -> str | None:
    if isinstance(value, str):
        text = " ".join(value.split())
        return text or None

    if isinstance(value, list):
        messages = [_first_error_message(item) for item in value]
        messages = [message for message in messages if message]
        return "; ".join(messages) if messages else None

    if isinstance(value, dict):
        for key in ("errorMessage", "message", "detail", "title", "error"):
            if key in value:
                message = _first_error_message(value[key])
                if message:
                    return message
        if "errors" in value:
            message = _first_error_message(value["errors"])
            if message:
                return message

    return None


def _sanitize_message(value: str | None, *secrets: str) -> str | None:
    if not value:
        return None

    sanitized = " ".join(value.split())
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[redacted]")

    if "traceback" in sanitized.casefold():
        return None

    return sanitized[:PROWLARR_ERROR_MESSAGE_MAX_CHARS] or None


class ProwlarrClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        indexer_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.api_key = api_key
        self.indexer_url = indexer_url
        self.timeout = min(max(float(timeout), 0.1), 30.0)
        self.max_response_bytes = max_response_bytes
        self._opener = opener

    def _http_error_message(self, exc: HTTPError) -> str | None:
        try:
            raw = exc.read(PROWLARR_ERROR_MAX_RESPONSE_BYTES + 1)
        except Exception:
            return None

        if len(raw) > PROWLARR_ERROR_MAX_RESPONSE_BYTES:
            raw = raw[:PROWLARR_ERROR_MAX_RESPONSE_BYTES]

        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            return None

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            message = text
        else:
            message = _first_error_message(payload)

        return _sanitize_message(message, self.api_key)

    def _http_error(self, exc: HTTPError, stage: str) -> ProwlarrError:
        upstream_message = self._http_error_message(exc)

        if exc.code in {401, 403}:
            return ProwlarrError(
                "Prowlarr rejected the API key",
                code="prowlarr_auth_failed",
                stage=stage,
                hint="Check the Prowlarr API key and permissions.",
                upstream_status=exc.code,
                upstream_message=upstream_message,
            )

        if stage == "indexer_test":
            return ProwlarrError(
                "Prowlarr could not validate the Violarr indexer",
                code="indexer_test_failed",
                stage=stage,
                hint=(
                    "Check that the Indexer URL is reachable from Prowlarr and points "
                    "to the Violarr /api endpoint."
                ),
                upstream_status=exc.code,
                upstream_message=upstream_message,
            )

        if stage == "indexer_create":
            return ProwlarrError(
                "Prowlarr could not create the Violarr indexer",
                code="indexer_create_failed",
                stage=stage,
                hint="Check the Prowlarr validation message and indexer configuration.",
                upstream_status=exc.code,
                upstream_message=upstream_message,
            )

        return ProwlarrError(
            f"Prowlarr returned HTTP {exc.code}",
            code="prowlarr_http_error",
            stage=stage,
            hint="Check the Prowlarr URL, API availability, and server logs.",
            upstream_status=exc.code,
            upstream_message=upstream_message,
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: Any = None,
        max_response_bytes: int | None = None,
        *,
        stage: str = "request",
        timeout: float | None = None,
    ) -> Any:
        effective_max_response_bytes = (
            self.max_response_bytes if max_response_bytes is None else max_response_bytes
        )
        body = None
        headers = {
            "Accept": "application/json",
            "X-Api-Key": self.api_key,
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with self._opener(
                request,
                timeout=self.timeout if timeout is None else timeout,
            ) as response:
                length = response.headers.get("Content-Length")
                if length is not None:
                    try:
                        if int(length) > effective_max_response_bytes:
                            raise ProwlarrError(
                                "Prowlarr response is too large",
                                code="prowlarr_response_too_large",
                                stage=stage,
                            )
                    except ValueError:
                        pass
                raw = response.read(effective_max_response_bytes + 1)
        except ProwlarrError:
            raise
        except HTTPError as exc:
            raise self._http_error(exc, stage) from None
        except URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise ProwlarrError(
                    "Prowlarr request timed out",
                    code="prowlarr_timeout",
                    stage=stage,
                    hint="Check the Prowlarr address, port, and network path.",
                ) from None
            raise ProwlarrError(
                "Unable to connect to Prowlarr",
                code="prowlarr_unreachable",
                stage=stage,
                hint=(
                    "If Prowlarr runs on the Docker host, use a host address reachable "
                    "from the Violarr container."
                ),
            ) from None
        except (socket.timeout, TimeoutError):
            raise ProwlarrError(
                "Prowlarr request timed out",
                code="prowlarr_timeout",
                stage=stage,
                hint="Check the Prowlarr address, port, and network path.",
            ) from None
        except OSError:
            raise ProwlarrError(
                "Unable to connect to Prowlarr",
                code="prowlarr_unreachable",
                stage=stage,
                hint=(
                    "If Prowlarr runs on the Docker host, use a host address reachable "
                    "from the Violarr container."
                ),
            ) from None

        if len(raw) > effective_max_response_bytes:
            raise ProwlarrError(
                "Prowlarr response is too large",
                code="prowlarr_response_too_large",
                stage=stage,
            )
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProwlarrError(
                "Prowlarr returned invalid JSON",
                code="prowlarr_invalid_response",
                stage=stage,
                hint="Check that the configured URL points to a Prowlarr instance.",
            ) from None

    def _schemas(self) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            "/api/v1/indexer/schema",
            max_response_bytes=PROWLARR_SCHEMA_MAX_RESPONSE_BYTES,
            stage="connect",
        )
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ProwlarrError(
                "Prowlarr returned an invalid indexer schema response",
                code="prowlarr_invalid_schema",
                stage="schema",
            )
        return payload

    def test_connection(self) -> None:
        self._schemas()

    def _generic_template(self) -> dict[str, Any]:
        for resource in self._schemas():
            if resource.get("implementation") != "Torznab":
                continue
            name = str(resource.get("name", "")).casefold()
            implementation_name = str(resource.get("implementationName", "")).casefold()
            if name == "generic torznab" or implementation_name == "generic torznab":
                return resource
        raise ProwlarrError(
            "Prowlarr Generic Torznab schema is unavailable",
            code="prowlarr_schema_unavailable",
            stage="schema",
            hint="Confirm that this Prowlarr version provides the Generic Torznab indexer.",
        )

    def build_indexer_resource(self) -> dict[str, Any]:
        resource = deepcopy(self._generic_template())

        base_url, api_path = split_indexer_url(self.indexer_url)

        values = {
            "baseUrl": base_url,
            "apiPath": api_path,
            "apiKey": "",
        }

        fields = resource.get("fields")

        if not isinstance(fields, list):
            raise ProwlarrError(
                "Prowlarr Generic Torznab schema has invalid fields",
                code="prowlarr_invalid_schema",
                stage="schema",
            )

        found = set()

        for field in fields:
            if isinstance(field, dict) and field.get("name") in values:
                field["value"] = values[field["name"]]
                found.add(field["name"])

        missing = set(values) - found

        if missing:
            missing_name = sorted(missing)[0]
            raise ProwlarrError(
                f"Prowlarr Generic Torznab schema is missing {missing_name}",
                code="prowlarr_invalid_schema",
                stage="schema",
            )

        resource["name"] = "Violarr"
        resource["appProfileId"] = self._default_app_profile_id()

        return resource

    def _indexers(self) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            "/api/v1/indexer",
            stage="list_indexers",
        )
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ProwlarrError(
                "Prowlarr returned an invalid indexer list",
                code="prowlarr_invalid_response",
                stage="list_indexers",
            )
        return payload

    def _is_installed(self, resource: dict[str, Any]) -> bool:
        if resource.get("implementation") != "Torznab":
            return False
        fields = _field_values(resource)
        try:
            configured = split_indexer_url(self.indexer_url)
            existing_origin, existing_path = split_indexer_url(
                f"{str(fields.get('baseUrl', '')).rstrip('/')}/{str(fields.get('apiPath', '')).lstrip('/')}"
            )
        except ProwlarrError:
            return False
        return (existing_origin.rstrip("/"), existing_path.rstrip("/")) == (
            configured[0].rstrip("/"),
            configured[1].rstrip("/"),
        )

    def ensure_indexer(self) -> dict[str, Any]:
        resource = self.build_indexer_resource()
        existing = next((item for item in self._indexers() if self._is_installed(item)), None)
        if existing is not None:
            identifier = existing.get("id")
            return {
                "created": False,
                "already_installed": True,
                "indexer_id": identifier if isinstance(identifier, int) else None,
            }
        self._request(
            "POST",
            "/api/v1/indexer/test",
            resource,
            stage="indexer_test",
            timeout=INDEXER_OPERATION_TIMEOUT,
        )
        created = self._request(
            "POST",
            "/api/v1/indexer",
            resource,
            stage="indexer_create",
            timeout=INDEXER_OPERATION_TIMEOUT,
        )
        identifier = created.get("id") if isinstance(created, dict) else None
        return {
            "created": True,
            "already_installed": False,
            "indexer_id": identifier if isinstance(identifier, int) else None,
        }

    def status(self) -> dict[str, Any]:
        try:
            self.test_connection()
            installed = any(self._is_installed(item) for item in self._indexers())
            return {
                "configured": True,
                "connected": True,
                "indexer_installed": installed,
                "error": None,
            }
        except ProwlarrError as exc:
            if exc.code == "prowlarr_unreachable":
                error = "Unable to connect to Prowlarr"
            elif exc.code == "prowlarr_invalid_response":
                error = "Prowlarr returned invalid JSON"
            else:
                error = "Prowlarr is unavailable"
            return {
                "configured": True,
                "connected": False,
                "indexer_installed": False,
                "error": error,
            }

    def _app_profiles(self) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            "/api/v1/appprofile",
            stage="app_profile",
        )

        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ProwlarrError(
                "Prowlarr returned an invalid app profile response",
                code="prowlarr_invalid_response",
                stage="app_profile",
            )

        return payload

    def _default_app_profile_id(self) -> int:
        profiles = self._app_profiles()

        for profile in profiles:
            profile_id = profile.get("id")

            if isinstance(profile_id, int) and not isinstance(profile_id, bool) and profile_id > 0:
                return profile_id

        raise ProwlarrError(
            "Prowlarr has no valid app profile configured",
            code="prowlarr_no_app_profile",
            stage="app_profile",
            hint="Create or enable an app profile in Prowlarr and try again.",
        )
