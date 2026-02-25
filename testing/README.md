# Testing Layout

This folder contains manual/automation testing assets split by platform:

- `web/` – comprehensive Selenium + HTTP test suite for sanity, main flow, regression, performance, and security checks.
- `android/` – placeholder for Android test plans / Appium suites.
- `ios/` – placeholder for iOS test plans / XCUITest/Appium suites.

## Web Test Coverage

`testing/web/full_website_test.py` includes:

- **Sanity checks**: home page and key public pages.
- **Main frame checks**: critical navigation journey and key forms.
- **Regression checks**: protected routes/auth behavior, internal-link stability, role login smoke checks.
- **Performance checks**: page and API response-time budgets, p95 and concurrent API health checks.
- **Security checks**: sensitive-file exposure, suspicious query handling, invalid login payload rejection, common header presence, and unsafe HTTP method checks.

## Quick Start

1. Start the MusicSchool web app locally.
2. Install Selenium dependencies:
   ```bash
   pip install selenium webdriver-manager
   ```
3. Run the suite:
   ```bash
   python testing/web/full_website_test.py --base-url http://127.0.0.1:5000 --headless
   ```

## Useful Runtime Flags

- `--timeout 20` for Selenium wait timeout.
- `--http-timeout 10` for HTTP/API timeout.
- `--page-threshold-ms 2500` for page performance budget.
- `--api-threshold-ms 1200` for API performance budget.
- `--perf-samples 7` for repeated performance sampling.
- `--headed` to run browser tests in visible mode.
- `--chromedriver-path /path/to/chromedriver` to use a custom driver.

## Optional Role Login Coverage

Set these environment variables if you want role-based login smoke tests to run:

- `TEST_STUDENT_EMAIL`, `TEST_STUDENT_PASSWORD`
- `TEST_TEACHER_EMAIL`, `TEST_TEACHER_PASSWORD`
- `TEST_ADMIN_EMAIL`, `TEST_ADMIN_PASSWORD`

If missing, login smoke tests are skipped automatically.
