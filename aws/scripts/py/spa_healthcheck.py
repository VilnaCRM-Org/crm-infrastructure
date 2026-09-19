#!/usr/bin/env python3
"""Read-only HTTP deployment/UI contract check for the VilnaCRM SPA."""

import argparse
import hashlib
import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


ROUTES = ("/", "/sign-in", "/sign-in/", "/sign-up")
MISSING_ASSET_PATH = "/__crm_deployment_missing__.js"
USER_AGENT = "vilnacrm-spa-healthcheck/1.0"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
PLACEHOLDER_HOSTS = {"yourserver.io", "example.com", "example.org", "example.net"}
JAVASCRIPT_TYPES = {
    "application/javascript",
    "text/javascript",
    "application/ecmascript",
    "text/ecmascript",
}


class ShellParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.title_depth = 0
        self.root_count = 0
        self.runtime_config = None
        self.script_assets = []
        self.css_assets = []
        self._runtime_depth = 0
        self._runtime_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.title_depth += 1
        if tag == "div" and attrs.get("id") == "root":
            self.root_count += 1
        if tag == "script":
            if attrs.get("id") == "app-runtime-config":
                if attrs.get("type", "").lower() != "application/json" or self.runtime_config is not None:
                    raise ValueError("Expected one application/json #app-runtime-config block")
                self._runtime_depth = 1
            elif attrs.get("src"):
                self.script_assets.append(attrs["src"])
        if tag == "link" and "stylesheet" in attrs.get("rel", "").lower().split() and attrs.get("href"):
            self.css_assets.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "title" and self.title_depth:
            self.title_depth -= 1
        if tag == "script" and self._runtime_depth:
            self._runtime_depth = 0
            self.runtime_config = "".join(self._runtime_parts)

    def handle_data(self, data):
        if self.title_depth:
            self.title_parts.append(data)
        if self._runtime_depth:
            self._runtime_parts.append(data)


def fail(message):
    raise ValueError(message)


def request(url, timeout, headers):
    req = Request(url, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, response.headers, response.read()
    except HTTPError as error:
        return error.code, error.headers, error.read()
    except (URLError, TimeoutError, OSError) as error:
        fail(f"Request failed for {url}: {error}")


def same_origin_asset(base_url, asset_path):
    asset_url = urljoin(base_url, asset_path)
    base, asset = urlparse(base_url), urlparse(asset_url)
    if asset.scheme != base.scheme or asset.netloc != base.netloc:
        fail(f"Asset must use the CRM origin: {asset_path}")
    if not asset_path.startswith("/"):
        fail(f"Asset URL must be root-relative: {asset_path}")
    return asset_url


def validate_runtime_config(parser):
    if parser.runtime_config is None:
        fail("Missing #app-runtime-config application/json block")
    try:
        config = json.loads(parser.runtime_config)
    except json.JSONDecodeError as error:
        fail(f"Invalid app-runtime-config JSON: {error}")
    if not isinstance(config, dict):
        fail("app-runtime-config must be a JSON object")

    for key in ("apiBaseUrl", "graphqlUrl"):
        value = config.get(key)
        if value is None or value == "":
            continue  # App's documented build-time defaults may be localhost.
        if not isinstance(value, str):
            fail(f"Runtime {key} must be a URL string")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            fail(f"Runtime {key} must be an absolute HTTP(S) URL")
        host = parsed.hostname.lower().rstrip(".")
        if host in PLACEHOLDER_HOSTS or host.startswith("yourserver") or "placeholder" in host:
            fail(f"Runtime {key} uses placeholder host {host!r}")
        if host not in LOCAL_HOSTS and parsed.scheme != "https":
            fail(f"Runtime {key} must use HTTPS outside localhost")


def validate_manifest(path, shell, env):
    if path is None:
        return
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"Cannot read deployment manifest: {error}")
    if not isinstance(manifest, dict):
        fail("Deployment manifest must be a JSON object")
    actual_hash = hashlib.sha256(shell).hexdigest()
    if manifest.get("index_sha256") != actual_hash:
        fail("Deployment manifest index_sha256 does not match served index.html")
    source_version = env.get("CRM_SOURCE_VERSION")
    if source_version and manifest.get("crm_source_revision") != source_version:
        fail("Deployment manifest crm_source_revision does not match CRM_SOURCE_VERSION")
    if not isinstance(manifest.get("crm_source_revision"), str) or not manifest["crm_source_revision"]:
        fail("Deployment manifest is missing crm_source_revision")


def check(url, staging=False, manifest=None, timeout=20, env=None):
    env = os.environ if env is None else env
    parsed_base = urlparse(url)
    if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
        fail("--url must be an absolute HTTP(S) URL")
    base_url = url.rstrip("/")
    headers = {}
    if staging:
        value = env.get("CLOUDFRONT_HEADER", "").strip()
        if not value:
            fail("--staging requires CLOUDFRONT_HEADER")
        headers[f"aws-cf-cd-{value}"] = value
    if env.get("CRM_SOURCE_VERSION") and not manifest:
        fail("CRM_SOURCE_VERSION is set; --deployment-manifest is required")

    shells = []
    for route in ROUTES:
        status, response_headers, body = request(urljoin(base_url + "/", route.lstrip("/")), timeout, headers)
        if status != 200:
            fail(f"{route} returned HTTP {status}, expected 200")
        if "text/html" not in response_headers.get("Content-Type", "").lower():
            fail(f"{route} did not return text/html")
        shells.append((route, body))

    shell = shells[0][1]
    for route, body in shells[1:]:
        if body != shell:
            fail(f"{route} did not return the exact same SPA shell as /")

    parser = ShellParser()
    try:
        parser.feed(shell.decode("utf-8"))
        parser.close()
    except (UnicodeDecodeError, ValueError) as error:
        fail(f"Invalid SPA shell: {error}")
    if "".join(parser.title_parts).strip() != "VilnaCRM":
        fail("HTML title must be VilnaCRM")
    if parser.root_count != 1:
        fail("HTML shell must contain exactly one #root element")
    validate_runtime_config(parser)
    validate_manifest(manifest, shell, env)

    if not parser.script_assets:
        fail("HTML shell has no JavaScript assets")
    for asset_path, expected_types, kind in (
        *((path, JAVASCRIPT_TYPES, "JavaScript") for path in parser.script_assets),
        *((path, {"text/css"}, "CSS") for path in parser.css_assets),
    ):
        asset_url = same_origin_asset(url, asset_path)
        status, asset_headers, body = request(asset_url, timeout, headers)
        if status != 200:
            fail(f"{kind} asset {asset_path} returned HTTP {status}, expected 200")
        content_type = asset_headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type not in expected_types:
            fail(f"{kind} asset {asset_path} has incorrect Content-Type {content_type!r}")
        if b"<!doctype html" in body[:512].lower() or b"<html" in body[:512].lower():
            fail(f"{kind} asset {asset_path} returned HTML content")

    missing_url = urljoin(base_url + "/", MISSING_ASSET_PATH.lstrip("/"))
    missing_status, _missing_headers, _missing_body = request(missing_url, timeout, headers)
    if missing_status not in {403, 404}:
        fail(f"Missing-asset probe returned HTTP {missing_status}, expected 403 or 404")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check VilnaCRM SPA deployment delivery")
    parser.add_argument("--url", required=True, help="CRM site base URL")
    parser.add_argument("--staging", action="store_true", help="Use CloudFront continuous-deployment header")
    parser.add_argument("--deployment-manifest", help="Deployment manifest emitted by deploy_content.py")
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args(argv)
    try:
        check(args.url, args.staging, args.deployment_manifest, args.timeout)
    except (ValueError, AssertionError) as error:
        print(f"SPA deployment check failed: {error}", file=sys.stderr)
        return 1
    print("SPA deployment check passed: routes, shell, runtime config, and assets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
