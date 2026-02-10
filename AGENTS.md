# MITx Online - Copilot Instructions

## Project Overview

MITx Online is a Django-based web platform for managing MIT online courses and programs. It integrates with Open edX for course delivery, Wagtail CMS for content management, and includes features for ecommerce, B2B provisioning, flexible pricing, and certificate generation.

**Tech Stack:**
- Backend: Django 5.1, Python 3.11+
- Frontend: React 16, Webpack, Yarn workspaces
- CMS: Wagtail 7.2
- Database: PostgreSQL 15
- Cache/Queue: Redis, Celery
- Authentication: OAuth2, Keycloak (optional)
- Build System: Pants 2.17
- Container: Docker Compose

## Build, Test, and Lint Commands

### Python/Django

**Run tests:**
```bash
# Full test suite with parallel execution
poetry run pytest -n logical

# Single test file
poetry run pytest courses/api_test.py

# Single test function
poetry run pytest courses/api_test.py::test_function_name

# With coverage
poetry run pytest --cov . --cov-report html
```

**Linting and formatting:**
```bash
# Format code (ruff)
poetry run ruff format .

# Lint with auto-fix
poetry run ruff check --fix .

# Pre-commit hooks (runs all checks)
pre-commit run --all-files
```

**Run development server:**
```bash
docker compose up  # Full stack
docker compose run --rm web python manage.py <command>  # Django management commands
```

### Frontend (JavaScript/React)

Frontend code lives in `frontend/public/` and `frontend/staff-dashboard/` workspaces.

**Run tests:**
```bash
# From frontend/public directory
yarn test              # Run tests once
yarn test:watch        # Watch mode
yarn coverage          # With coverage report
```

**Linting and formatting:**
```bash
# From frontend/public directory
yarn lint              # ESLint
yarn scss_lint         # Sass linting
yarn fmt               # Format with prettier-eslint
yarn fmt:check         # Check formatting
```

**Build:**
```bash
# From project root
yarn workspaces foreach run build

# From frontend/public directory
yarn build             # Production build
yarn dev-server        # Development server with HMR
```

### Documentation

```bash
# Build Sphinx docs (requires Pants)
pants docs ::

# Output is in dist/sphinx/index.html
```

## High-Level Architecture

### Django Apps Structure

**Core Business Logic:**
- `courses/` - Course, CourseRun, Program, ProgramRun models and enrollments
- `ecommerce/` - Product catalog, Basket, Order workflow (state machine pattern)
- `b2b/` - B2B contracts, organizations, SCIM provisioning, Keycloak admin integration
- `flexiblepricing/` - Income-based pricing tiers and flexible pricing requests
- `authentication/` - OAuth2 provider, API gateway integration
- `users/` - User profiles and management

**CMS and Content:**
- `cms/` - Wagtail pages (CoursePage, ProgramPage, CertificatePage, etc.)
- `openedx/` - Integration with Open edX LMS (enrollment sync, grades)

**Supporting:**
- `mail/` - Email templates and sending
- `hubspot_sync/` - HubSpot CRM synchronization
- `sheets/` - Google Sheets integration for deferrals

### API Architecture

**Multi-Version REST APIs:**
- `/api/v1/` - Legacy endpoints
- `/api/v2/` - Current stable API (preferred for new features)
- `/api/v3/` - Newer endpoints

APIs use Django REST Framework with:
- ViewSets for CRUD operations
- Custom filterset classes for complex filtering
- drf-spectacular for OpenAPI schema generation
- Pagination via `PageNumberPagination`

### Data Model Patterns

**Dual Lookup Pattern:**
Models like `Course`, `Program`, and `CourseRun` support lookup by both:
- Integer primary key: `/api/v2/courses/123/`
- Human-readable ID: `/api/v2/courses/course-v1:MITx+6.00.1x+2024/`

Implemented via `ReadableIdLookupMixin` in viewsets (see `courses/views/v2/__init__.py`).

**Enrollment Hierarchy:**
```
ProgramEnrollment
  └─> CourseRunEnrollment (for specific course runs within program)
```

**Order State Machine:**
Orders follow a state machine pattern with distinct model classes:
- `PendingOrder` → `FulfilledOrder` / `DeclinedOrder` / `ErroredOrder`
- `FulfilledOrder` → `RefundedOrder` / `PartiallyRefundedOrder` / `CanceledOrder`

State transitions are managed via `Order.fulfill()`, `Order.refund()`, etc.

### Wagtail CMS Integration

Wagtail pages mirror Django models:
- `CoursePage` ↔ `Course` (linked via `page` foreign key)
- `ProgramPage` ↔ `Program`
- Pages manage content, descriptions, marketing copy
- Django models manage enrollments, pricing, business logic

**Important:** When querying courses/programs for public display, filter by `page__live=True` to show only published content.

### Open edX Integration

The platform syncs with Open edX:
- Enrollments created in MITx Online are pushed to edX via API
- Grades and certificates are fetched from edX
- Celery tasks handle periodic synchronization
- Configuration in `OPENEDX_*` settings

### B2B System

B2B features support bulk course access for organizations:
- `Organization` - Companies purchasing course access
- `Contract` - Agreement between org and MIT
- `ContractMembership` - Links contracts to courses/programs
- SCIM 2.0 API for user provisioning (`/scim/v2/`)
- Keycloak integration for SSO and group management

## Key Conventions

### Test Files and Factories

**Test naming:** Test files use the `*_test.py` suffix (e.g., `models_test.py`, `api_test.py`), not `test_*.py`.

**Factories:** Use `factory_boy` for test data generation. Factory classes live in `factories.py` within each app:
```python
from courses.factories import CourseFactory, CourseRunFactory
course = CourseFactory.create()
```

### Configuration and Environment

**Environment variables:**
- Use `main/env.py` for environment variable definitions
- Settings in `main/settings.py` pull from environment
- Docker Compose sets defaults in `docker-compose.yml`

**Feature flags:** Managed via `main/features.py` constants and `settings.FEATURES` dict.

### Database Migrations

**Always check for missing migrations before committing:**
```bash
poetry run python manage.py makemigrations --check --dry-run
```

Test suite includes checks for:
- Missing migrations (`scripts/test/detect_missing_migrations.sh`)
- Auto-generated migration issues (`scripts/test/no_auto_migrations.sh`)

### API Development

**Serializers:** Version-specific serializers live in app-level directories:
- `courses/serializers/v1/`
- `courses/serializers/v2/`
- `courses/serializers/v3/`

**Schema generation:** Use `drf-spectacular` decorators for OpenAPI docs:
```python
from drf_spectacular.utils import extend_schema, OpenApiParameter

@extend_schema(
    parameters=[OpenApiParameter(name='readable_id', type=str)],
    responses={200: CourseSerializer}
)
def list(self, request):
    ...
```

**Queryset optimization:** Use `extend_schema_get_queryset` decorator (from `openapi/utils.py`) when queryset depends on request context not available at schema generation time.

### Celery Tasks

**Task organization:**
- Task definitions in `<app>/tasks.py`
- Import app tasks in `main/celery.py` via autodiscovery
- Queue routing: HubSpot tasks use dedicated queue

**Always eager in tests:** Tests set `CELERY_TASK_ALWAYS_EAGER=True` to run tasks synchronously.

### mitol-django Libraries

The project uses several internal MIT ODL Django libraries:
- `mitol-django-common` - Shared utilities, base models
- `mitol-django-authentication` - OAuth/OIDC support
- `mitol-django-openedx` - Open edX API client
- `mitol-django-payment-gateway` - CyberSource integration
- `mitol-django-hubspot-api` - HubSpot CRM client
- `mitol-django-scim` - SCIM 2.0 server implementation

These provide standard patterns used across MIT ODL projects.

### Dependency Management

**Python:** Use Poetry for dependency management:
```bash
docker compose run --rm web poetry add <package>
docker compose build web celery  # Rebuild images after changes
```

**JavaScript:** Use Yarn 3 (Berry) with workspaces. Update dependencies from workspace root or specific workspace directory.

### Code Style

**Python:**
- Formatted with `ruff format` (Black-compatible)
- Linted with `ruff` (replaces flake8, isort, pylint)
- Type hints encouraged but not required
- Docstrings for public APIs

**JavaScript:**
- ESLint with `eslint-config-mitodl`
- Flow type checking (older code) - run `yarn flow`
- Prettier for formatting via `prettier-eslint`

### Keycloak Integration

Optional OIDC authentication via Keycloak:
- Local instance: `docker-compose.yml` includes Keycloak service (disabled by default)
- Enable with `docker compose -f docker-compose.yml -f docker-compose-keycloak-override.yml up`
- B2B provisioning syncs users/groups to Keycloak
- See `README-keycloak.md` for setup details

## Working with the Codebase

### Local Development Setup

1. Follow the [MIT ODL common web app guide](https://mitodl.github.io/handbook/how-to/common-web-app-guide.html)
2. Add entries to `/etc/hosts`:
   ```
   127.0.0.1  mitxonline.odl.local
   127.0.0.1  openedx.odl.local
   ```
3. Start services: `docker compose up`
4. Create superuser: `docker compose run --rm web python manage.py createsuperuser`
5. Access at: http://mitxonline.odl.local:8013

### Running Single Tests

The test suite uses `pytest-django` with parallel execution via `pytest-xdist`:
```bash
# Single test module
poetry run pytest courses/models_test.py

# Single test class
poetry run pytest courses/models_test.py::TestCourse

# Single test method
poetry run pytest courses/models_test.py::TestCourse::test_course_creation

# With debugging (disables parallel execution)
poetry run pytest -n0 -s courses/models_test.py::test_function
```

### Common Management Commands

```bash
# Run inside container
docker compose run --rm web python manage.py <command>

# Useful commands
manage.py migrate                    # Apply migrations
manage.py makemigrations             # Create migrations
manage.py createsuperuser            # Create admin user
manage.py shell_plus                 # Enhanced shell with models loaded
manage.py configure_wagtail          # Set up Wagtail site
manage.py createcachetable           # Set up cache table
manage.py collectstatic              # Collect static files
```

### OpenAPI Schema

Generate and view API schema:
```bash
# Generate schema
poetry run python manage.py spectacular --file schema.yml

# View in browser
# Navigate to http://mitxonline.odl.local:8013/api/schema/swagger-ui/
```

Schema checked in tests: `scripts/test/openapi_spec_check.sh` ensures schema is up-to-date.

### Frontend Development

For frontend changes with hot module replacement:
```bash
# Start webpack dev server
cd frontend/public
yarn dev-server
```

The Django dev server uses `webpack-dev-middleware` to proxy webpack assets.
