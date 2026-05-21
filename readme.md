# Kawsay Blog (Django)

Kawsay is a personal blog built with Django. Visitors browse public posts; authenticated authors manage content through a dedicated **editor** app with Markdown editing, version history, and preview.

## Apps

| App | Responsibility |
|-----|----------------|
| `blog` | Posts, categories, tags, comments, likes, public listing and detail |
| `accounts` | Registration, login/logout, profiles, password flows |
| `editor` | Markdown editor (EasyMDE), create/edit posts, versions, publish, preview |
| `project` | Settings, root URLs, shared templates and static files |

## Features

### Public

- Homepage and blog listing
- Post detail with comments and likes
- Categories and tags on posts

### Authenticated authors

- **Editor** (`/editor/…`) — create and edit posts with EasyMDE
- **Version history** — append-only snapshots on each save; restore creates a new version
- **Preview** — server-rendered Markdown (mistune)
- **Publish** — set `published_at` from the editor (POST action)
- Per-user categories (filtered in `PostForm`)
- Create categories/tags from the editor via `?next=` redirects
- Profile with avatar and post list

### Interaction

- Like/unlike per user (unique constraint)
- Threaded comments; authors or comment owners can delete
- Django admin for all core models

## Tech stack

- Python 3
- Django 6
- SQLite (development)
- Django templates + Bootstrap-style layout
- **EasyMDE** (Markdown editor, CDN)
- **mistune** (Markdown → HTML for preview)
- Pillow (featured images)
- Class-based views throughout

## Project structure

```
manage.py
project/          # settings, root urls, base templates, static/
blog/             # domain models, public views, post detail
accounts/         # auth and Profile
editor/           # editor views, PostVersion, templates
media/            # uploaded featured images
docs/
  blog_docs/      # blog views reference, category notes
  editor_docs/    # editor views reference (this app)
```

## Core models

**`blog`**

- `Category`, `Tag`, `Post`, `Comment`, `Like`

**`accounts`**

- `Profile` (display name, bio, website, avatar)

**`editor`**

- `PostVersion` — snapshot of `content` and `excerpt` per save (immutable history)

`Post` remains the live source of truth; versions are historical copies only.

## Main routes

| URL | Description |
|-----|-------------|
| `/` | Home |
| `/blog/` | Blog listing |
| `/blog/posts/<slug>/` | Post detail |
| `/blog/posts/<slug>/delete/` | Delete post (author) |
| `/blog/posts/<slug>/like/` | Toggle like |
| `/editor/posts/create/` | New post (editor) |
| `/editor/posts/<slug>/edit/` | Edit post (editor) |
| `/editor/posts/<slug>/versions/` | Version history |
| `/editor/posts/<slug>/preview/` | Markdown preview |
| `/editor/posts/<slug>/publish/` | Publish (POST) |
| `/accounts/register/`, `login/`, `logout/` | Auth |
| `/admin/` | Django admin |

Post create/edit URLs under `/blog/posts/…` were removed; use `/editor/…` instead.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install django pillow mistune
python3 manage.py migrate
python3 manage.py createsuperuser   # optional
python3 manage.py runserver
```

- Home: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/
- New post: http://127.0.0.1:8000/editor/posts/create/ (after login)

## Media and static

- Static: `project/static/`
- Uploads: `media/` (served in development when `DEBUG=True` via `project/urls.py`)

## Documentation

| Doc | Contents |
|-----|----------|
| [`docs/editor_docs/editor_views.md`](docs/editor_docs/editor_views.md) | Editor CBVs, request flow, security, EasyMDE |
| [`docs/blog_docs/views_reference.md`](docs/blog_docs/views_reference.md) | Blog app class-based views |
| [`docs/blog_docs/per_user_category_uniqueness.md`](docs/blog_docs/per_user_category_uniqueness.md) | Category ownership rules |

## Notes

- No `requirements.txt` in the repo yet; install `django`, `pillow`, and `mistune` as above.
- Default database: SQLite (`db.sqlite3`).
- Legacy `PostCreateView` / `PostUpdateView` remain in `blog/views.py` but are not registered in `blog/urls.py`.

Last updated: May 2026.
