"""Offline unit tests for the SPA deployment/UI health check."""

import hashlib
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

import spa_healthcheck as healthcheck


SHELL = (
    b'<!doctype html><html><head><title>VilnaCRM</title>'
    b'<script id="app-runtime-config" type="application/json">'
    b'{"apiBaseUrl":"http://localhost:3000/api",'
    b'"graphqlUrl":"http://localhost:4000/graphql","flags":{}}'
    b'</script><link rel="stylesheet" href="/static/app.css">'
    b'</head><body><div id="root"></div>'
    b'<script src="/static/app.js"></script></body></html>'
)


class FakeResponse:
    def __init__(self, body, content_type):
        self.status = 200
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class SpaHealthcheckTests(unittest.TestCase):
    SHELL_ROUTES = ("/", "/sign-in", "/sign-in/", "/sign-up")

    def setUp(self):
        self.responses = {
            "/": (SHELL, "text/html"),
            "/sign-in": (SHELL, "text/html"),
            "/sign-in/": (SHELL, "text/html"),
            "/sign-up": (SHELL, "text/html"),
            "/static/app.js": (b"console.log('app')", "application/javascript"),
            "/static/app.css": (b"body{}", "text/css"),
            healthcheck.MISSING_ASSET_PATH: (b"missing", "text/plain"),
        }
        self.statuses = {healthcheck.MISSING_ASSET_PATH: 404}

    def serve(self, request, **_kwargs):
        path = request.full_url.removeprefix("https://crm.test")
        body, content_type = self.responses[path]
        response = FakeResponse(body, content_type)
        response.status = self.statuses.get(path, 200)
        return response

    def run_check(self, **kwargs):
        with patch.object(healthcheck, "urlopen", side_effect=self.serve):
            return healthcheck.check("https://crm.test", **kwargs)

    def set_shell(self, shell):
        self.responses.update({route: (shell, "text/html") for route in self.SHELL_ROUTES})

    def test_accepts_identical_shell_and_localhost_runtime_defaults(self):
        self.assertTrue(self.run_check())

    def test_accepts_valid_javascript_only_shell(self):
        shell = SHELL.replace(b'<link rel="stylesheet" href="/static/app.css">', b"")
        self.set_shell(shell)
        self.assertTrue(self.run_check())

    def test_sends_cloudfront_staging_header_contract(self):
        seen = []

        def capture(request, **_kwargs):
            seen.append(dict(request.header_items()))
            return self.serve(request)

        with patch.object(healthcheck, "urlopen", side_effect=capture):
            healthcheck.check(
                "https://crm.test",
                staging=True,
                env={"CLOUDFRONT_HEADER": "canary"},
            )
        self.assertTrue(
            any(
                name.lower() == "aws-cf-cd-canary" and value == "canary"
                for name, value in seen[0].items()
            )
        )

    def test_checks_manifest_hash_and_optional_source_revision(self):
        manifest = {
            "index_sha256": hashlib.sha256(SHELL).hexdigest(),
            "crm_source_revision": "crm-rev-1",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deployment.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertTrue(self.run_check(manifest=str(path), env={"CRM_SOURCE_VERSION": "crm-rev-1"}))
            with self.assertRaisesRegex(ValueError, "does not match CRM_SOURCE_VERSION"):
                self.run_check(manifest=str(path), env={"CRM_SOURCE_VERSION": "crm-rev-2"})

    def test_source_version_requires_manifest(self):
        with self.assertRaisesRegex(ValueError, "--deployment-manifest is required"):
            self.run_check(env={"CRM_SOURCE_VERSION": "crm-rev-1"})

    def test_manifest_hash_must_match_served_index(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deployment.json"
            path.write_text(json.dumps({"index_sha256": "0" * 64, "crm_source_revision": "r"}))
            with self.assertRaisesRegex(ValueError, "index_sha256"):
                self.run_check(manifest=str(path))

    def test_manifest_must_include_both_identity_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deployment.json"
            path.write_text(json.dumps({"index_sha256": hashlib.sha256(SHELL).hexdigest()}))
            with self.assertRaisesRegex(ValueError, "crm_source_revision"):
                self.run_check(manifest=str(path))

    def test_rejects_missing_staging_header(self):
        with self.assertRaisesRegex(ValueError, "requires CLOUDFRONT_HEADER"):
            self.run_check(staging=True, env={})

    def test_rejects_nonidentical_shell(self):
        self.responses["/sign-in"] = (SHELL + b" ", "text/html")
        self.responses["/sign-in/"] = self.responses["/sign-in"]
        with self.assertRaisesRegex(ValueError, "exact same SPA shell"):
            self.run_check()

    def test_rejects_non_200_route(self):
        self.responses["/sign-up"] = (SHELL, "text/html")
        original = self.serve

        def missing_signup(request, **kwargs):
            if request.full_url.endswith("/sign-up"):
                response = FakeResponse(SHELL, "text/html")
                response.status = 404
                return response
            return original(request, **kwargs)

        with patch.object(healthcheck, "urlopen", side_effect=missing_signup):
            with self.assertRaisesRegex(ValueError, "HTTP 404"):
                healthcheck.check("https://crm.test")

    def test_accepts_missing_asset_403_or_404(self):
        for status in (403, 404):
            with self.subTest(status=status):
                def missing_asset(request, **kwargs):
                    if request.full_url.endswith(healthcheck.MISSING_ASSET_PATH):
                        response = FakeResponse(b"not found", "text/plain")
                        response.status = status
                        return response
                    return self.serve(request, **kwargs)

                with patch.object(healthcheck, "urlopen", side_effect=missing_asset):
                    self.assertTrue(healthcheck.check("https://crm.test"))

    def test_rejects_missing_asset_spa_fallback_200_html(self):
        def html_fallback(request, **kwargs):
            if request.full_url.endswith(healthcheck.MISSING_ASSET_PATH):
                return FakeResponse(SHELL, "text/html")
            return self.serve(request, **kwargs)

        with patch.object(healthcheck, "urlopen", side_effect=html_fallback):
            with self.assertRaisesRegex(ValueError, "Missing-asset probe returned HTTP 200"):
                healthcheck.check("https://crm.test")

    def test_rejects_missing_root_mount(self):
        self.responses["/"] = (SHELL.replace(b"id=\"root\"", b"id=\"app\""), "text/html")
        self.responses.update({route: self.responses["/"] for route in self.SHELL_ROUTES[1:]})
        with self.assertRaisesRegex(ValueError, "#root"):
            self.run_check()

    def test_rejects_wrong_title(self):
        shell = SHELL.replace(b"VilnaCRM", b"Other")
        self.set_shell(shell)
        with self.assertRaisesRegex(ValueError, "title must be VilnaCRM"):
            self.run_check()

    def test_rejects_invalid_runtime_json(self):
        self.responses["/"] = (SHELL.replace(b'{"apiBaseUrl":', b'{broken,"apiBaseUrl":'), "text/html")
        self.responses["/sign-in"] = self.responses["/"]
        self.responses["/sign-in/"] = self.responses["/"]
        self.responses["/sign-up"] = self.responses["/"]
        with self.assertRaisesRegex(ValueError, "Invalid app-runtime-config JSON"):
            self.run_check()

    def test_rejects_missing_runtime_config_block(self):
        shell = SHELL.replace(
            b'<script id="app-runtime-config" type="application/json">'
            b'{"apiBaseUrl":"http://localhost:3000/api",'
            b'"graphqlUrl":"http://localhost:4000/graphql","flags":{}}'
            b'</script>',
            b"",
        )
        self.set_shell(shell)
        with self.assertRaisesRegex(ValueError, "Missing #app-runtime-config"):
            self.run_check()

    def test_allows_missing_runtime_urls_for_app_build_defaults(self):
        shell = SHELL.replace(b'"apiBaseUrl":"http://localhost:3000/api",', b"").replace(
            b'"graphqlUrl":"http://localhost:4000/graphql",', b""
        )
        self.set_shell(shell)
        self.assertTrue(self.run_check())

    def test_rejects_placeholder_and_non_local_http_runtime_urls(self):
        for url in ("https://yourserver.io/api/", "http://api.crm.test/graphql"):
            shell = SHELL.replace(b"http://localhost:3000/api", url.encode())
            self.set_shell(shell)
            with self.assertRaises(ValueError):
                self.run_check()

    def test_rejects_missing_javascript_asset(self):
        def no_js(request, **_kwargs):
            if request.full_url.endswith("/static/app.js"):
                response = FakeResponse(b"", "text/plain")
                response.status = 404
                return response
            return self.serve(request)

        with patch.object(healthcheck, "urlopen", side_effect=no_js):
            with self.assertRaisesRegex(ValueError, "JavaScript asset.*HTTP 404"):
                healthcheck.check("https://crm.test")

    def test_rejects_asset_served_as_html(self):
        self.responses["/static/app.css"] = (SHELL, "text/html")
        with self.assertRaisesRegex(ValueError, "incorrect Content-Type"):
            self.run_check()

    def test_rejects_missing_javascript_rewritten_to_html_with_200(self):
        self.responses["/static/app.js"] = (SHELL, "text/html")
        with self.assertRaisesRegex(ValueError, "incorrect Content-Type"):
            self.run_check()

    def test_rejects_html_body_even_with_javascript_content_type(self):
        self.responses["/static/app.js"] = (SHELL, "application/javascript")
        with self.assertRaisesRegex(ValueError, "returned HTML content"):
            self.run_check()

    def test_rejects_css_asset_with_wrong_content_type(self):
        self.responses["/static/app.css"] = (b"body{}", "text/plain")
        with self.assertRaisesRegex(ValueError, "CSS asset.*incorrect Content-Type"):
            self.run_check()

    def test_rejects_cross_origin_assets(self):
        shell = SHELL.replace(b"/static/app.js", b"https://assets.test/app.js")
        self.set_shell(shell)
        with self.assertRaisesRegex(ValueError, "CRM origin"):
            self.run_check()

    def test_rejects_non_html_route_response(self):
        self.responses["/sign-in"] = (SHELL, "application/json")
        with self.assertRaisesRegex(ValueError, "did not return text/html"):
            self.run_check()


if __name__ == "__main__":
    unittest.main()
