# KingsmanConstruction

Kingsman Renovations Construction Inc.

## New architecture (frontend + backend split)

This repository now supports a **REST API backend** and a **GitHub Pages-friendly frontend** in separate folders:

- `backend/` → Flask backend exposing API endpoints to be merged/run alongside your Music app backend.
- `frontend/` → static site for GitHub Pages.
  - `frontend/index.html`
  - `frontend/login.html`
  - `frontend/signup.html`
  - `frontend/static/css/styles.css`
  - `frontend/static/js/main.js`
  - `frontend/static/js/auth.js`
  - `frontend/static/img/*.svg` (all frontend images/icons are text-based SVG assets)

---

## API prefix

Construction endpoints are namespaced under:

`/api/kingsman/v1`

Examples:

- `GET /api/kingsman/v1/health`
- `GET /api/kingsman/v1/services`
- `GET /api/kingsman/v1/jobs`
- `GET /api/kingsman/v1/jobs/<id>`
- `POST /api/kingsman/v1/contact`
- `POST /api/kingsman/v1/auth/login`
- `POST /api/kingsman/v1/auth/signup`

---

## Pattern A (Recommended for you): Merge Kingsman + Music School in ONE Flask app

You said you will use **Pattern A** and both apps use the **same DB host**. This section is the full merge playbook.

### Goal

Run one Flask server that serves both:

- Music School API (example prefix: `/api/music/v1`)
- Kingsman API (prefix: `/api/kingsman/v1`)

This avoids route interference by using different URL prefixes.

---

## 1) Copy Kingsman backend module into your Music app repo

Copy these folders/files from this repo into your Music School repo:

- `backend/`
  - `backend/__init__.py`
  - `backend/api/__init__.py`
  - `backend/api/routes.py`

If your Music app already has `config.py` and `db.py`, keep one source of truth there and adapt imports if needed.

---

## 2) Register Kingsman blueprint inside Music app factory

In your Music School app factory (example `create_app()`), register Kingsman API blueprint.

```python
from flask import Flask

# existing music imports...
# from music.api import music_bp

# kingsman import (after copying backend package)
from backend.api import api_bp as kingsman_api_bp


def create_app(config_object=None):
    app = Flask(__name__)

    # existing config setup...
    # app.config.from_object(config_object)

    # existing music routes/blueprints...
    # app.register_blueprint(music_bp, url_prefix="/api/music/v1")

    # register kingsman blueprint (already includes /api/kingsman/v1 prefix)
    app.register_blueprint(kingsman_api_bp)

    return app
```

> Important: do **not** re-prefix Kingsman blueprint during registration, because it already has `url_prefix="/api/kingsman/v1"`.

---

## 3) Keep one SQLAlchemy engine for the shared DB host

Because both apps use the same DB host, use one DB config in your host app and ensure Kingsman routes use the same engine.

Current Kingsman code imports `engine` from `db.py`. So in merged app, make sure:

- the active `db.py` points to your intended shared DB connection string,
- both Music and Kingsman code import that same engine.

If your Music app uses a different DB module name, update Kingsman imports in:

- `backend/api/routes.py`
- `backend/__init__.py` (for `ensure_schema`)

to reference your host app DB module.

---

## 4) Schema strategy (same DB host)

Kingsman app factory calls `ensure_schema()` to create required tables.

In merged Pattern A setup, pick one approach:

### Option A (simple):
Call `ensure_schema()` at app startup once (works for dev/small deploys).

### Option B (preferred in production):
Run schema/migrations in deployment pipeline and remove startup schema creation from request app startup.

---

## 5) CORS strategy when merged

If Music app already has global CORS handling, avoid duplicate/conflicting headers.

Kingsman currently adds permissive CORS via `after_request`. In merged app:

- either keep one centralized CORS layer for the whole app,
- or ensure duplicate headers are not overwritten incorrectly.

---

## 6) Final route map check (must pass)

After merging, verify both groups are live:

- Music API: `/api/music/v1/...`
- Kingsman API: `/api/kingsman/v1/...`

Quick checks:

- `GET /api/kingsman/v1/health`
- one known Music endpoint (example `/api/music/v1/health`)

---

## 7) Frontend integration (GitHub Pages)

For Kingsman frontend (`frontend/*.html`), set API base to merged host:

```html
<script>
  window.CONSTRUCTION_API_BASE = "https://YOUR_DOMAIN/api/kingsman/v1";
</script>
```

Place this before loading:

- `frontend/static/js/main.js`
- `frontend/static/js/auth.js`

---

## 8) Example production topology for Pattern A

- One Flask app process (Music + Kingsman blueprints)
- One reverse proxy (Nginx/Caddy)
- One DB host (shared)
- Distinct API prefixes:
  - `/api/music/v1`
  - `/api/kingsman/v1`

This is exactly how to avoid interference while sharing infrastructure.

---

## Run backend (standalone Kingsman, optional)

```bash
python backend/run.py
```

Backend default URL: `http://localhost:8000`

---

## Run frontend locally

From repo root:

```bash
python -m http.server 5500
```

Then open `http://localhost:5500/frontend/`

If backend is not on localhost:8000, set this before loading frontend pages:

```html
<script>
  window.CONSTRUCTION_API_BASE = "https://your-backend-host/api/kingsman/v1";
</script>
```
