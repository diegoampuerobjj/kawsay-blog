# Kawsay Blog (Django)

Kawsay is a personal blog web application built with Django. It includes a public-facing site for reading posts and a complete authenticated workflow for creating and managing blog content.

The project is organized into two core apps:

- `blog`: post publishing, categories, tags, comments, and likes
- `accounts`: registration, login/logout, and user profile model

## What this project is about

This app provides a simple but complete blogging platform where:

- Visitors can browse posts from the homepage and blog list
- Registered users can create, edit, and delete posts
- Users can like posts and leave comments
- Authors (or comment owners) can delete comments
- Content can be grouped with categories and tags
- Posts support featured images via media uploads

## Current features

- Authentication
	- User registration
	- Login/logout
	- Built-in Django password reset templates integrated
- Blog content
	- Post CRUD (create/read/update/delete)
	- Auto-generated slugs for posts, categories, and tags
	- Featured image upload support
	- Post listing and post detail views
- Interaction
	- Like/unlike toggle per user (unique like constraint)
	- Comment creation on post detail pages
	- Comment deletion permissions
- Organization
	- Categories and tags (with creation forms)
	- Admin registration for all core models

## Tech stack

- Python
- Django 6
- SQLite (default development database)
- Django templates + static CSS
- Media file handling for uploaded images
- Class-Based Views (migrated from Function-Based Views)

## Project structure

```
manage.py
project/     # Django project settings, root urls, shared templates/static
blog/        # Blog domain logic: models, views, forms, urls, templates
accounts/    # Authentication and profile features
media/       # Uploaded files (featured images)
docs/        # Project documentation (views reference, migration logs)
```

## Core models

From the current codebase:

- `Category`: name, slug, description
- `Tag`: name, slug
- `Post`: author, category, tags, title, slug, excerpt, content, featured image, publish dates
- `Comment`: post, user, parent, content, created date
- `Like`: post, user, created date (one like per user per post)
- `Profile` (accounts app): user profile info (display name, website, bio)

## Main routes

- `/` home page
- `/blog/` blog listing
- `/blog/posts/create/` create post (authenticated)
- `/blog/posts/<slug>/` post detail
- `/blog/posts/<slug>/edit/` edit post (authenticated)
- `/blog/posts/<slug>/delete/` delete post (authenticated)
- `/blog/posts/<slug>/like/` toggle like (authenticated)
- `/accounts/register/` registration
- `/accounts/login/` login
- `/accounts/logout/` logout
- `/admin/` Django admin

## Local setup

1. Clone the repository and move into the project folder.
2. Create and activate a virtual environment.
3. Install dependencies.
4. Run migrations.
5. Create an admin user (optional but recommended).
6. Start the development server.

Example commands:

```bash
python -m venv .venv
source .venv/bin/activate
pip install django pillow
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open in browser:

- Home: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`

## Media and static files

- Static files are served from `project/static/`
- Uploaded media is stored in `media/`
- In development, media serving is enabled through `project/urls.py` when `DEBUG=True`

## Notes

- No dependency lock file (`requirements.txt`, `pyproject.toml`, etc.) is currently present.
- The default database is SQLite (`db.sqlite3`).
- All views use Django Class-Based Views (CBVs) instead of Function-Based Views (FBVs).
- See `docs/views_reference.md` for detailed CBV documentation.
- This README reflects the current implementation as of 14 May 2026.
