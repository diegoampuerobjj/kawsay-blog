# Editor Views Reference — `editor/views.py`

## Overview

This document covers all views for the `editor` Django app: a **Markdown editor** (EasyMDE) with **version history**, **publish**, and **preview**. These views replaced the old `PostCreateView` and `PostUpdateView` from the `blog` app (those classes still exist in `blog/views.py` but are no longer wired in URLs).

The editor app follows a **versioned content** model:

```
Post (source of truth — always holds the latest content)
  └── PostVersion (immutable snapshots — append-only history)
```

Content is edited in the browser with **EasyMDE** and persisted only when the user submits the form (no server-side autosave).

---

## Table of Contents

1. [Imports Explained](#1-imports-explained)
2. [How Django Handles a Request (Under the Hood)](#2-how-django-handles-a-request-under-the-hood)
3. [Concepts That Transfer to Backend Engineering](#3-concepts-that-transfer-to-backend-engineering)
4. [Architecture: Create vs Edit Flow](#4-architecture-create-vs-edit-flow)
5. [EditorCreateView (CreateView)](#5-editorcreateview-createview)
6. [EditorUpdateView (UpdateView)](#6-editorupdateview-updateview)
7. [PublishView (View — POST only)](#7-publishview-view--post-only)
8. [VersionHistoryView (View — GET only)](#8-versionhistoryview-view--get-only)
9. [RestoreVersionView (View — POST only)](#9-restoreversionview-view--post-only)
10. [PreviewView (View — GET only)](#10-previewview-view--get-only)
11. [Frontend: EasyMDE in `editor.html`](#11-frontend-easymde-in-editorhtml)
12. [CBV Patterns Summary](#12-cbv-patterns-summary)
13. [Security Patterns](#13-security-patterns)
14. [Common Mistakes & Edge Cases](#14-common-mistakes--edge-cases)
15. [Quick Reference](#15-quick-reference)

---

## 1. Imports Explained

```python
import mistune
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic.edit import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from blog.models import Post
from blog.forms import PostForm
from .models import PostVersion
```

| Import | Purpose |
|--------|---------|
| `mistune` | Markdown → HTML for server-side preview |
| `HttpResponseRedirect` | Explicit redirect after custom `form_valid()` logic |
| `render`, `redirect`, `get_object_or_404` | Template responses, shortcuts, safe object lookup |
| `View` | Minimal CBV for actions without forms (publish, restore, preview) |
| `CreateView` / `UpdateView` | Generic CRUD with `ModelForm` |
| `LoginRequiredMixin` | Redirect unauthenticated users to login |
| `messages` | One-time flash messages (session-backed) |
| `timezone` | Timezone-aware dates for `published_at` |
| `PostForm` | Shared form from `blog/forms.py` |
| `PostVersion` | Version snapshots in `editor/models.py` |

---

## 2. How Django Handles a Request (Under the Hood)

You do not call `EditorUpdateView` directly. Django does this chain:

```
HTTP request
  → Middleware stack (security, session, CSRF, auth, …)
  → URL resolver (match path → view callable)
  → view callable = EditorUpdateView.as_view()  # factory created once at startup
  → dispatch(request, *args, **kwargs)
       → LoginRequiredMixin.dispatch  # redirect if anonymous
       → UpdateView.dispatch
            → routes to get() or post() by HTTP method
  → get() or post() runs (generic logic + your overrides)
  → HttpResponse (HTML, redirect, 404, …)
  → Middleware (reverse order)
  → HTTP response
```

### What `.as_view()` does

`path('posts/<slug:slug>/edit/', views.EditorUpdateView.as_view(), name='edit')` stores a **function** Django can call. On each request that function:

1. Instantiates `EditorUpdateView()`
2. Sets `request`, `args`, `kwargs` on the instance
3. Calls `dispatch()`, which picks `get` or `post`

Without `.as_view()`, you would pass a class and Django would not know how to run it.

### MRO and mixins

```python
class EditorUpdateView(LoginRequiredMixin, UpdateView):
```

Python’s **method resolution order (MRO)** walks left to right. `LoginRequiredMixin` runs before `UpdateView`, so auth is checked before any form handling. In larger codebases, mixin order is a common source of subtle bugs — always put security mixins first.

### Where the slug comes from

URL pattern: `posts/<slug:slug>/edit/`

Django passes `slug='my-post'` into `kwargs`. `UpdateView` uses it in `get_object()` (default: filter `Post` by `slug` from `slug_url_kwarg`).

---

## 3. Concepts That Transfer to Backend Engineering

These patterns appear in Django and in most web frameworks.

| Concept | In this app | Broader meaning |
|---------|-------------|-----------------|
| **Thin routing, fat domain** | URLs in `editor/urls.py`, logic in views/models | Separate transport (HTTP) from business rules |
| **Idempotent GET** | Version list, preview only read data | Safe to retry; caches and crawlers assume GET does not mutate |
| **POST for mutations** | Publish, restore, form save | State changes need CSRF and should not be bookmarkable |
| **Authorization in queries** | `author=request.user` in `get_object_or_404` | Do not load a resource then check ownership — filter in the DB query |
| **404 vs 403** | Wrong author → 404 | Avoid leaking whether a resource exists (enumeration) |
| **Transactional side effects** | Save post, then create `PostVersion` | In production you might wrap both in `transaction.atomic()` so they succeed or fail together |
| **Append-only history** | Restore creates v4 with v1’s content, never edits v1 | Audit logs, event sourcing, and version tables use the same idea |
| **Source of truth vs projections** | `Post` is live; `PostVersion` is history | Like “current row” vs “event log” in other systems |
| **Override hooks, not rewrite** | `form_valid()`, `get_form_kwargs()` | Framework provides a pipeline; you inject steps at extension points |

You do not need to memorize Django’s entire CBV hierarchy. Learn the **request → auth → handler → persistence → response** pipeline; Django’s class names are just labels on those steps.

---

## 4. Architecture: Create vs Edit Flow

### Create flow

```
Browser                          Django Server
  │                                  │
  ├─ GET /editor/posts/create/ ─────→│ EditorCreateView.get()
  │                                  │   → empty PostForm
  │←─ editor.html (EasyMDE empty) ───┤
  │                                  │
  ├─ POST /editor/posts/create/ ────→│ EditorCreateView.post()
  │  (multipart form)                │   → is_valid()?
  │                                  │   → form_valid():
  │                                  │        INSERT Post
  │                                  │        INSERT PostVersion v1
  │←─ redirect post-detail ──────────┤
```

- The post does not exist until POST succeeds.
- EasyMDE syncs markdown into the textarea on submit (see [§11](#11-frontend-easymde-in-editorhtml)).

### Edit flow

```
Browser                          Django Server
  │                                  │
  ├─ GET /editor/posts/<slug>/edit/ →│ EditorUpdateView.get()
  │                                  │   → get_object(Post)
  │                                  │   → PostForm(instance=post)
  │←─ editor.html (filled EasyMDE) ──┤
  │                                  │
  ├─ POST .../edit/ ────────────────→│ EditorUpdateView.post()
  │                                  │   → UPDATE Post
  │                                  │   → INSERT PostVersion vN+1
  │←─ redirect post-detail ──────────┤
```

- No background saves: draft state lives only in the browser until submit.
- Each successful save appends a new `PostVersion` (never overwrites old versions).

### URL map (`editor/urls.py`)

| Name | Path | View |
|------|------|------|
| `editor:create` | `/editor/posts/create/` | `EditorCreateView` |
| `editor:edit` | `/editor/posts/<slug>/edit/` | `EditorUpdateView` |
| `editor:publish` | `/editor/posts/<slug>/publish/` | `PublishView` |
| `editor:version-history` | `/editor/posts/<slug>/versions/` | `VersionHistoryView` |
| `editor:restore-version` | `/editor/posts/<slug>/versions/<n>/restore/` | `RestoreVersionView` |
| `editor:preview` | `/editor/posts/<slug>/preview/` | `PreviewView` |

---

## 5. EditorCreateView (CreateView)

```python
class EditorCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'editor/editor.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        self.object = form.save()
        PostVersion.objects.create(
            post=self.object,
            version_number=1,
            content=self.object.content,
            excerpt=self.object.excerpt,
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('post-detail', kwargs={'slug': self.object.slug})
```

### Request lifecycle for POST

| Step | What runs |
|------|-----------|
| 1 | `post()` on `ProcessFormView` → binds `PostForm` to `request.POST` / `FILES` |
| 2 | `form.is_valid()` — field validation, `clean_*` methods |
| 3 | `form_valid(form)` — your override (author, save, version, redirect) |
| 4 | If invalid → `form_invalid()` re-renders template with errors |

### Why not `super().form_valid(form)`?

Parent `CreateView.form_valid()` saves and redirects immediately. You need **between** save and redirect:

```
form.save()  →  PostVersion.objects.create()  →  redirect
```

### `form.instance` vs `self.object`

- **`form.instance`**: the `Post` being built (before or during save).
- **`self.object`**: set after `form.save()`; used by `get_success_url()` for `self.object.slug`.

Set `author` on `form.instance` before save so users cannot spoof ownership via the form.

### `get_form_kwargs()` — view to form bridge

Default kwargs: `{'data', 'files', 'instance'}`. Adding `'user'` lets `PostForm` filter categories to the current user without the form touching `request` (keeps forms testable and reusable).

---

## 6. EditorUpdateView (UpdateView)

```python
class EditorUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'editor/editor.html'

    def form_valid(self, form):
        self.object = form.save()
        latest = self.object.versions.first()
        new_vn = (latest.version_number + 1) if latest else 1
        PostVersion.objects.create(
            post=self.object,
            version_number=new_vn,
            content=self.object.content,
            excerpt=self.object.excerpt,
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('post-detail', kwargs={'slug': self.object.slug})
```

### CreateView vs UpdateView

| Aspect | CreateView | UpdateView |
|--------|------------|------------|
| `form.instance` | New `Post()` | Existing row from DB |
| SQL on save | `INSERT` | `UPDATE` |
| URL | No object id in path | `slug` in path → `get_object()` |
| Template | Same `editor/editor.html` | Same template (`object` set) |

### Version numbering

```python
latest = self.object.versions.first()  # ordering = ['-version_number']
new_vn = (latest.version_number + 1) if latest else 1
```

`related_name='versions'` on `PostVersion.post` gives `post.versions`. `.first()` is the highest version number. If no versions exist (edge case), start at `1`.

### No `get_initial()` override

The form is filled from `instance=post` only. There is no draft-recovery layer — what is in the database is what the user sees.

---

## 7. PublishView (View — POST only)

```python
class PublishView(LoginRequiredMixin, View):
    def post(self, request, slug):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        if not post.content.strip():
            messages.error(request, "Can't publish an empty post.")
            return redirect('editor:edit', slug=post.slug)
        if not post.published_at:
            post.published_at = timezone.now().date()
            post.save(update_fields=['published_at'])
        return redirect('post-detail', slug=post.slug)
```

### Why `View` instead of `UpdateView`?

`View.dispatch()` routes by HTTP method only — no form, no template. Good for **one action** (publish, restore, toggle).

### POST-only

No `get()` → browser GET returns **405 Method Not Allowed**. Publishing must be triggered by a form POST (see `editor.html`), not by visiting a URL.

### `update_fields=['published_at']`

Narrows the SQL `UPDATE` to one column — clearer intent and avoids clobbering other fields if concurrent edits exist.

### Idempotent publish

If `published_at` is already set, the view does nothing. Repeated POSTs are safe.

---

## 8. VersionHistoryView (View — GET only)

```python
class VersionHistoryView(LoginRequiredMixin, View):
    def get(self, request, slug):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        versions = post.versions.all()
        return render(request, 'editor/version_history.html', {
            'post': post,
            'versions': versions,
        })
```

Read-only listing. Restore is a separate POST endpoint (`RestoreVersionView`) — **read and write paths separated**, same idea as GET list + POST action in REST APIs.

`post.versions.all()` uses `Meta.ordering = ['-version_number']` on `PostVersion`.

---

## 9. RestoreVersionView (View — POST only)

```python
class RestoreVersionView(LoginRequiredMixin, View):
    def post(self, request, slug, version_number):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        version = get_object_or_404(PostVersion, post=post, version_number=version_number)
        latest = post.versions.first()
        new_vn = (latest.version_number + 1) if latest else 1
        PostVersion.objects.create(
            post=post,
            version_number=new_vn,
            content=version.content,
            excerpt=version.excerpt,
        )
        post.content = version.content
        post.excerpt = version.excerpt
        post.save(update_fields=['content', 'excerpt'])
        return redirect('editor:edit', slug=post.slug)
```

### Authorization chain

1. Post must exist and belong to `request.user`.
2. Version must belong to **that** post (`post=post` in the second lookup).

### Immutability

Restoring v1 does not edit v1. It creates v4 with v1’s content:

```
Before:  v1 → v2 → v3
After:   v1 → v2 → v3 → v4 (copy of v1)
```

History stays append-only; mistakes can be undone by restoring again.

---

## 10. PreviewView (View — GET only)

```python
class PreviewView(LoginRequiredMixin, View):
    def get(self, request, slug):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        html = mistune.html(post.content)
        return render(request, 'editor/preview.html', {
            'post': post,
            'html': html,
        })
```

Server-side Markdown matches your deployed rendering more closely than EasyMDE’s in-editor preview. Template uses `{{ html|safe }}` because `mistune` output is HTML — only safe here because content is your authenticated users’ posts; public untrusted input would need sanitization (e.g. `bleach`).

---

## 11. Frontend: EasyMDE in `editor.html`

EasyMDE wraps the content `<textarea>`. On submit, JavaScript copies the editor value back into the textarea so Django receives it in `request.POST`:

```javascript
const easyMDE = new EasyMDE({ element: document.getElementById('id_content'), ... });

document.getElementById('post-form').addEventListener('submit', function() {
  document.getElementById('id_content').value = easyMDE.value();
});
```

**Why this matters:** the server only sees standard form fields. The rich editor is a client-side UX layer; persistence is still a normal Django form POST (multipart for images).

EasyMDE is loaded from a CDN in `{% block extra_js %}` — no extra Python package.

---

## 12. CBV Patterns Summary

| Pattern | Base class | Overrides / methods | Example |
|---------|------------|---------------------|---------|
| Create with form | `CreateView` | `form_valid`, `get_form_kwargs`, `get_success_url` | `EditorCreateView` |
| Update with form | `UpdateView` | `form_valid`, `get_form_kwargs`, `get_success_url` | `EditorUpdateView` |
| Action (mutation) | `View` | `post()` only | `PublishView`, `RestoreVersionView` |
| Read-only page | `View` | `get()` only | `VersionHistoryView`, `PreviewView` |

### Templates

| View | Template |
|------|----------|
| `EditorCreateView` / `EditorUpdateView` | `editor/editor.html` |
| `VersionHistoryView` | `editor/version_history.html` |
| `PreviewView` | `editor/preview.html` |
| `PublishView`, `RestoreVersionView` | None (redirect) |

---

## 13. Security Patterns

### Filter by owner in the query

```python
post = get_object_or_404(Post, slug=slug, author=request.user)
```

### POST for state changes

| Action | Method |
|--------|--------|
| Create / update post | POST (form) |
| Publish | POST |
| Restore version | POST |
| Version list, preview | GET |

### Never put `author` in `PostForm.Meta.fields`

Ownership is set in `form_valid()` only, so clients cannot reassign posts via hidden inputs.

---

## 14. Common Mistakes & Edge Cases

### 1. Missing `author=request.user`

```python
# Wrong — any logged-in user could edit any slug they guess
post = get_object_or_404(Post, slug=slug)

# Right
post = get_object_or_404(Post, slug=slug, author=request.user)
```

### 2. Calling `super().form_valid()` when you need post-save logic

Save manually, run side effects, then `HttpResponseRedirect`.

### 3. Version `unique_together`

Duplicate `(post, version_number)` raises `IntegrityError`.

### 4. Concurrent edits

Two tabs saving at once can interleave version numbers. Fixes at scale: optimistic locking or `select_for_update`.

---

## 15. Quick Reference

| Goal | Override / approach |
|------|---------------------|
| Set fields before save | `form_valid()` — mutate `form.instance`, then `form.save()` |
| Logic after save, before redirect | `form_valid()` — no `super().form_valid()` |
| Pass `request.user` into form | `get_form_kwargs()` |
| Extra template variables | `get_context_data()` |
| Redirect target | `get_success_url()` |
| Simple GET/POST without form | `View` + `get()` / `post()` |
| Require login | `LoginRequiredMixin` first in bases |

---

## Related docs

- Blog views: `docs/blog_docs/views_reference.md`
- Per-user categories: `docs/blog_docs/per_user_category_uniqueness.md`
- Project overview: `readme.md`
