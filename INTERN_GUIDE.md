# Django: Intermediate → Advanced

**A 6-week guided track, built on the PulseBoard codebase.**

Ye tutorial nahi hai. Codebase already kaam kar raha hai — tumhara kaam hai use
padhna, tod-ke samajhna, aur usme naye features add karna. Har module ka ek
**acceptance criteria** hai. Criteria pass na ho toh module complete nahi hai,
chahe code "chal raha ho".

---

## Table of contents

- [Ground rules](#ground-rules)
- [Day 0 — Setup gate](#day-0--setup-gate)
- [How to study this codebase](#how-to-study-this-codebase)
- [Module 1 — Models, constraints, inheritance](#module-1--models-constraints-inheritance)
- [Module 2 — Managers, QuerySets, soft delete](#module-2--managers-querysets-soft-delete)
- [Module 3 — The ORM (the big one)](#module-3--the-orm-the-big-one)
- [Module 4 — Writes, transactions, concurrency](#module-4--writes-transactions-concurrency)
- [Module 5 — Views, DRF, request lifecycle](#module-5--views-drf-request-lifecycle)
- [Module 6 — Python craft + ops](#module-6--python-craft--ops)
- [Capstone](#capstone)
- [Red flags — code jo review me reject hoga](#red-flags--code-jo-review-me-reject-hoga)
- [Self-check questions](#self-check-questions)
- [Reviewer checklist](#reviewer-checklist)
- [Rubric](#rubric)
- [Reference links](#reference-links)

---

## Ground rules

1. **Har PR me query counts hone chahiye.** Jo endpoint ya selector tumne
   chhua hai, uska `assertNumQueries` test likho. "Kaam kar raha hai" enough
   nahi hai — kitni queries me kaam kar raha hai, wo matter karta hai.
2. **AI se code copy karna allowed hai, samjhe bina merge karna nahi.**
   Review me main kisi bhi line pe "ye kyun?" pooch sakta hoon. Jawab nahi
   aaya toh line hategi.
3. **Har module ke end pe likhit answers** — `notes/moduleN.md` me. Bullet
   points chalenge, essay nahi chahiye. Ye tumhara revision material banega.
4. **Migration kabhi hand-edit mat karo** jab tak specifically na bola jaaye.
   `makemigrations` chalao, generated file padho, phir commit karo.
5. **`main` pe direct commit nahi.** Har module ek branch: `intern/m1-models`.
6. Stuck ho toh **45 minute** khud try karo, phir poocho. Poochte waqt batao:
   kya try kiya, kya expect tha, kya mila.

---

## Day 0 — Setup gate

**Python 3.12+ chahiye.** Kam version pe `StrEnum` aur modern type hints fail honge.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_demo --orgs 2 --projects 3 --tasks 30 --entries 4 --flush
python manage.py daily_rollup --days 14
python manage.py test
python manage.py runserver
```

Ye sab green hone ke baad, browser me kholo:

| URL | Kya dekhna hai |
|---|---|
| `/reports/projects/?org=org-1` | Report table render ho raha hai |
| `/projects/1/` | Contributors + burndown |
| `/projects/1/pulse/` | JSON response (async view) |
| `/api/projects/` | DRF browsable API |
| `/admin/` | `owner@example.com` / `demo12345` |

**Gate pass tabhi jab:** 22/22 tests pass ho aur tum browser dev-tools me
kisi bhi API response ka `X-Query-Count` header padh ke bata sako.

---

## How to study this codebase

Teen tools roz use karne hain:

### 1. `.query` — generated SQL padho

```python
python manage.py shell
```

```python
from workspace.models import Task
qs = Task.objects.for_org("org-1").open().with_logged_minutes()
print(str(qs.query))      # SQL string
print(qs.explain())       # DB ka execution plan
```

Har naya ORM construct likhne ke baad SQL padho. ORM magic nahi hai — wo SQL
generator hai. Generated SQL galat hai toh ORM code bhi galat hai.

### 2. `CaptureQueries` — kitni queries chali

```python
from core.context_managers import CaptureQueries
from workspace.selectors import project_list

with CaptureQueries() as q:
    for p in project_list("org-1"):
        _ = [t.assignee.full_name for t in p.open_tasks]

print(q.count)          # kitni queries
print(q.duplicates())   # kaunsi query repeat hui (= N+1 ka pakka signal)
```

### 3. `assertNumQueries` — CI me lock kar do

```python
with self.assertNumQueries(2):
    ...
```

Number badhega toh test fail hoga. Yahi tumhara N+1 alarm hai.

**Reading order:**
`core/models.py` → `core/managers.py` → `workspace/models.py` →
`workspace/selectors.py` → `workspace/services.py` → `workspace/api/` →
`workspace/tests/`

---

## Module 1 — Models, constraints, inheritance

**Duration:** ~4 days

### Concepts

| Concept | Kahan padho |
|---|---|
| Abstract base models | `core/models.py` — `TimeStampedModel`, `SoftDeleteModel` |
| Abstract vs multi-table vs proxy inheritance | `core/models.py` docstring, `ArchivedProject` |
| `TextChoices` / `IntegerChoices` with methods | `core/enums.py` |
| Through-model for M2M with extra fields | `Membership` |
| `UniqueConstraint`, `CheckConstraint` | `workspace/models.py` → `Meta.constraints` |
| Composite indexes, leftmost-prefix rule | `Task.Meta.indexes` |
| Generic FK (contenttypes) | `ActivityLog` |
| Custom user model | `accounts/models.py` |

### Core idea

**Validators aur `clean()` DB-level guarantee nahi dete.** `bulk_create`,
`queryset.update()`, aur raw SQL unhe bypass kar dete hain. Jo invariant
kabhi toota nahi chahiye, wo `Meta.constraints` me jaana chahiye — DB level pe.

### Tasks

- [ ] **1.1** Shell me `Task.objects.create(status="done")` chalao (bina
      `completed_at` ke). Kya hota hai? Ab `signals.py` me
      `stamp_completed_at` receiver comment out karo aur dobara chalao.
      Ab kya error aata hai, aur kis layer se aata hai?
- [ ] **1.2** `Task` pe ek `Tag` model add karo (M2M). Phir use through-model
      me convert karo jisme `added_by` aur `added_at` ho. Migration padho:
      Django ne kya generate kiya?
- [ ] **1.3** `TimeEntry` pe ek `CheckConstraint` add karo jo future-dated
      `started_at` rok de. Test likho jo constraint violate kare aur
      `IntegrityError` expect kare.
- [ ] **1.4** `Task.Meta.indexes` me `["project", "status", "due_date"]` hai.
      `explain()` chala ke batao — ye index in dono queries me use hota hai ya nahi?
      - `Task.objects.filter(project_id=1, status="done")`
      - `Task.objects.filter(status="done", due_date__lt=today)`
      Difference kyun hai?
- [ ] **1.5** Ek proxy model `CriticalTask` banao jiska default queryset
      `priority=4` ho. Confirm karo ki koi nayi table nahi bani
      (`sqlmigrate` output padho).

### Acceptance criteria

- Migrations clean hain (`makemigrations --check` no changes dikhaye)
- Naye constraints ke liye `IntegrityError` test hai
- `notes/module1.md` me: abstract vs proxy vs multi-table — kab kaunsa,
  aur composite index ka column order kyun matter karta hai

---

## Module 2 — Managers, QuerySets, soft delete

**Duration:** ~3 days

### Concepts

| Concept | Kahan |
|---|---|
| Custom `QuerySet` vs custom `Manager` | `core/managers.py` |
| `Manager.from_queryset()` | `workspace/managers.TaskManager` |
| Default manager scoping | `TaskManager.get_queryset()` |
| `_default_manager` vs `_base_manager` | `TaskManager` docstring |
| Soft delete pattern | `core/managers.SoftDeleteQuerySet` |

### Core idea

Method **Manager** pe likhoge toh chain toot jaayegi
(`Task.objects.open().overdue()` fail hoga). **QuerySet** pe likho aur
`from_queryset()` se Manager bana lo — dono jagah kaam karega.

### The gotcha you must internalise

```python
Task.objects.all()                      # deleted_at filter LAGTA hai
project.tasks.all()                     # LAGTA hai
TimeEntry.objects.filter(task__project=p)   # NAHI lagta — JOIN traversal
                                            # _base_manager use karta hai
```

Isiliye `selectors.py` ke subqueries me `deleted_at__isnull=True` **manually**
likha hua hai. Ye bhool jao toh soft-deleted rows report me aa jaayengi.

### Tasks

- [ ] **2.1** `TaskQuerySet.stale()` add karo — jo tasks 7 din se update nahi hue
      aur abhi open hain. Chainable hona chahiye:
      `Task.objects.for_org("org-1").stale().high_priority()`
- [ ] **2.2** `TimeEntry` ke liye ek `TimeEntryQuerySet` banao with
      `this_week()`, `by_user(user)`, `longer_than(minutes)`.
- [ ] **2.3** Ek test likho jo prove kare ki soft-deleted task
      `project.tasks.all()` me nahi dikhta, par `Task.all_objects` me dikhta hai
      **aur** JOIN traversal me leak ho jaata hai. Leak ko fix karo.
- [ ] **2.4** `SoftDeleteQuerySet.restore()` ke liye ek management command
      banao: `python manage.py restore_task <id>`.

### Acceptance criteria

- Saare naye methods chainable hain (test me at least 3-method chain ho)
- Leak wala test pehle **fail** hota tha, ab pass hota hai (PR description me
  before/after dikhao)
- `notes/module2.md`: `_default_manager` vs `_base_manager` — apne shabdon me

---

## Module 3 — The ORM (the big one)

**Duration:** ~2 weeks. Yahi module tumhe intermediate se advanced le jaayega.

### Concepts

| Concept | Kahan |
|---|---|
| `select_related` vs `prefetch_related` | `selectors.project_list` |
| `Prefetch(queryset=..., to_attr=...)` | `selectors.project_list` |
| **JOIN fan-out trap** | `selectors.org_summary` docstring |
| `Subquery` + `OuterRef` | `selectors._logged_minutes_sq` |
| `Exists()` | `selectors.project_health` |
| `Case` / `When` / `F()` / `Value` / `Coalesce` | `selectors`, `managers` |
| Conditional aggregation `Count(filter=Q(...))` | `selectors.org_summary` |
| Window functions: `Rank()`, `partition_by` | `selectors.top_contributors`, `running_effort` |
| `TruncDate` + gap filling | `selectors.burndown` |
| `Q` objects | `managers.TaskQuerySet.search` |
| `aggregate()` vs `annotate()` | `org_summary` vs `project_health` |
| `.only()` / `.defer()` / `.values()` / `.iterator()` | — (khud research karo) |

### The three rules

1. **`select_related` = JOIN** (forward FK, OneToOne). Ek query.
   **`prefetch_related` = second query** (reverse FK, M2M). Python me join hota hai.
2. **Do reverse-FK aggregates ek saath = fan-out.** Rows duplicate ho jaati hain
   aur `Sum`/`Count` inflate ho jaata hai. Ilaaj: `distinct=True`, ya behtar —
   `Subquery` se har aggregate apne scope me rakho.
3. **`annotate()` per-row hai, `aggregate()` whole-queryset hai.**
   `annotate()` QuerySet return karta hai, `aggregate()` dict.

### The fan-out demo — ye khud chalao

```python
from django.db.models import Count, Sum
from workspace.models import Task

# GALAT — time_entries ka JOIN har task ko N baar duplicate karta hai
Task.objects.for_org("org-1").aggregate(
    total=Count("id"),
    logged=Sum("time_entries__minutes"),
)
# total inflate ho jaayega

# SAHI — do alag queries, ya Count(distinct=True)
```

Number likh lo. Ye baat tum kabhi nahi bhoologe.

### Tasks

- [ ] **3.1** `project_health()` me `avg_cycle_time` annotate karo —
      `completed_at - created_at` ka average, sirf done tasks pe.
      Hint: `Avg`, `F()`, `filter=Q(...)`, `DurationField`.
      **Constraint: query count 1 hi rehna chahiye.**
- [ ] **3.2** `top_contributors()` me `Rank()` ko `DenseRank()` se badlo.
      Deliberately tie banao (do users ko same minutes do) aur dono ka output
      compare karo. `notes` me difference likho.
- [ ] **3.3** Ek naya selector `idle_members(org_slug)` — jin members ne
      pichhle 7 din me koi time log nahi kiya. **`Exists()` use karo, `Count() == 0`
      nahi.** Dono ka `explain()` compare karke batao kaunsa tez hai aur kyun.
- [ ] **3.4** `project_list()` ko deliberately tod do — `prefetch_related`
      hata do. Test chalao. Query count kya hua? Ab `select_related` se fix
      karne ki koshish karo — kaam karta hai? Kyun nahi?
- [ ] **3.5** Ek `workload_forecast(org_slug)` selector banao jo har user ke
      liye next 14 days ke open tasks ka estimate sum kare, aur unhe
      `Case/When` se `underloaded` / `balanced` / `overloaded` bucket me daale.
- [ ] **3.6** `running_effort()` me `partition_by` hata do. Output kaise
      badla? SQL me kya farak aaya?
- [ ] **3.7** 50,000 time entries seed karo
      (`seed_demo --tasks 500 --entries 20`). `burndown()` aur `org_summary()`
      ka time measure karo `stopwatch` se. Phir `DailyProjectRollup` se
      padhne wala version likho aur dono compare karo.

### Acceptance criteria

- 3.1, 3.3, 3.5 ke liye `assertNumQueries` tests hain aur count **1 ya 2** hai
- 3.7 me before/after timings PR description me hain
- `notes/module3.md` me: fan-out kya hai, `Subquery` kab use karna,
  `select_related` vs `prefetch_related` decision rule

---

## Module 4 — Writes, transactions, concurrency

**Duration:** ~1 week

### Concepts

| Concept | Kahan |
|---|---|
| Service layer (fat services, thin views) | `workspace/services.py` |
| `transaction.atomic` — decorator aur context manager | pura `services.py` |
| `select_for_update()` row locking | `services.move_task` |
| `transaction.on_commit()` | `services.log_time` |
| `F()` updates — race-free | `services.bump_priority` |
| State machine + domain exceptions | `ALLOWED_TRANSITIONS`, `core/exceptions.py` |
| `bulk_create(update_conflicts=True)` — UPSERT | `management/commands/daily_rollup.py` |
| Signals — aur kab **nahi** | `workspace/signals.py` |

### Core ideas

**Read-modify-write race:**

```python
# GALAT — do parallel requests, ek update kho jaayega
task.priority += 1
task.save()

# SAHI — DB me hota hai, atomic
Task.objects.filter(pk=pk).update(priority=F("priority") + 1)
```

**`select_for_update()` sirf `atomic()` ke andar kaam karta hai.** Lock tab tak
rehta hai jab tak transaction chale. Bahar likhoge toh silently useless ho jaayega.

**Side effects `on_commit()` me.** Transaction rollback ho gaya par email/webhook
already ja chuka — ye production bug hai jo staging me kabhi nahi dikhta.

**Signals business logic ke liye nahi hain.** Invisible control flow banate hain,
test karna mushkil hai, aur `bulk_create` / `queryset.update()` pe fire hi nahi hote.
Cache invalidation aur search re-indexing jaise cross-app reactions ke liye theek hain.

### Tasks

- [ ] **4.1** `services.reassign_task(task_id, to_user, actor)` likho.
      Rules: sirf manager reassign kar sakta hai; assignee usi org ka member ho;
      activity log likhe; cache invalidate kare. Poore rules ke liye tests likho.
- [ ] **4.2** Race condition demonstrate karo. Ek script likho jo do threads se
      same task pe `move_task` chalaye. Pehle `select_for_update` ke bina, phir
      ke saath. Difference `notes` me record karo.
      (SQLite pe locking behaviour alag hai — Postgres pe chalao agar mil jaaye.)
- [ ] **4.3** `services.log_time` me budget check `Sum` query karta hai har baar.
      Isko `Project` pe ek denormalized `logged_minutes` counter se replace karo,
      jo `F()` se update ho. Trade-offs `notes` me likho: ab kaunsi cheez
      galat ho sakti hai, aur usko kaise detect karoge?
- [ ] **4.4** `on_commit()` wali line hata do aur ek test likho jo prove kare
      ki rollback ke baad bhi side effect chal gaya. Phir wapas laga ke test
      pass karao.
- [ ] **4.5** `daily_rollup` ko idempotent hone ka test already hai. Ab ek
      `--dry-run` flag add karo jo kuch likhe nahi, sirf report kare ki
      kitni rows badalti.

### Acceptance criteria

- Har naye service function ke liye happy path **aur** har error path ka test
- Ek bhi business rule serializer ya view me nahi hai — sab services me
- `notes/module4.md`: `select_for_update` kab kaam nahi karta, `on_commit` kyun

---

## Module 5 — Views, DRF, request lifecycle

**Duration:** ~1 week

### Concepts

| Concept | Kahan |
|---|---|
| CBV + custom mixins | `workspace/views.py` |
| Async views, `aget()`, `async for`, `sync_to_async` | `views.project_pulse` |
| Custom middleware | `core/middleware.py` |
| `contextvars` for request-scoped state | `core/middleware.py` |
| Context processors | `core/context_processors.py` |
| DRF ViewSet + `@action` | `api/views.py` |
| Serializer validation vs business rules | `api/serializers.py` |
| Object-level permissions | `api/permissions.py` |
| Custom exception handler | `core/exceptions.py` |
| Throttling, pagination | `settings.py`, `core/pagination.py` |
| Custom template tags | `templatetags/report_tags.py` |

### Core ideas

**Permission classes me dono methods chahiye.** Sirf `has_object_permission`
likhoge toh list endpoint khula reh jaayega — object-level check list pe
chalta hi nahi.

**Serializer shape validate karta hai, business rules nahi.** "Estimate 200h se
kam ho" → serializer. "Manager hi archive kar sakta hai" → service.

**Tenant scoping `get_queryset()` me hona chahiye, view logic me nahi.** Wahan
bhoolna structurally mushkil hai; har view me `if` lagana bhoolne wala hai.

**`contextvars` global variable nahi hai.** Thread aur async task dono me safe
hai. Middleware me `token = var.set(x)` ke baad `finally: var.reset(token)`
zaroori hai, warna leak hoga.

### Tasks

- [ ] **5.1** Ek `TimeEntryViewSet` banao — list, create, delete.
      Rules: user sirf apni entries dekhe/delete kare; manager poore org ki
      dekhe. `IsOrgMember` extend karo, naya permission class banao.
- [ ] **5.2** `IsOrgMember.has_permission` ko `return True` kar do. Ek test
      likho jo prove kare ki ab outsider list endpoint pe data dekh sakta hai.
      Fix karo. **Ye test permanently rehna chahiye.**
- [ ] **5.3** `ProjectReportView` ko async banao. Query count aur response
      time compare karo sync version se. Faayda hua? Kyun / kyun nahi?
- [ ] **5.4** Ek middleware likho jo har request ko ek `X-Request-ID` de aur
      use `contextvars` me daale, taaki har log line me wo ID aaye.
      `logging.Filter` ke saath wire karo.
- [ ] **5.5** `@register.inclusion_tag` se ek `burndown_sparkline` tag banao
      jo inline SVG bar chart render kare.
- [ ] **5.6** `daily_rollup` ko API se trigger karne wala endpoint banao,
      throttle `2/hour` ke saath, sirf org owner ke liye.

### Acceptance criteria

- 5.2 wala regression test suite me hai
- Naye endpoints pe `X-Query-Count` 5 se kam hai
- Koi business rule serializer me nahi ghusa
- `notes/module5.md`: `has_permission` vs `has_object_permission`, aur
  async view kab actually faayda deta hai

---

## Module 6 — Python craft + ops

**Duration:** ~4 days

### Concepts

| Concept | Kahan |
|---|---|
| `functools.wraps`, decorator factory | `core/decorators.py` |
| `ParamSpec` / `TypeVar` typed decorators | `core/decorators.py` |
| Context managers — class-based aur `@contextmanager` | `core/context_managers.py` |
| Generators + `itertools.islice` | `core/utils.chunked` |
| Descriptors (`__get__`) | `core/utils.classproperty` |
| `dataclass(frozen=True, slots=True)` | `core/types.py` |
| `Protocol` (structural typing), `TypedDict` | `core/types.py` |
| `enum.StrEnum` vs Django choices | `core/enums.py` |
| Management commands + argparse | `management/commands/` |
| Data migrations (`RunPython`) | `migrations/0002_*.py` |
| Admin customisation | `workspace/admin.py` |
| Cache with explicit invalidation | `core/decorators.cached_for` |

### Data migration rules (ratta maar lo)

1. `apps.get_model()` use karo — direct import **kabhi nahi**. Migration ko
   us waqt ka historical model chahiye, aaj wala nahi.
2. Hamesha `reverse_code` do (`noop` bhi chalega).
3. Bade tables pe `.iterator()` + chunks, ya `.update()` — Python loop nahi.
4. Schema aur data migration alag files me.

### Tasks

- [ ] **6.1** `@retry` decorator me ek `on_retry` callback add karo.
      Test likho jo verify kare ki backoff sahi hai (`time.sleep` mock karke).
- [ ] **6.2** Ek `@require_role("manager")` decorator likho service functions
      ke liye, jo `actor` kwarg inspect kare aur `PermissionDenied` uthaye.
      `services.py` me manual checks isse replace karo.
- [ ] **6.3** Ek context manager `bulk_mode()` likho jo apne andar signals
      disconnect kar de aur bahar nikalte hi reconnect. Test likho.
- [ ] **6.4** Ek data migration likho jo har existing `Project` ke liye
      `logged_minutes` counter backfill kare (Module 4.3 wala field).
      Reversible hona chahiye. `migrate` aur `migrate workspace 0002` dono chalao.
- [ ] **6.5** Admin me `Task` ke liye ek custom `list_filter` banao —
      "Overdue / Due this week / No due date". `SimpleListFilter` subclass karo.
- [ ] **6.6** `cached_for` ko cache stampede se bachao (ek key expire hote hi
      50 requests same query maar dein). Ek approach research karke implement karo.

### Acceptance criteria

- Decorators pe `functools.wraps` laga hai (test se verify karo:
  `fn.__name__` sahi aata hai)
- Data migration forward aur backward dono chalti hai
- `notes/module6.md`: `apps.get_model()` kyun zaroori hai — ek concrete
  example do jahan direct import tootega

---

## Capstone

**Duration:** ~1 week

Ek complete feature end-to-end deliver karo: **Sprint planning**.

Requirements:

- `Sprint` model — org-scoped, start/end date, ek `Task` ek time pe ek hi
  sprint me. Overlapping sprints ek org me allowed nahi (DB constraint).
- `services.py` me: sprint banana, task assign/remove karna, sprint close karna.
  Closed sprint immutable hai.
- Selector: sprint velocity report — planned vs completed estimate hours,
  per-user breakdown with ranking. **Max 2 queries.**
- DRF endpoints with correct permissions (member read, manager write).
- Report page with template tags.
- Management command: `sprint_report --sprint <id> --format json|table`.
- Data migration jo existing tasks ko ek "Backlog" sprint me daal de.
- Tests: models (constraints), services (har error path), selectors
  (`assertNumQueries`), API (permissions).

**Definition of done:**

- [ ] `python manage.py test` — sab green
- [ ] `makemigrations --check --dry-run` — no pending changes
- [ ] Velocity report ka query count test me locked hai
- [ ] Har naye endpoint pe `X-Query-Count` < 6
- [ ] README me nayi feature documented hai
- [ ] PR description me: design decisions, kya trade-off kiya, kya nahi kiya aur kyun

---

## Red flags — code jo review me reject hoga

| Pattern | Kyun galat | Kya karo |
|---|---|---|
| Loop ke andar query | N+1 | `select_related` / `prefetch_related` |
| `obj.field += 1; obj.save()` | read-modify-write race | `F()` expression |
| `select_for_update()` bina `atomic()` | lock kaam hi nahi karta | `@transaction.atomic` lagao |
| Email/webhook `atomic()` block ke andar | rollback ke baad bhi bhej diya | `transaction.on_commit()` |
| Business rule serializer ya view me | admin/command/task bypass kar denge | service layer |
| Signal me business logic | invisible flow, `bulk_create` skip karta hai | explicit service call |
| Validator pe bharosa, constraint nahi | bulk ops bypass kar dete hain | `Meta.constraints` |
| `except Exception: pass` | error nigal gaya | specific exception, ya log karo |
| Migration me direct model import | historical state toot jaayega | `apps.get_model()` |
| `Count()` + `Sum()` ek hi aggregate me | fan-out, numbers inflate | alag queries ya `Subquery` |
| `.all()` pe iterate over 100k rows | memory | `.iterator()` + chunks |
| Test bina query count assertion ke | N+1 chupke se aa jaayega | `assertNumQueries` |
| Tenant filter view logic me | ek jagah bhoolo, data leak | `get_queryset()` me |

---

## Self-check questions

Module complete karne se pehle bina Google ke jawab do. Nahi aaya toh module
dobara padho.

**Models**
1. Abstract, multi-table, aur proxy inheritance me kya farak hai? Kab kaunsa?
2. `validators` aur `CheckConstraint` me kya farak hai? Kaunsa `bulk_create` bypass kar deta hai?
3. Composite index `(a, b, c)` kis query me use hoga, kis me nahi?
4. Generic FK ka trade-off kya hai?

**ORM**
5. `select_related` aur `prefetch_related` — kaunsa kab, aur kitni queries?
6. JOIN fan-out kya hai? Do tareeke batao fix karne ke.
7. `annotate()` aur `aggregate()` me kya farak?
8. `Exists()` `Count() > 0` se tez kyun hai?
9. `Subquery` + `OuterRef` kab zaroori ho jaata hai?
10. Window function aur `GROUP BY` aggregate me kya farak?

**Writes**
11. `select_for_update()` kab silently useless ho jaata hai?
12. `transaction.on_commit()` kyun chahiye?
13. Signals kab use karo, kab nahi?
14. `F()` expression race kaise rokta hai?

**Views / DRF**
15. `has_permission` sirf ya `has_object_permission` sirf — kya toot jaayega?
16. Serializer validation aur service validation — line kahan khinchti hai?
17. Async view kab actually faster hai, kab nahi?

**Python**
18. `functools.wraps` na lagao toh kya tootega?
19. Descriptor kya hai? `property` kaise implement hota hai internally?
20. Data migration me `apps.get_model()` kyun, direct import kyun nahi?

---

## Reviewer checklist

Har PR pe ye dekho — order me:

- [ ] Tests hain? Green hain?
- [ ] `assertNumQueries` hai naye read paths pe?
- [ ] `makemigrations --check` clean hai?
- [ ] Business logic services me hai, views/serializers/signals me nahi?
- [ ] Naye invariants DB constraints me hain, sirf Python me nahi?
- [ ] Tenant scoping `get_queryset()` me hai?
- [ ] Error paths ka test hai, sirf happy path nahi?
- [ ] Koi `except Exception: pass` nahi?
- [ ] `notes/moduleN.md` update hua?
- [ ] PR description me trade-offs likhe hain?
- [ ] Randomly 2 lines pe "ye kyun?" pooch ke dekho

---

## Rubric

| Level | Kya dikhta hai |
|---|---|
| **Needs work** | Code chalta hai par query counts pata nahi. Business logic bikhri hui. Test sirf happy path ke. |
| **On track** | `select_related`/`prefetch_related` sahi lagta hai. Services me logic. Error paths test hote hain. Constraints DB me. |
| **Strong** | ORM se non-trivial reports 1-2 query me nikaal leta hai. Fan-out khud pehchaan leta hai. Transaction boundaries deliberate hain. Trade-offs likh ke justify karta hai. |
| **Advanced** | Performance ko measure karke optimise karta hai, guess karke nahi. Denormalisation kab karni hai jaanta hai. Race conditions pehle se dekh leta hai. Uska code review karne me maza aata hai. |

---

## Reference links

Order me padho, sab ek saath nahi:

- Django ORM: [Making queries](https://docs.djangoproject.com/en/stable/topics/db/queries/)
- [Aggregation](https://docs.djangoproject.com/en/stable/topics/db/aggregation/) — cheat sheet ki tarah
- [Query expressions](https://docs.djangoproject.com/en/stable/ref/models/expressions/) — `F`, `Case`, `Subquery`, `Window`
- [Database optimization](https://docs.djangoproject.com/en/stable/topics/db/optimization/)
- [Transactions](https://docs.djangoproject.com/en/stable/topics/db/transactions/)
- [Constraints](https://docs.djangoproject.com/en/stable/ref/models/constraints/)
- [Migrations](https://docs.djangoproject.com/en/stable/topics/migrations/)
- [Async support](https://docs.djangoproject.com/en/stable/topics/async/)
- [DRF viewsets](https://www.django-rest-framework.org/api-guide/viewsets/) & [permissions](https://www.django-rest-framework.org/api-guide/permissions/)
- Python: [functools](https://docs.python.org/3/library/functools.html),
  [contextlib](https://docs.python.org/3/library/contextlib.html),
  [itertools](https://docs.python.org/3/library/itertools.html),
  [descriptors](https://docs.python.org/3/howto/descriptor.html)

**Tools install kar lo:** `django-debug-toolbar` (dev), `django-extensions`
(`shell_plus --print-sql` kaafi useful hai).
