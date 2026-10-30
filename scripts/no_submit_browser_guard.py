"""Fail-closed browser egress sentinel for the fictional, no-submit website QA.

Attaches before navigation to every page in a browser context, blocks any
non-local GET and WebSocket route, and records popup/navigation/download
attempts. Only redacted violation *codes* may appear in logs.
"""
from __future__ import annotations

from urllib.parse import urlsplit


class NoSubmitNetworkGuard:
    def __init__(self, origin: str):
        try:
            parsed = urlsplit(origin)
            valid = (parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
                     and isinstance(parsed.port, int) and parsed.port > 0
                     and parsed.username is None and parsed.password is None
                     and parsed.path in ("", "/") and not parsed.query
                     and not parsed.fragment)
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("NO_SUBMIT_GUARD_REQUIRES_LOCAL_LOOPBACK_ORIGIN")
        self.port = parsed.port
        self.requests_seen = 0
        self.pages_seen = 0
        self.violations: list[str] = []

    def _violate(self, code: str) -> None:
        # Never log destination URLs, queries, email addresses, or form data.
        if code not in self.violations:
            self.violations.append(code)

    def _local(self, url: str) -> bool:
        try:
            target = urlsplit(url)
            return (target.scheme == "http" and target.hostname == "127.0.0.1"
                    and target.port == self.port
                    and target.username is None and target.password is None)
        except (TypeError, ValueError):
            return False

    def _allowed(self, request) -> bool:
        return request.method == "GET" and self._local(request.url)

    def observe_request(self, request) -> None:
        self.requests_seen += 1
        if not self._allowed(request):
            self._violate("NONLOCAL_OR_NONGET_REQUEST")

    def route_request(self, route) -> None:
        # Route interception happens before bytes reach a remote endpoint.
        if self._allowed(route.request):
            route.continue_()
        else:
            self._violate("NONLOCAL_OR_NONGET_REQUEST")
            route.abort("blockedbyclient")

    def route_websocket(self, route) -> None:
        self._violate("WEBSOCKET_ATTEMPT")
        route.close()

    def observe_websocket(self, _websocket) -> None:
        self._violate("WEBSOCKET_ATTEMPT")

    def observe_download(self, _download) -> None:
        self._violate("UNEXPECTED_DOWNLOAD")

    def observe_navigation(self, frame) -> None:
        url = frame.url
        if url != "about:blank" and not self._local(url):
            self._violate("NONLOCAL_FRAME_NAVIGATION")

    def observe_page(self, page) -> None:
        self.pages_seen += 1
        if self.pages_seen != 1:
            self._violate("UNEXPECTED_POPUP_OR_TAB")
        page.on("websocket", self.observe_websocket)
        page.on("download", self.observe_download)
        page.on("framenavigated", self.observe_navigation)

    def attach(self, context) -> None:
        # A page-scoped request listener misses popups/new tabs. Observe and
        # block at context scope *before* creating the first browser page.
        context.route("**/*", self.route_request)
        context.route_web_socket("**/*", self.route_websocket)
        context.on("request", self.observe_request)
        context.on("page", self.observe_page)

    def assert_clean(self) -> None:
        if self.pages_seen != 1:
            self._violate("PRIMARY_PAGE_COUNT_INVALID")
        if self.requests_seen < 1:
            self._violate("NO_LOCAL_PAGE_REQUEST_OBSERVED")
        if self.violations:
            raise AssertionError("NO_SUBMIT_EGRESS_BLOCKED:" + ",".join(sorted(self.violations)))
