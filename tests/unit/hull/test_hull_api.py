"""Test HullApi interface for skill servers."""


class TestHullApi:

    def test_register_route(self):
        from vessal.ark.shell.hull.hull_api import HullApi

        routes = {}
        wake_fn = lambda reason: None
        api = HullApi(routes=routes, wake_fn=wake_fn)

        def handler(body):
            return 200, {"ok": True}

        api.register_route("GET", "/custom", handler)
        assert ("GET", "/custom") in routes
        assert routes[("GET", "/custom")](None) == (200, {"ok": True})

    def test_unregister_route(self):
        from vessal.ark.shell.hull.hull_api import HullApi

        routes = {("GET", "/custom"): lambda b: (200, {})}
        api = HullApi(routes=routes, wake_fn=lambda r: None)

        api.unregister_route("/custom")
        assert ("GET", "/custom") not in routes

    def test_wake(self):
        from vessal.ark.shell.hull.hull_api import HullApi

        wakes = []
        api = HullApi(routes={}, wake_fn=lambda r: wakes.append(r))

        api.wake("test-reason")
        assert wakes == ["test-reason"]
