# Per-User Category Uniqueness

## The Problem

When categories were made per-user (each user sees only their own categories), a new user trying to create a category with the same name as an existing one would get:

```
IntegrityError at /blog/categories/create/
UNIQUE constraint failed: blog_category.slug
```

The `Category.slug` field had `unique=True` — a **global** uniqueness constraint at the database level. This meant no two categories in the entire table could share a slug, even if they belonged to different users.

## What Was Changed

### Model (`blog/models.py`)

**Before:**
```python
slug = models.SlugField(unique=True, max_length=100, blank=True)
```

**After:**
```python
slug = models.SlugField(max_length=100, blank=True)

class Meta:
    constraints = [
        models.UniqueConstraint(fields=['user', 'slug'], name='unique_user_category_slug'),
        models.UniqueConstraint(fields=['user', 'name'], name='unique_user_category_name'),
    ]
```

### Two changes made:

1. **Removed `unique=True`** from the `slug` field — this lifts the global uniqueness.
2. **Added two `UniqueConstraint`s** in `Meta.constraints` — these create composite (multi-column) uniqueness.

## How It Works Under the Hood

### Database Level

`unique=True` on a single field creates a **single-column unique index**:
```sql
CREATE UNIQUE INDEX "blog_category_slug_key" ON "blog_category"("slug");
```

A `UniqueConstraint(fields=['user', 'slug'])` creates a **composite unique index**:
```sql
CREATE UNIQUE INDEX "unique_user_category_slug" ON "blog_category"("user_id", "slug");
```

The difference:
- **Single-column**: Only `slug` is checked. `slug = "technology"` can only appear once in the whole table.
- **Composite**: The pair `(user_id, slug)` must be unique. User A can have `("technology", 1)` and User B can have `("technology", 2)` — they're different rows because `user_id` differs.

### Django ORM Level

Django's `ModelForm` (used by `CreateView`) calls `Model.validate_unique()` during form validation. Since Django 4.1+, `validate_unique()` checks `Meta.constraints` — including `UniqueConstraint`. When a user submits a duplicate name, `validate_unique()` raises a `ValidationError` before the SQL is ever executed. The user sees a clean form error like *"Category with this Name already exists."* instead of a 500 error page.

### Why a Data Migration Was Needed

Before these changes, there was 1 legacy category with `user=NULL` (created before the `user` field existed). If we applied the `UniqueConstraint` on `(user, name)` without deleting it, there would be potential issues:
- The old global slug uniqueness prevented slug collisions, but names could theoretically collide.
- The constraint would allow multiple NULL-user rows with the same name (most databases treat NULLs as distinct in unique constraints).

A `RunPython` step was added to migration `0006` to delete orphaned categories with no user, keeping the data clean.

## Lessons Learned

### 1. Think about scope early

`unique=True` seems like the obvious choice — but it's global by default. Always ask: *"Unique across what scope?"* If the answer is "per user" or "per project" or "per tenant", you need a composite constraint, not a single-field one.

### 2. Database constraints vs. Python-level validation

| Approach | Enforced at | Race condition safe? |
|---|---|---|
| `unique=True` / `UniqueConstraint` | Database level — always enforced | Yes — ACID guarantee |
| `validate_unique()` / `clean()` | Python level — only if called | No — TOCTOU bug possible |
| `get_or_create()` | Python + DB | Partially — can mask intent |

**Rule of thumb**: Always enforce at the database level. Python validation is for user-friendly error messages; DB constraints are for data integrity.

### 3. Migrations with data cleanup

When a schema migration has preconditions (e.g., "delete old records before adding a constraint"), include a `RunPython` step **before** the schema operations in the same migration. This keeps the migration atomic — if the data cleanup fails, the schema doesn't change.

### 4. Django's `Meta.constraints` is the modern way

Django introduced `Meta.constraints` in 2.2 and has been expanding its capabilities. The `UniqueConstraint` class supports:
- `fields` — the columns to enforce uniqueness on
- `name` — a stable name for the constraint (important for migrations)
- `condition` — a `Q` object for partial unique constraints (Django 3.0+)
- `deferrable` — for deferred constraint checking (PostgreSQL, Django 3.1+)

## Going Deeper: Ways to Keep Learning

### Database Indexing & Constraints

- **PostgreSQL docs**: [Unique Indexes](https://www.postgresql.org/docs/current/indexes-unique.html), [Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html) — the gold standard reference.
- **Use `EXPLAIN ANALYZE`** to see how the database uses unique indexes for lookups vs. enforcement.
- **Learn about partial unique indexes**: `CREATE UNIQUE INDEX ... WHERE user_id IS NOT NULL` — allows NULL-user duplicates while enforcing for non-null users. Django supports this via `UniqueConstraint(condition=Q(user__isnull=False))`.

### Django-Specific

- **Django docs**: [Models — Constraints](https://docs.djangoproject.com/en/stable/ref/models/constraints/)
- **Django docs**: [Validating objects](https://docs.djangoproject.com/en/stable/ref/models/instances/#validating-objects) — how `full_clean()`, `validate_unique()`, and form validation interact.
- **Source code**: `django.db.models.constraints` and `django.db.models.base.Model.validate_unique()` — reading the source is the fastest way to understand the boundary between Python validation and DB enforcement.

### Practical experiments to try

1. **Test race conditions**: Open two shell sessions, pause at the same `save()` call (use `import pdb; pdb.set_trace()`), and submit from both. See whether Python-only validation or DB constraints catch the duplicate.

2. **Compare constraint types**:
   - `unique_together` (legacy) vs. `UniqueConstraint` (modern) — both generate the same SQL, but constraints support additional features.
   - `db_index=True` vs. `unique=True` vs. `UniqueConstraint` — understand what's an index, what's a constraint, and when to use each.

3. **Add a partial unique constraint**: Try `UniqueConstraint(fields=['user', 'slug'], condition=Q(user__isnull=False))` — this lets you have multiple NULL-user categories with the same slug while still enforcing per-user uniqueness.

4. **Observe the SQL**: Watch the actual SQL Django generates by adding `'loggers': {'django.db.backends': {'level': 'DEBUG'}}` to `LOGGING` in settings. Compare before and after the migration.

### Books & Resources

- **"High Performance MySQL" / "PostgreSQL: Up and Running"** — chapters on indexing and constraints.
- **"Database Design for Mere Mortals"** — conceptual foundation for uniqueness, normalization.
- **Use `sqlite3` / `psql` directly** to create tables, insert rows, and see how each constraint type behaves on violation. Hands-on is better than reading.
