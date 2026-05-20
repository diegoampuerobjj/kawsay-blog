# Editor Views Reference — `editor/views.py`

## Overview

This document covers all views for the `editor` Django app — the content editor with versioning and autosave. These views replace the old `PostCreateView` and `PostUpdateView` from the `blog` app.

The `editor` app follows a **versioned content** architecture:

```
Post (model — always holds the latest content)
  ├── PostVersion (list of snapshots — immutable history)
  └── PostAutosave (in-progress draft — overwritten each time)
```

---

## Table of Contents

1. [Imports Explained](#1-imports-explained)
2. [Architecture Overview: Create vs Edit Flow](#2-architecture-overview-create-vs-edit-flow)
3. [EditorCreateView (CreateView)](#3-editorcreateview-createview)
4. [EditorUpdateView (UpdateView)](#4-editorupdateview-updateview)
5. [AutosaveView (View — JSON)](#5-autosaveview-view--json)
6. [PublishView (View — POST only)](#6-publishview-view--post-only)
7. [VersionHistoryView (View — GET only)](#7-versionhistoryview-view--get-only)
8. [RestoreVersionView (View — POST only)](#8-restoreversionview-view--post-only)
9. [PreviewView (View — GET only)](#9-previewview-view--get-only)
10. [CBV Patterns Summary](#10-cbv-patterns-summary)
11. [Security Patterns](#11-security-patterns)
12. [Common Mistakes & Edge Cases](#12-common-mistakes--edge-cases)

---

## 1. Imports Explained

```python
import json
import mistune
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic.edit import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from blog.models import Post, Category
from blog.forms import PostForm
from .models import PostVersion, PostAutosave
```

| Import | Purpose |
|--------|---------|
| `json` | Parse JSON from `request.body` (autosave endpoint) |
| `mistune` | Convert Markdown to HTML (preview) |
| `JsonResponse` | Return JSON responses for API-like endpoints |
| `HttpResponseRedirect` | Explicit redirect (we use this instead of `super().form_valid()` in some views) |
| `View` | Base class for simple custom views (autosave, publish, preview) |
| `CreateView` | Generic view for creating model objects |
| `UpdateView` | Generic view for updating model objects |
| `messages` | Flash messages — one-time notifications shown on next page load |
| `timezone` | Timezone-aware datetime utilities |
| `PostForm` | Reused from `blog/forms.py` — the same form that was used in `post_form.html` |
| `PostVersion`, `PostAutosave` | The versioning models defined in `editor/models.py` |

### Why `HttpResponseRedirect` instead of `super().form_valid()`?

```python
# Pattern used in EditorCreateView and EditorUpdateView:
def form_valid(self, form):
    self.object = form.save()
    # ... create PostVersion ...
    return HttpResponseRedirect(self.get_success_url())
```

`form_valid()` in Django's generic CBV normally does:
```python
def form_valid(self, form):
    self.object = form.save()
    return HttpResponseRedirect(self.get_success_url())
```

By NOT calling `super()`, we take control of the save-and-redirect flow ourselves. This lets us insert logic **between** `form.save()` and the redirect — specifically, creating a `PostVersion` and, in the update case, clearing the autosave.

---

## 2. Architecture Overview: Create vs Edit Flow

### Create flow

```
Browser                          Django Server
  │                                  │
  ├─ GET /editor/posts/create/ ─────→│
  │                                  ├─ EditorCreateView.get()
  │                                  │   → empty PostForm
  │                                  │   → render editor.html (no slug)
  │←─ editor.html (EasyMDE empty) ───┤
  │                                  │
  │  [User types. Autosave → localStorage via JS]
  │                                  │
  ├─ POST /editor/posts/create/ ────→│
  │  (title, content, category, etc) │
  │                                  ├─ EditorCreateView.post()
  │                                  │   → form.is_valid()?
  │                                  │   → YES:
  │                                  │     → form.save() → INSERT Post
  │                                  │     → PostVersion.objects.create(v1)
  │                                  │     → redirect /blog/posts/<slug>/
  │←─ redirect to post-detail ───────┤
```

Key points:
- The Post does not exist in the database until the form is submitted.
- During creation, autosave is handled entirely in **localStorage** (JS) because there's no slug to send data to.
- The first `PostVersion` has `version_number=1`.

### Edit flow

```
Browser                          Django Server
  │                                  │
  ├─ GET /editor/posts/<slug>/edit/ →│
  │                                  ├─ EditorUpdateView.get()
  │                                  │   → get_object() → Post by slug
  │                                  │   → get_initial() → checks autosave
  │                                  │   → render editor.html (with slug)
  │←─ editor.html (EasyMDE with      │
  │    content loaded) ──────────────┤
  │                                  │
  │  [User types. Every 30s:]        │
  │  ┌─ POST /editor/posts/<slug>/   │
  │  │         autosave/ ───────────→│
  │  │   {content, excerpt}          ├─ AutosaveView.post()
  │  │                               │   → update_or_create PostAutosave
  │  │←─ {"status": "ok"} ──────────┤
  │  └───────────────────────────────┘
  │                                  │
  ├─ POST /editor/posts/<slug>/edit/→│
  │  (updated content, etc)          │
  │                                  ├─ EditorUpdateView.post()
  │                                  │   → form.is_valid()?
  │                                  │   → YES:
  │                                  │     → form.save() → UPDATE Post
  │                                  │     → PostVersion.objects.create(v2+)
  │                                  │     → PostAutosave.delete()
  │                                  │     → redirect /blog/posts/<slug>/
  │←─ redirect to post-detail ───────┤
```

Key points:
- The Post already exists (fetched by slug from URL).
- Autosave goes to the **server** via `fetch()` JSON every 30 seconds.
- After a successful save, the autosave is **deleted** to prevent stale draft recovery.

---

## 3. EditorCreateView (CreateView)

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

### How it works step by step

| Event | What happens |
|-------|-------------|
| `GET /editor/posts/create/` | `CreateView.get()` calls `get_form()` → creates empty `PostForm`. Since there's no instance yet, `form.instance` is `Post()`. Template renders with empty fields. |
| `POST` (form invalid) | `form.is_valid()` returns False. Same template re-rendered with `<div class="invalid-feedback">` errors. |
| `POST` (form valid) | `form_valid()` is called → see below |

### `form_valid()` — the creation pipeline

```python
def form_valid(self, form):
    form.instance.author = self.request.user   # 1
    self.object = form.save()                  # 2
    PostVersion.objects.create(...)             # 3
    return HttpResponseRedirect(...)           # 4
```

**Step 1 — `form.instance.author = self.request.user`**

`form.instance` is the `Post()` model instance that the form is building. Before saving, we set fields that the user should NOT control via the form:
- `author` — must be the logged-in user
- If there were timestamps that should be set programmatically, this is where

**Step 2 — `self.object = form.save()`**

`form.save()` does three things in order:
1. `self.object = form.instance` (sets the local reference)
2. `form.instance.save()` → executes `INSERT INTO blog_post (...) VALUES (...)` — the Post is now in the database with its auto-generated `slug` and `id`
3. `form.save_m2m()` → saves ManyToMany relationships (tags)

**Why NOT `super().form_valid(form)`?**

The parent `CreateView.form_valid()` does:
```python
def form_valid(self, form):
    self.object = form.save()
    return HttpResponseRedirect(self.get_success_url())
```

If we called `super()`, it would save the Post AND redirect immediately — we'd lose the chance to create the first `PostVersion`. By duplicating the two lines and adding our logic in between, we get:

```
form.save()  →  create PostVersion  →  redirect
```

**Step 3 — `PostVersion.objects.create(...)`**

Creates the first version snapshot. Key detail: we use `self.object.content` (not `form.cleaned_data['content']`).

Both would work, but `self.object.content` is the value that was actually written to the database — it went through Django's field processing (pre-save hooks, etc.). `form.cleaned_data` is the validated Python value before any model-level processing.

**Step 4 — `return HttpResponseRedirect(self.get_success_url())`**

`get_success_url()` calls `reverse('post-detail', kwargs={'slug': self.object.slug})`. The slug was auto-generated from the title in `Post.save()`.

### `get_form_kwargs()`

```python
def get_form_kwargs(self):
    kwargs = super().get_form_kwargs()
    kwargs['user'] = self.request.user
    return kwargs
```

This is how we inject extra parameters into the form constructor. The default `get_form_kwargs()` returns:
```python
{'data': request.POST, 'files': request.FILES, 'instance': None}
```

We add `user` to this dict. In `PostForm.__init__`, this is received as:
```python
def __init__(self, *args, **kwargs):
    user = kwargs.pop('user', None)
    super().__init__(*args, **kwargs)
    if user:
        self.fields['category'].queryset = Category.objects.filter(user=user)
```

The user is used to filter the category dropdown — each user only sees their own categories.

### Key concepts

| Concept | Explanation |
|---------|-------------|
| `form.instance` | The unsaved model object. Available BEFORE `form.save()` |
| `self.object` | The saved model object. Set AFTER `form.save()`. Needed by `get_success_url()` |
| `get_form_kwargs()` | The bridge between the view (which has `request`) and the form (which shouldn't touch `request`) |
| `get_success_url()` | Called AFTER save, so `self.object.pk` and `self.object.slug` exist |

### When to use CreateView

- You have a form that creates a model object
- The creation flow is standard: GET shows form, POST validates and creates
- You need to set fields programmatically (author, timestamps)

### When NOT to use CreateView

- You need confirmation before creating (use a simple View with two steps)
- The creation depends on an external service (payment, API call) — you need finer control
- You're not actually saving to the database

---

## 4. EditorUpdateView (UpdateView)

```python
class EditorUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'editor/editor.html'

    def get_initial(self):
        initial = super().get_initial()
        try:
            autosave = PostAutosave.objects.get(
                post=self.object, user=self.request.user
            )
            if autosave.updated_at > self.object.updated_at:
                initial['content'] = autosave.content
                initial['excerpt'] = autosave.excerpt
        except PostAutosave.DoesNotExist:
            pass
        return initial

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

        PostAutosave.objects.filter(
            post=self.object, user=self.request.user
        ).delete()

        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('post-detail', kwargs={'slug': self.object.slug})
```

### `get_initial()` — Draft recovery (autosave)

This is the first view hook that runs on GET. It populates the form fields with initial values **before** the model instance data is loaded.

The default `UpdateView.get_initial()` returns an empty dict `{}`. But `UpdateView` also calls `get_form()` which passes `instance=self.object` to the form. The form then loads the instance's data as initial values. So the flow is:

```
1. get_initial() → {'content': 'autosave text'}  (if autosave exists)
2. get_form() → PostForm(instance=post, initial={'content': 'autosave text'})
3. Form merges: instance data first, then initial overrides
```

**The merge rule:** `initial` values OVERRIDE the instance values. So if the autosave has different content, it wins.

**Why check `autosave.updated_at > self.object.updated_at`?**
- If the user saved the post successfully, the post is newer than the autosave → don't recover
- If the user was editing and the browser crashed, the autosave is newer than the post → recover

### `form_valid()` — Update + version + cleanup

```python
def form_valid(self, form):
    self.object = form.save()                            # 1
    latest = self.object.versions.first()                # 2
    new_vn = (latest.version_number + 1) if latest else 1  # 3
    PostVersion.objects.create(post=self.object,         # 4
                               version_number=new_vn, ...)
    PostAutosave.objects.filter(...).delete()             # 5
    return HttpResponseRedirect(...)                     # 6
```

**Step 1 — `form.save()`**

For an `UpdateView`, `form.instance` is the **existing** Post. `form.save()` calls `form.instance.save()` which executes `UPDATE blog_post SET ... WHERE id=...` — it modifies the existing row, does NOT create a new one.

**Steps 2-3 — Auto-increment version_number**

```python
latest = self.object.versions.first()
new_vn = (latest.version_number + 1) if latest else 1
```

`self.object.versions` is the RelatedManager (from `related_name='versions'` in `PostVersion.post`). With `ordering = ['-version_number']`, `.first()` is the highest version number.

If the post has versions 1, 2, 3 → `latest.version_number = 3` → `new_vn = 4`

**Edge case:** If for some reason the post has no versions (data corruption, migration issue), `latest` is `None` → `new_vn = 1`.

**Step 4 — Create the new version**

We use `self.object.content` (the value just saved to the database) as the version content.

**Step 5 — Delete autosave**

After a successful save, the autosave is stale. If we didn't delete it, the next time the user opens the editor, `get_initial()` would find an autosave and try to recover it — even though the user intentionally saved. By deleting it, we ensure that only unsaved drafts trigger recovery.

### UpdateView vs CreateView: Key differences

| Aspect | CreateView | UpdateView |
|--------|-----------|------------|
| `form.instance` | `Post()` (new) | `Post.objects.get(slug=...)` (existing) |
| `form.save()` SQL | `INSERT` | `UPDATE` |
| `get_initial()` | Empty or defaults | Can override model data |
| URL parameter | None needed | Needs slug or pk |

### When to use UpdateView

- Same as CreateView, but for EXISTING objects
- The URL contains an identifier (slug, pk) to fetch the object
- You want to pre-fill the form with current values

---

## 5. AutosaveView (View — JSON)

```python
class AutosaveView(LoginRequiredMixin, View):
    def get(self, request, slug):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        autosave, created = PostAutosave.objects.get_or_create(
            post=post, user=request.user,
            defaults={'content': post.content, 'excerpt': post.excerpt}
        )
        return JsonResponse({
            'content': autosave.content,
            'excerpt': autosave.excerpt,
            'updated_at': autosave.updated_at.isoformat(),
        })

    def post(self, request, slug):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        data = json.loads(request.body)

        PostAutosave.objects.update_or_create(
            post=post, user=request.user,
            defaults={
                'content': data.get('content', ''),
                'excerpt': data.get('excerpt', ''),
            }
        )
        return JsonResponse({'status': 'ok'})
```

### Why `View` and not `CreateView`/`UpdateView`?

`View` is the most basic class-based view. It does ONE thing: routes HTTP methods.

```python
class View:
    def dispatch(self, request, *args, **kwargs):
        handler = getattr(self, request.method.lower(), None)
        if handler is None:
            return HttpResponseNotAllowed(...)
        return handler(request, *args, **kwargs)
```

That's it. If you define `get()`, it handles GET. If you define `post()`, it handles POST. No forms, no models, no templates.

**When to use View:**
- JSON endpoints (like this autosave)
- Simple actions (like/unlike, delete)
- Any case where you don't need Django's generic CRUD machinery

### GET flow — `get_object_or_404` + `get_or_create`

```python
post = get_object_or_404(Post, slug=slug, author=request.user)
```

**Three things in one line:**
1. `Post.objects.get(slug=slug, author=request.user)` — query the database
2. If no match → `raise Http404` (returns 404 page)
3. If match → returns the Post object

**The `author=request.user` filter is AUTHORIZATION:**
- Users can only autosave their OWN posts
- If the post exists but belongs to another user, the request gets a 404 (not 403 — we don't reveal the post exists)

```python
autosave, created = PostAutosave.objects.get_or_create(
    post=post, user=request.user,
    defaults={'content': post.content, 'excerpt': post.excerpt}
)
```

**`get_or_create` explained:**
1. Try `PostAutosave.objects.get(post=post, user=request.user)`
2. If found → return `(object, False)`
3. If NOT found → create one with the `defaults` + the lookup fields → return `(new_object, True)`

**The `created` variable:**
- `True` if a new autosave was created (first time opening the editor)
- `False` if the autosave already existed (returning to an ongoing edit)

**Why `defaults={'content': post.content}`?**
When creating a fresh autosave for a post that has never been autosaved, seed it with the post's current content. This prevents the autosave from being empty on first access.

### POST flow — `json.loads(request.body)` + `update_or_create`

```python
data = json.loads(request.body)
```

The JavaScript client sends:
```javascript
fetch(`/editor/posts/${slug}/autosave/`, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify({content: easyMDE.value(), excerpt: excerptValue}),
});
```

`request.body` contains the raw bytes of the request. `json.loads()` parses them into a Python dict.

**Why not `request.POST`?**
- `request.POST` only works with form-encoded data (`Content-Type: application/x-www-form-urlencoded` or `multipart/form-data`)
- Our fetch sends JSON (`Content-Type: application/json`)
- Django does NOT parse JSON bodies automatically — you must do it yourself

```python
PostAutosave.objects.update_or_create(
    post=post, user=request.user,
    defaults={
        'content': data.get('content', ''),
        'excerpt': data.get('excerpt', ''),
    }
)
```

**`update_or_create` explained:**
1. Try `PostAutosave.objects.get(post=post, user=request.user)`
2. If found → update its `content` and `excerpt` with `defaults`
3. If NOT found → create one with the lookup fields + defaults

**Difference from `get_or_create`:**
- `get_or_create`: only creates if missing, never updates
- `update_or_create`: updates if exists, creates if missing

### CSRF and JSON endpoints

Django's CSRF middleware requires a CSRF token for any non-GET request from authenticated users. When sending JSON via `fetch()`, you must include the token as a header:

```javascript
// Get token from cookie
function getCookie(name) {
    let value = `; ${document.cookie}`;
    let parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

fetch(url, {
    method: 'POST',
    headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
});
```

**Why this works:** Django's CSRF middleware checks for the token in this order:
1. `request.META['CSRF_COOKIE']` (the cookie)
2. `request.META['HTTP_X_CSRFTOKEN']` (the header)
3. `request.POST['csrfmiddlewaretoken']` (form field)

If the header matches the cookie, the request passes CSRF validation.

---

## 6. PublishView (View — POST only)

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

### Why POST-only with no GET handler?

Only `post()` is defined — no `get()`. If someone navigates to `/editor/posts/my-post/publish/` in their browser (a GET request), Django's `View.dispatch()` tries to call `self.get()`, which doesn't exist, and returns **405 Method Not Allowed**.

This is intentional:
- Publishing is an **action** (changes state), not a page
- Actions should only be triggered via POST (submitting a form or JS request)
- GET requests should be idempotent — visiting a URL should never change data

### Guard clause: empty post

```python
if not post.content.strip():
    messages.error(request, "Can't publish an empty post.")
    return redirect('editor:edit', slug=post.slug)
```

This prevents publishing a post with no content. `strip()` removes whitespace — so a post with just spaces is also rejected.

`messages.error()` stores a message in the session. On the next page load (the redirect to the editor), the template can show it:
```html
{% if messages %}
    {% for message in messages %}
        <div class="alert alert-{{ message.tags }}">{{ message }}</div>
    {% endfor %}
{% endif %}
```

### Idempotent publish

```python
if not post.published_at:
    post.published_at = timezone.now().date()
```

If the post is already published (`published_at` is set), we do nothing. This makes the endpoint **idempotent** — calling it 10 times has the same effect as calling it once.

### `update_fields=['published_at']`

```python
post.save(update_fields=['published_at'])
```

Without `update_fields`, `post.save()` would execute:
```sql
UPDATE blog_post SET author=..., title=..., content=..., published_at=..., ... WHERE id=1;
```

With `update_fields=['published_at']`:
```sql
UPDATE blog_post SET published_at='2026-05-19' WHERE id=1;
```

**Why this matters:**
- Performance: only sends one field over the wire
- Safety: won't accidentally overwrite `content` if another request modified it between read and write
- Intent: makes the code self-documenting — "I only intend to change published_at"

### `timezone.now().date()`

`timezone.now()` → aware datetime with timezone from `settings.TIME_ZONE`
`.date()` → extracts just the date part (strips time)

`published_at` is a `DateField` (not `DateTimeField`), so we need a date.

---

## 7. VersionHistoryView (View — GET only)

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

### Why only GET?

This is a read-only page. No POST handler — you can only view, not modify. Actions (like restoring) have their own POST endpoint (`RestoreVersionView`).

### `post.versions.all()`

`versions` is the `related_name` defined in `PostVersion.post`:
```python
class PostVersion(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='versions')
```

`post.versions` is a RelatedManager. Equivalent to:
```python
PostVersion.objects.filter(post=post)
```

But the RelatedManager also respects the model's `ordering`:
```python
class Meta:
    ordering = ['-version_number']
```

So `post.versions.all()` returns versions newest-first without needing `.order_by()`.

### Template context

The template receives:
- `post` — the Post object (for the heading, back link, etc.)
- `versions` — QuerySet of PostVersion objects, newest first

In the template:
```html
{% for version in versions %}
    <tr>
        <td>v{{ version.version_number }}</td>
        <td>{{ version.created_at|date:"M d, Y H:i" }}</td>
        <td>{{ version.excerpt|truncatewords:20 }}</td>
        <td>
            <form method="POST" action="{% url 'editor:restore-version' post.slug version.version_number %}">
                {% csrf_token %}
                <button type="submit">Restore</button>
            </form>
        </td>
    </tr>
{% endfor %}
```

---

## 8. RestoreVersionView (View — POST only)

```python
class RestoreVersionView(LoginRequiredMixin, View):
    def post(self, request, slug, version_number):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        version = get_object_or_404(PostVersion, post=post, version_number=version_number)

        latest = post.versions.first()
        new_vn = (latest.version_number + 1) if latest else 1

        PostVersion.objects.create(
            post=post, version_number=new_vn,
            content=version.content, excerpt=version.excerpt,
        )

        post.content = version.content
        post.excerpt = version.excerpt
        post.save(update_fields=['content', 'excerpt'])

        return redirect('editor:edit', slug=post.slug)
```

### Two `get_object_or_404` calls — authorization chain

```python
post = get_object_or_404(Post, slug=slug, author=request.user)
version = get_object_or_404(PostVersion, post=post, version_number=version_number)
```

**First call:** Verifies the post exists AND belongs to the current user. If either is false → 404.

**Second call:** Verifies the version exists AND belongs to that specific post. The `post=post` filter is critical — without it, a user could try `version_number=999999` and possibly access another post's version (though the version_number would likely not collide, it's still a security hole).

**The chain ensures:**
- You can only restore versions of your own posts
- You can only restore versions that actually belong to that post

### Immutability — why create a NEW version

When you "restore" version 1, we do NOT modify version 1. Instead, we create a NEW version with version 1's content:

```
Before:  v1 → v2 → v3
After:   v1 → v2 → v3 → v4 (content = v1's content)
```

This preserves the full history:
- If the restore was a mistake, you can restore AGAIN to go back
- The history graph shows what happened: "v4 is a restore of v1"
- No data is ever lost

### Updating `post.content` and `post.excerpt`

```python
post.content = version.content
post.excerpt = version.excerpt
post.save(update_fields=['content', 'excerpt'])
```

The restored content is immediately visible on the post's detail page. This is what makes the restore "real" — it's not just a version entry, the actual post content changes.

---

## 9. PreviewView (View — GET only)

```python
import mistune

class PreviewView(LoginRequiredMixin, View):
    def get(self, request, slug):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        html = mistune.html(post.content)
        return render(request, 'editor/preview.html', {
            'post': post,
            'html': html,
        })
```

### Server-side Markdown rendering

```python
html = mistune.html(post.content)
```

`mistune` is a Python Markdown parser. It converts:
```
# Hello\n\nThis is **bold** text.
```
Into:
```html
<h1>Hello</h1>
<p>This is <strong>bold</strong> text.</p>
```

**Why server-side preview when EasyMDE has client-side preview?**
- Client-side preview (EasyMDE) shows what the Markdown looks like generically
- Server-side preview shows what the post will look like with YOUR CSS and layout
- You can share the preview URL with someone who doesn't have access to the editor

### The `|safe` filter

In the template:
```html
<section class="post-content">
    {{ html|safe }}
</section>
```

Django auto-escapes ALL template variables by default. Without `|safe`, the HTML would appear as literal text:
```html
&lt;h1&gt;Hello&lt;/h1&gt;
```

`|safe` marks the string as "safe HTML" — Django won't escape it.

**Security note:** `|safe` is only safe because:
1. We control the Markdown content (it's our own posts)
2. The content was entered through our authenticated editor
3. If users could submit arbitrary content, you'd need to sanitize with `bleach` first

---

## 10. CBV Patterns Summary

### Pattern reference

| Pattern | Base Class | Methods You Override | Use Case |
|---------|-----------|---------------------|----------|
| **Create form** | `CreateView` | `form_valid()`, `get_form_kwargs()`, `get_success_url()` | EditorCreateView |
| **Update form** | `UpdateView` | `form_valid()`, `get_initial()`, `get_form_kwargs()`, `get_success_url()` | EditorUpdateView |
| **JSON action** | `View` | `get()`, `post()` | AutosaveView (JSON in/out) |
| **Simple action** | `View` | `post()` only | PublishView, RestoreVersionView |
| **Read-only page** | `View` | `get()` only | VersionHistoryView, PreviewView |

### Inheritance hierarchy

```
View
├── LoginRequiredMixin + CreateView  → EditorCreateView
├── LoginRequiredMixin + UpdateView  → EditorUpdateView
├── LoginRequiredMixin + View        → AutosaveView
├── LoginRequiredMixin + View        → PublishView
├── LoginRequiredMixin + View        → VersionHistoryView
├── LoginRequiredMixin + View        → RestoreVersionView
└── LoginRequiredMixin + View        → PreviewView
```

### Template mapping

| View | Template |
|------|----------|
| `EditorCreateView` | `editor/editor.html` |
| `EditorUpdateView` | `editor/editor.html` (same template) |
| `AutosaveView` | No template (returns JSON) |
| `PublishView` | No template (redirects) |
| `VersionHistoryView` | `editor/version_history.html` |
| `RestoreVersionView` | No template (redirects) |
| `PreviewView` | `editor/preview.html` |

---

## 11. Security Patterns

### Pattern 1: Always filter by user

Every view that accesses a Post uses:
```python
post = get_object_or_404(Post, slug=slug, author=request.user)
```

Without `author=request.user`, User A could:
- Autosave User B's drafts
- Publish User B's posts
- Restore/delete User B's versions
- View User B's editor/preview

### Pattern 2: POST-only for state changes

| Action | Method | Why |
|--------|--------|-----|
| Publish | POST | Changes state (published_at) |
| Restore version | POST | Changes state (creates version, updates post) |
| Autosave save | POST | Changes state (writes to DB) |
| View versions | GET | Read-only |
| View preview | GET | Read-only |
| Autosave read | GET | Read-only |

### Pattern 3: Don't reveal existence

Using 404 instead of 403:
```python
post = get_object_or_404(Post, slug=slug, author=request.user)
```

If the post exists but belongs to another user, the request gets a 404 ("Not Found"). Not a 403 ("Forbidden"). This way, an attacker can't brute-force slugs to discover which posts exist.

### Pattern 4: CSRF protection

JSON endpoints receive the CSRF token via the `X-CSRFToken` header. This is automatic — Django's CSRF middleware checks both form tokens and header tokens.

Template-rendered forms include `{% csrf_token %}` which generates a hidden input.

---

## 12. Common Mistakes & Edge Cases

### 1. Forgetting `author=request.user` in `get_object_or_404`

```python
# WRONG — any authenticated user can access any post
post = get_object_or_404(Post, slug=slug)

# RIGHT — only the author can access
post = get_object_or_404(Post, slug=slug, author=request.user)
```

### 2. `get_initial()` vs `initial` in the form class

```python
# In the VIEW — per-request, has access to request.user, self.object
def get_initial(self):
    initial = super().get_initial()
    # dynamic logic here
    return initial

# In the FORM CLASS — defined once, no access to request
class PostForm(forms.ModelForm):
    title = forms.CharField(initial='Untitled')  # static default only
```

### 3. Calling `super().form_valid()` when you need to add logic after save

```python
# WRONG — creates PostVersion AFTER the redirect has already been sent
def form_valid(self, form):
    form.instance.author = self.request.user
    return super().form_valid(form)  # This redirects immediately!

# RIGHT — save manually, add logic, redirect yourself
def form_valid(self, form):
    form.instance.author = self.request.user
    self.object = form.save()
    PostVersion.objects.create(...)  # This runs BEFORE the redirect
    return HttpResponseRedirect(self.get_success_url())
```

### 4. `form.save()` vs `form.save(commit=False)`

```python
# commit=False: creates model instance but does NOT write to DB
instance = form.save(commit=False)
instance.author = request.user
instance.save()  # Now it's written

# commit=True (default): saves immediately
instance = form.save()  # Already in the database
```

We use the first pattern. `commit=False` gives us a chance to set `author` before the instance is written to the database.

### 5. Autosave race condition

If the user submits the form at the same time an autosave fires:
```
JS: autosave POST → Server saves autosave
JS: form POST → Server saves Post + deletes autosave
```

The autosave arrives first, then the form save deletes it. Clean.

But if order reverses:
```
JS: form POST → Server saves Post + deletes autosave
JS: autosave POST → Server saves autosave (with OLD data)
```

Now there's a stale autosave. On next edit, `get_initial()` finds an autosave that's newer than the post. This is acceptable for autosave — worst case, the user sees a "Restore draft?" prompt with slightly outdated content.

### 6. No `author=request.user` in the form's `fields`

The `PostForm.Meta.fields` does NOT include `author`. This is intentional:
- If `author` were in the fields, the user could set it via a hidden input
- By omitting it, `author` can only be set server-side in `form_valid()`

**Rule:** Never include ownership/authorization fields in `fields`. Always set them programmatically.

### 7. `get_object_or_404` with filter kwargs

```python
# Raises Http404 if slug doesn't match
get_object_or_404(MyModel, slug=slug)

# Also raises Http404 if the model doesn't have a matching field
# This fails silently — no error if field doesn't exist
get_object_or_404(MyModel, slug=slug, nonexistent_field=value)  # Error!
```

### 8. `json.loads(request.body)` vs `request.POST`

`request.POST` only works with form-encoded data. If your client sends JSON:
```javascript
fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({key: 'value'}),
});
```

Then `request.POST` is empty. You MUST use `json.loads(request.body)`.

### 9. Version number collision

The `unique_together = ['post', 'version_number']` constraint prevents two versions with the same number for the same post. If somehow the auto-increment logic fails (unlikely, since we always use `latest + 1`), Django will raise an `IntegrityError`. This is a safety net — equivalent to a database-level assertion.

---

## Quick Reference: When to Override What

| You want to... | Override this method |
|---------------|---------------------|
| Set a field before save (author) | `form_valid()` — modify `form.instance` before `form.save()` |
| Add logic after save but before redirect | `form_valid()` — call `form.save()` manually, add logic, then redirect |
| Pass extra data from request to form | `get_form_kwargs()` — add to the kwargs dict |
| Pre-fill form fields with non-model data | `get_initial()` — return dict of field: value |
| Add variables to the template | `get_context_data()` — add to context dict |
| Control where to redirect after success | `get_success_url()` — return a URL using `reverse()` |
| Handle just GET and POST with no form | Use `View` and define `get()` / `post()` |
| Return JSON instead of HTML | Use `View` + `JsonResponse` |
