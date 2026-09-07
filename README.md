# PulseBoard — Django intermediate → advanced, ek chalte hue project me

Multi-tenant task + time-tracking app with a reporting API. Har file ek ya do
Django concepts ko *use karke* sikhati hai — tutorial code nahi, kaam ka code hai.

**22 tests pass hote hain. Sab kuch chalta hua verify kiya gaya hai.**

**Requires Python 3.12+.** Tested on Django 6.1.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_demo --orgs 1 --projects 3 --tasks 30 --flush
python manage.py daily_rollup --days 14
python manage.py test
python manage.py runserver
```

Login: `owner@example.com` / `demo12345`

| URL | Kya dikhata hai |
|---|---|
| `/admin/` | Admin customisation, inlines, actions, proxy model |
| `/reports/projects/?org=org-1` | CBV + custom template tags + annotated report |
| `/projects/1/` | DetailView, window functions, burndown |
| `/projects/1/pulse/` | **Async view** + `asyncio.gather` |
| `/api/projects/` | DRF ViewSet, tenant scoping, annotations |
| `/api/projects/1/burndown/?days=7` | `@action` custom route |
| `/api/tasks/1/move/` | Service layer + domain errors |

Har response pe `X-Query-Count` header aata hai — N+1 turant dikh jaata hai.

---

## Tumhare stack se mapping

| Bun/Hono/Prisma | Django |
|---|---|
| Prisma `include` | `select_related` (JOIN) / `prefetch_related` (2nd query) |
| Prisma `$transaction` | `transaction.atomic()` + `select_for_update()` |
| Zod schema | DRF Serializer + `validate_*()` |
| Hono middleware | Callable class, `__call__(request)` |
| BullMQ worker | Management command + Celery beat / cron |
| Prisma migrate | `makemigrations` + `RunPython` data migrations |
| Redis cache | `django.core.cache` (backend swappable) |
| AsyncLocalStorage | `contextvars.ContextVar` |
| Raw SQL for window fns | `Window()` + `Rank()` / `Sum()` ORM me |

---

## Concept → file map

### 1. Models & schema (intermediate)
| Concept | Kahan |
|---|---|
| Abstract base models (`abstract = True`) | `core/models.py` |
| Model inheritance: abstract vs proxy | `core/models.py`, `ArchivedProject` in `workspace/models.py` |
| `TextChoices` / `IntegerChoices` + methods on them | `core/enums.py` |
| Through-model for M2M with extra fields | `Membership` |
| `UniqueConstraint` / `CheckConstraint` (DB-level invariants) | `workspace/models.py` Meta |
| Composite indexes, leftmost-prefix rule | `Task.Meta.indexes` |
| Generic FK (contenttypes) for audit log | `ActivityLog` |
| Denormalised rollup table | `DailyProjectRollup` |
| Custom user (`AbstractBaseUser` + `PermissionsMixin`) | `accounts/models.py` |

### 2. ORM (yahi asli advance hai)
| Concept | Kahan |
|---|---|
| Custom `QuerySet` + `Manager.from_queryset()` | `core/managers.py`, `workspace/managers.py` |
| Soft delete pattern (default manager scoping) | `core/managers.py`, `core/models.py` |
| `select_related` vs `prefetch_related` vs `Prefetch(to_attr=)` | `selectors.project_list` |
| **JOIN fan-out trap** aur uska ilaaj | `selectors.org_summary` docstring |
| `Subquery` + `OuterRef` (correlated subquery) | `selectors._logged_minutes_sq` |
| `Exists()` — `Count() > 0` se hamesha tez | `selectors.project_health` |
| `Case/When`, `F()`, `Coalesce`, `Value` | `selectors`, `managers` |
| Conditional aggregation `Count(filter=Q(...))` | `selectors.org_summary` |
| Window functions: `Rank()`, `partition_by` | `selectors.top_contributors`, `running_effort` |
| `TruncDate` + gap-filling generator | `selectors.burndown` |
| `Q` objects for composable OR/AND | `managers.TaskQuerySet.search` |

### 3. Writes, transactions, concurrency
| Concept | Kahan |
|---|---|
| Service layer (fat services, thin views) | `workspace/services.py` |
| `transaction.atomic` as decorator + CM | `services.py` |
| `select_for_update()` row locking | `services.move_task` |
| `transaction.on_commit()` for side effects | `services.log_time` |
| `F()` update = race-free increment | `services.bump_priority` |
| State machine + domain exceptions | `services.ALLOWED_TRANSITIONS`, `core/exceptions.py` |
| `bulk_create` with `update_conflicts` (UPSERT) | `management/commands/daily_rollup.py` |
| Signals — aur kab **nahi** use karne | `workspace/signals.py` |

### 4. Views, API, request layer
| Concept | Kahan |
|---|---|
| CBV + custom mixins + `LoginRequiredMixin` | `workspace/views.py` |
| **Async views**, `aget`, `async for`, `sync_to_async` | `views.project_pulse` |
| Custom middleware (2x) | `core/middleware.py` |
| `contextvars` for request-scoped tenant | `core/middleware.py` |
| Context processor | `core/context_processors.py` |
| DRF ViewSet + `@action` routes | `api/views.py` |
| Serializer validation vs business rules | `api/serializers.py` |
| Object-level permissions (dono methods!) | `api/permissions.py` |
| Custom DRF exception handler | `core/exceptions.py` |
| Throttling scopes, pagination | `settings.py`, `core/pagination.py` |
| Custom template tags: filter / simple / inclusion | `templatetags/report_tags.py` |

### 5. Ops-y cheezein
| Concept | Kahan |
|---|---|
| Management commands with argparse | `management/commands/*.py` |
| Data migration (`RunPython`, reversible, `apps.get_model`) | `migrations/0002_*.py` |
| Admin: inlines, actions, `@admin.display`, annotated columns | `workspace/admin.py` |
| Cache decorator with explicit invalidation | `core/decorators.cached_for` |
| `assertNumQueries` — N+1 ko CI me pakdo | `tests/test_selectors.py` |
| `setUpTestData` vs `setUp` | `tests/*` |

### 6. Python functionality (Django se independent)
| Concept | Kahan |
|---|---|
| `functools.wraps`, decorator factory, retry+backoff | `core/decorators.py` |
| Context managers: class-based aur `@contextmanager` | `core/context_managers.py` |
| Generators + `itertools.islice` chunking | `core/utils.chunked` |
| `itertools.accumulate`, date generator | `core/utils.py` |
| **Descriptor** (`__get__`) | `core/utils.classproperty` |
| `dataclass(frozen=True, slots=True)`, computed properties | `core/types.py` |
| `Protocol` (structural typing), `TypedDict` | `core/types.py` |
| `enum.StrEnum` vs Django choices | `core/enums.py` |
| `ParamSpec` / `TypeVar` typed decorators | `core/decorators.py` |
| `contextvars` (async-safe globals) | `core/middleware.py` |

---

## Padhne ka order (2-3 baithak)

1. `core/models.py` → `core/managers.py` → `workspace/models.py`
   *soft delete + constraints kaise ek saath fit hote hain*
2. `workspace/selectors.py` — **sabse zyada value yahin hai.** Har function ek
   ORM technique hai. `python manage.py shell` me chala ke `.query` print karo:
   ```python
   from workspace.selectors import project_health
   print(str(Project.objects.annotate(...).query))
   ```
3. `workspace/services.py` — transactions, locking, domain errors
4. `api/` — DRF ka poora loop
5. `tests/` — kyunki assertNumQueries ke bina ORM sirf ummeed hai

## Khud try karo (order of difficulty)

1. `TaskQuerySet.stale()` add karo — 7 din se `updated_at` nahi badla
2. `project_health` me `avg_cycle_time` (created_at → completed_at) annotate karo
3. `TimeEntry` pe overlapping entries rokne wala constraint (`ExclusionConstraint`, Postgres-only)
4. `top_contributors` me `DenseRank` vs `Rank` ka farak dekho, tie banake
5. `daily_rollup` ko Celery task me convert karo, `on_commit` se trigger
6. `project_report` view ko async banao aur query count compare karo

## Production me kya badlega

- SQLite → Postgres (`ExclusionConstraint`, `JSONField` indexes, `SearchVector` khulte hain)
- LocMem cache → Redis (`cached_for` bina change ke kaam karega)
- `settings.py` → `settings/{base,dev,prod}.py` + env vars
- `django-debug-toolbar` dev me, `django-silk` staging me
- Celery + beat for `daily_rollup`
- `select_for_update(skip_locked=True)` jab worker queue pattern chahiye
