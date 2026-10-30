"""Zero-network adversarial QA for browser-wide no-submit egress protection."""
import unittest

from scripts.no_submit_browser_guard import NoSubmitNetworkGuard


class Request:
    def __init__(self, method="GET", url="http://127.0.0.1:32123/index.html"):
        self.method = method
        self.url = url


class Route:
    def __init__(self, request=None):
        self.request = request or Request()
        self.continued = False
        self.blocked = False

    def continue_(self):
        self.continued = True

    def abort(self, reason):
        assert reason == "blockedbyclient"
        self.blocked = True


class SocketRoute:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class Emitter:
    def __init__(self):
        self.events = {}

    def on(self, name, callback):
        self.events[name] = callback

    def emit(self, name, obj):
        self.events[name](obj)


class Context(Emitter):
    def route(self, pattern, callback):
        assert pattern == "**/*"
        self.http_route = callback

    def route_web_socket(self, pattern, callback):
        assert pattern == "**/*"
        self.socket_route = callback


class Frame:
    def __init__(self, url):
        self.url = url


class NoSubmitNetworkTests(unittest.TestCase):
    def setUp(self):
        self.guard = NoSubmitNetworkGuard("http://127.0.0.1:32123/")
        self.context = Context()
        self.guard.attach(self.context)
        self.page = Emitter()
        self.context.emit("page", self.page)
        self.local = Request()
        self.context.emit("request", self.local)

    def test_local_get_is_allowed(self):
        route = Route(self.local)
        self.context.http_route(route)
        self.assertTrue(route.continued)
        self.assertFalse(route.blocked)
        self.page.emit("framenavigated", Frame("about:blank"))
        self.page.emit("framenavigated", Frame(self.local.url))
        self.guard.assert_clean()

    def test_cross_origin_get_is_blocked_before_network_even_in_popup(self):
        secret = "test-buyer@example.com"
        request = Request(url="https://unapproved.example/collect?email=" + secret)
        route = Route(request)
        self.context.http_route(route)
        self.context.emit("request", request)
        second_page = Emitter()
        self.context.emit("page", second_page)
        self.assertFalse(route.continued)
        self.assertTrue(route.blocked)
        with self.assertRaisesRegex(AssertionError, "NONLOCAL_OR_NONGET_REQUEST") as exc:
            self.guard.assert_clean()
        self.assertNotIn(secret, str(exc.exception))
        self.assertIn("UNEXPECTED_POPUP_OR_TAB", str(exc.exception))

    def test_same_origin_post_is_blocked(self):
        route = Route(Request(method="POST"))
        self.context.http_route(route)
        self.assertTrue(route.blocked)
        with self.assertRaisesRegex(AssertionError, "NONLOCAL_OR_NONGET_REQUEST"):
            self.guard.assert_clean()

    def test_other_local_port_is_blocked(self):
        route = Route(Request(url="http://127.0.0.1:54321/private"))
        self.context.http_route(route)
        self.assertTrue(route.blocked)

    def test_localhost_alias_is_not_allowlisted(self):
        route = Route(Request(url="http://localhost:32123/secret"))
        self.context.http_route(route)
        self.assertTrue(route.blocked)

    def test_foreign_websocket_is_closed_before_open(self):
        socket = SocketRoute()
        self.context.socket_route(socket)
        self.assertTrue(socket.closed)
        with self.assertRaisesRegex(AssertionError, "WEBSOCKET_ATTEMPT"):
            self.guard.assert_clean()

    def test_frame_mailto_or_data_navigation_is_recorded(self):
        self.page.emit("framenavigated", Frame("mailto:buyer@example.com"))
        with self.assertRaisesRegex(AssertionError, "NONLOCAL_FRAME_NAVIGATION"):
            self.guard.assert_clean()

    def test_page_download_attempt_is_recorded(self):
        self.page.emit("download", object())
        with self.assertRaisesRegex(AssertionError, "UNEXPECTED_DOWNLOAD"):
            self.guard.assert_clean()

    def test_no_page_or_network_is_not_false_green(self):
        guard = NoSubmitNetworkGuard("http://127.0.0.1:32123")
        with self.assertRaisesRegex(AssertionError, "PRIMARY_PAGE_COUNT_INVALID"):
            guard.assert_clean()

    def test_actual_browser_qa_installs_guard_at_context_scope(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "scripts" /
                  "qa_browser_to_core_intake.py").read_text(encoding="utf-8")
        self.assertIn("guard.attach(context)", source)
        self.assertIn("guard.assert_clean()", source)
        self.assertNotIn('page.on("request"', source)

    def test_bad_origin_cannot_silently_relax_policy(self):
        for url in ("https://127.0.0.1:32123", "http://localhost:32123",
                    "http://127.0.0.1:32123@evil.example",
                    "http://127.0.0.1:32123/other", "http://127.0.0.1"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                NoSubmitNetworkGuard(url)


if __name__ == "__main__":
    unittest.main()
