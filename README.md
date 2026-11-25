# EmployBoard

### Every job. Every source. One board.

EmployBoard is a multi-source job aggregation and discovery platform that collects publicly available job postings from multiple Applicant Tracking Systems (ATS), transforms heterogeneous job data into a unified schema, maintains a centralized PostgreSQL database, and exposes the aggregated information through a searchable interface.

Instead of visiting individual company career pages and searching through different recruitment platforms, users can discover opportunities from multiple companies through a single interface.

The platform is built around a data-engineering pipeline that handles external API integration, data extraction, normalization, deduplication, incremental synchronization, persistence, and retrieval.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [How EmployBoard Works](#3-how-employboard-works)
4. [Technology Stack](#4-technology-stack)
5. [System Architecture](#5-system-architecture)
6. [Data Sources and ATS Integrations](#6-data-sources-and-ats-integrations)
7. [Company Registry](#7-company-registry)
8. [Data Ingestion Pipeline](#8-data-ingestion-pipeline)
9. [Data Normalization](#9-data-normalization)
10. [Deduplication Strategy](#10-deduplication-strategy)
11. [Synchronization and Job Lifecycle Management](#11-synchronization-and-job-lifecycle-management)
12. [Database Architecture](#12-database-architecture)
13. [Database Design Decisions](#13-database-design-decisions)
14. [Backend Architecture](#14-backend-architecture)
15. [API Reference](#15-api-reference)
16. [Frontend Architecture](#16-frontend-architecture)
17. [Search, Filtering and Pagination](#17-search-filtering-and-pagination)
18. [Error Handling and Reliability](#18-error-handling-and-reliability)
19. [Security and Access Control](#19-security-and-access-control)
20. [Project Structure](#20-project-structure)
21. [Getting Started](#21-getting-started)
22. [Environment Configuration](#22-environment-configuration)
23. [Running the Application](#23-running-the-application)
24. [CLI Commands](#24-cli-commands)
25. [Database Migrations](#25-database-migrations)
26. [Deployment Considerations](#26-deployment-considerations)
27. [Performance and Scalability](#27-performance-and-scalability)
28. [Current Limitations](#28-current-limitations)
29. [Future Improvements](#29-future-improvements)
30. [Technical Design Decisions](#30-technical-design-decisions)
31. [Contributing](#31-contributing)
32. [License](#32-license)

---

# 1. Project Overview

EmployBoard provides a unified interface for discovering publicly available job opportunities across multiple companies.

The platform integrates with four ATS providers:

- Greenhouse
- Lever
- Ashby
- SmartRecruiters

Each provider exposes job information through its own public API, with different response structures, field names, data formats and levels of detail.

EmployBoard abstracts these differences through provider-specific adapters and transforms the retrieved information into a standardized internal representation.

The resulting data is stored in PostgreSQL and made available through a FastAPI REST API.

### Core capabilities

- Multi-source job aggregation through public ATS APIs.
- Configurable company and ATS registry.
- Provider-specific API adapters.
- Unified job data representation.
- Employment type, workplace type and experience-level normalization.
- Compensation parsing and validation.
- Cross-source duplicate detection.
- Canonical job record management.
- Automated and manually triggered synchronization.
- Missing-job detection and controlled deactivation.
- Historical ingestion tracking.
- PostgreSQL-backed search and filtering.
- Paginated job discovery.
- Responsive React frontend.
- Public job discovery API and protected administrative endpoints.

**The central engineering objective is to separate provider-specific data acquisition from provider-independent data processing and persistence.**

This allows additional companies using existing ATS providers to be integrated without implementing an entirely new ingestion pipeline.

---

# 2. Problem Statement

Company career pages are distributed across different recruitment platforms.

A user searching for opportunities may need to visit multiple career websites, navigate different interfaces, understand different filtering mechanisms and manually compare postings.

From an engineering perspective, the same problem exists at the data layer.

Different ATS providers expose different representations of the same business concepts.

For example:

| Concept | Provider A | Provider B | Provider C |
|---|---|---|---|
| Employment type | FullTime | Permanent | Full-time |
| Workplace | Remote First | WFH | Remote |
| Experience | Graduate | Entry Level | Entry |
| Job identifier | External ID A | External ID B | External ID C |

Directly combining these records without transformation would introduce inconsistencies into the resulting dataset.

EmployBoard addresses this by introducing a common data-processing layer.

### Objectives

1. Retrieve publicly available job postings from multiple ATS platforms.
2. Convert heterogeneous provider responses into a common representation.
3. Maintain a canonical record for each recognized vacancy.
4. Preserve references to the original external postings.
5. Identify existing records and avoid unnecessary duplication.
6. Synchronize changes without rebuilding the entire database.
7. Provide an efficient interface for searching and discovering opportunities.

---

# 3. How EmployBoard Works

The platform consists of two primary workflows.

**A. Data ingestion workflow**

Maintains the centralized job database by retrieving, processing and synchronizing information from external ATS providers.

**B. Job discovery workflow**

Allows users to search and filter the standardized information stored in PostgreSQL.

The complete lifecycle is:

```text
                  EXTERNAL DATA SOURCES
                           |
             +-------------+-------------+
             |             |             |
          Ashby          Lever       Greenhouse
             |             |             |
             +-------------+-------------+
                           |
                    SmartRecruiters
                           |
                           v
                   ATS ADAPTER LAYER
                           |
                           v
                    RAW JOB OBJECTS
                           |
                           v
                 DATA NORMALIZATION
                           |
                           v
                  DEDUPLICATION
                           |
                           v
                DATABASE SYNCHRONIZATION
                           |
                           v
                     POSTGRESQL
                           |
              +------------+------------+
              |                         |
              v                         v
        FASTAPI REST API          INGESTION HISTORY
              |
              v
        REACT FRONTEND
              |
              v
       UNIFIED JOB DISCOVERY
              |
              v
        ORIGINAL APPLY URL
```

The ingestion and discovery workflows are deliberately separated.

The frontend does not communicate directly with external ATS APIs. It retrieves already-processed information from the EmployBoard backend.

---

# 4. Technology Stack

| Layer | Technology | Responsibility |
|---|---|---|
| Backend language | Python | Application and ingestion logic |
| Backend framework | FastAPI | REST API and request handling |
| Database | PostgreSQL | Persistent relational storage |
| ORM | SQLAlchemy 2.0 | Asynchronous database access |
| Database migrations | Alembic | Schema versioning |
| Data validation | Pydantic 2 | Request and response validation |
| HTTP client | HTTPX | External API integration |
| Scheduling | APScheduler | Periodic ingestion |
| Frontend framework | React 18 | User interface |
| Frontend language | TypeScript | Static type checking |
| Build tooling | Vite | Development server and production builds |
| Styling | Tailwind CSS | Responsive UI |
| HTML sanitization | DOMPurify | Sanitization of job descriptions |
| Icons | Lucide React | Interface icons |

### Why this stack?

The backend is primarily an I/O-oriented application.

It spends considerable time waiting for external API responses and database operations.

FastAPI, HTTPX and SQLAlchemy's asynchronous interfaces provide a suitable foundation for these workloads.

PostgreSQL was selected because the application needs:

- Relational integrity.
- Structured filtering and querying.
- Referential relationships.
- Unique constraints.
- Transactional updates.
- JSONB support for provider-specific payloads.
- Indexing for frequently queried fields.

React and TypeScript provide a component-based frontend with explicit API response types.

---

# 5. System Architecture

EmployBoard follows a layered architecture.

The major layers are:

### 5.1 Adapter layer

Responsible for understanding provider-specific API formats.

Each adapter:
- Constructs the appropriate API request.
- Retrieves the provider's response.
- Validates the broad response structure.
- Extracts job-specific fields.
- Converts provider-specific information into an `AdapterJob`.

### 5.2 Normalization layer

Responsible for transforming `AdapterJob` objects into the application's canonical `NormalizedJob` representation.

This layer handles:
- Text standardization.
- Enum mapping.
- Location normalization.
- Compensation validation.
- Date parsing.
- URL validation.
- Description processing.
- Skills cleanup.

### 5.3 Deduplication layer

Responsible for identifying whether an incoming vacancy corresponds to an existing canonical job.

It implements a hierarchical matching strategy based on:
- External job identifiers.
- Requisition identifiers.
- Cross-source title and location matching.

### 5.4 Synchronization layer

Responsible for maintaining database state.

It handles:
- New record insertion.
- Existing record updates.
- Source relationship management.
- Missing-job detection.
- Controlled deactivation.
- Detail enrichment.
- Ingestion statistics.

### 5.5 Persistence layer

Uses SQLAlchemy and PostgreSQL to maintain:
- Company records.
- Canonical jobs.
- External job sources.
- Ingestion history.

### 5.6 API layer

Exposes the stored information through REST endpoints.

It handles:
- Search.
- Filtering.
- Sorting.
- Pagination.
- Job details.
- Company information.
- Source information.
- Statistics.
- Administrative synchronization.

---

# 6. Data Sources and ATS Integrations

An Applicant Tracking System (ATS) is software used by organizations to manage recruitment activities, including publishing vacancies, collecting applications and tracking candidates.

EmployBoard consumes the public job-posting interfaces exposed by these platforms.

It does not require access to private recruitment data or candidate records.

The current implementation integrates four providers.

## 6.1 Ashby

**Official documentation:** https://developers.ashbyhq.com/docs/public-job-posting-api

Endpoint:

```http
GET https://api.ashbyhq.com/posting-api/job-board/{board_identifier}
```

The implementation requests compensation information using:

```python
params={"includeCompensation": "true"}
```

The adapter extracts:
- Job identifier.
- Job title.
- Location.
- Department and team.
- Employment type.
- Workplace type.
- Description.
- Compensation.
- Application URL.
- Publication date.

Compensation information is extracted from the provider's compensation structure.

## 6.2 Greenhouse

**Official documentation:** https://developers.greenhouse.io/job-board.html

Endpoint:

```http
GET https://boards-api.greenhouse.io/v1/boards/{board_identifier}/jobs
```

The implementation requests job content:

```python
params={"content": "true"}
```

The adapter extracts:
- Job identifier.
- Title.
- Location.
- Offices.
- Departments.
- Metadata.
- Description.
- Publication date.
- Application URL.
- Requisition identifier, where supplied.

Employment type, workplace type and experience level are extracted from available metadata fields.

Greenhouse descriptions may contain escaped HTML, which is decoded during processing.

## 6.3 Lever

**Official documentation:** https://github.com/lever/postings-api

Endpoint:

```http
GET https://api.lever.co/v0/postings/{board_identifier}
```

The implementation uses:

```python
params={"mode": "json"}
```

The adapter extracts:
- External job ID.
- Job title.
- Department and team.
- Location.
- Employment commitment.
- Workplace type.
- Description sections.
- Requirements.
- Responsibilities.
- Posting date.
- Application URL.

Lever's description sections are inspected using heading-based matching to identify likely requirements and responsibilities.

## 6.4 SmartRecruiters

**Official documentation:** https://developers.smartrecruiters.com/

Job listing endpoint:

```http
GET https://api.smartrecruiters.com/v1/companies/{company}/postings
```

The implementation retrieves listings using pagination:

```python
params={
    "limit": 100,
    "offset": offset
}
```

The adapter extracts:
- Posting ID.
- Job title.
- Department and function.
- Location.
- Employment type.
- Workplace information.
- Experience level.
- Requisition reference.
- Publication date.

SmartRecruiters listing responses do not always contain full job descriptions.

Therefore, the adapter also implements a detail endpoint:

```http
GET https://api.smartrecruiters.com/v1/companies/{company}/postings/{posting_id}
```

This provides additional information about the job, including description sections and application URLs.

The detail enrichment process is bounded to avoid making an excessive number of requests.

### Provider integration summary

| Provider | Companies currently registered | Special handling |
|---|---|---|
| Ashby | Notion, OpenAI, Snowflake | Compensation retrieval |
| Lever | Spotify, Paytm | Description section parsing |
| Greenhouse | GitLab | Content and metadata extraction |
| SmartRecruiters | Bosch | Paginated listing and detail enrichment |

These are the current seeded companies, not a hardcoded limit on the number of companies the architecture can support.

The APIs are public job-posting interfaces. Their accessibility does not imply access to private ATS functionality.

---

# 7. Company Registry

**Location:** `backend/app/database/seed.py`

EmployBoard maintains a company registry that determines which companies are monitored.

Each registry entry contains:

```python
{
    "company_name": "OpenAI",
    "company_slug": "openai",
    "company_logo_url": "...",
    "company_website": "https://openai.com",
    "careers_url": "https://openai.com/careers",
    "ats_provider": "ashby",
    "board_identifier": "openai",
    "config": {}
}
```

The important fields are:

| Field | Purpose |
|---|---|
| `company_name` | Display name |
| `company_slug` | Unique application identifier |
| `ats_provider` | Identifies the ATS adapter |
| `board_identifier` | Identifies the company's ATS board |
| `is_active` | Controls whether the company is included in ingestion |
| `config` | Stores provider/company-specific configuration |

The registry is seeded through:

```bash
python -m app.cli seed
```

### Registry design decision

Company information is stored separately from job postings.

A company can have hundreds of vacancies, but its ATS provider and board configuration should not need to be repeated as independent configuration values throughout the application.

The unique constraint on `(ats_provider, board_identifier)` prevents duplicate board registrations.

Adding a company that uses an existing provider generally requires a new registry entry rather than a new adapter.

---

# 8. Data Ingestion Pipeline

**Primary files:**

- `backend/app/services/ingestion_service.py`
- `backend/app/services/job_sync_service.py`

The ingestion pipeline is responsible for retrieving external data and maintaining the internal database.

## 8.1 Ingestion triggers

There are two supported execution mechanisms.

**Scheduled ingestion**

APScheduler is configured to execute synchronization at a configurable interval.

Default:

```env
ENABLE_SCHEDULER=true
SYNC_INTERVAL_HOURS=6
```

The scheduler invokes:

```python
run_scheduled_sync()
```

**Manual ingestion**

Administrators can trigger ingestion through:

```http
POST /api/admin/sync
```

The same ingestion service is used by both mechanisms.

## 8.2 Loading registered companies

The ingestion service queries the company registry for active companies.

Conceptually:

```python
select(Company).where(
    Company.is_active.is_(True)
)
```

Optional company and provider filters can restrict the ingestion run.

## 8.3 Adapter selection

The registry in:

`backend/app/adapters/registry.py`

maps provider identifiers to adapter classes.

```python
_ADAPTERS = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "ashby": AshbyAdapter,
    "smartrecruiters": SmartRecruitersAdapter,
}
```

The ingestion service uses:

```python
adapter = build_adapter(
    company.ats_provider,
    client,
    settings
)
```

This isolates provider-specific API logic from the central ingestion workflow.

## 8.4 Fetching data

Each adapter implements:

```python
async def fetch_jobs(
    self,
    company: Company
) -> list[AdapterJob]:
```

The adapter retrieves the company's published postings and converts them into provider-neutral `AdapterJob` objects.

## 8.5 Processing records

Each returned job passes through:

1. Normalization.
2. Deduplication.
3. Database insertion or update.
4. Source metadata maintenance.

The processing of individual jobs uses nested database transactions through SQLAlchemy savepoints.

This allows an individual invalid or problematic job record to be skipped without necessarily aborting the entire company's ingestion.

## 8.6 Detail enrichment

Adapters can optionally implement:

```python
fetch_detail()
```

SmartRecruiters uses this capability.

The synchronization service:
- Finds active jobs without descriptions.
- Prioritizes newer postings.
- Retrieves additional details.
- Normalizes the returned information.
- Updates the canonical record.
- Preserves the detail payload in the source record.

The company registry supports a `detail_limit` setting.

Bosch currently has a configured detail limit of 100.

## 8.7 Ingestion statistics

Each company synchronization records:
- Jobs fetched.
- Jobs inserted.
- Jobs updated.
- Jobs deactivated.
- Jobs skipped.
- Validation errors.
- Upsert errors.
- Detail enrichment errors.

A synchronization run can be marked as:
- `running`
- `success`
- `partial`
- `failed`

The results are stored in `ingestion_runs`.

---

# 9. Data Normalization

**Location:** `backend/app/services/normalization_service.py`

Normalization is responsible for transforming heterogeneous provider responses into a common internal representation.

The pipeline uses two main data structures:

```text
Provider API JSON
       |
       v
   AdapterJob
       |
       v
Normalization Service
       |
       v
  NormalizedJob
       |
       v
  Database Sync
```

## 9.1 Canonical enums

The application defines standardized values in:

`backend/app/models/enums.py`

### Employment type

Supported values:

- Full-time
- Part-time
- Contract
- Internship
- Temporary
- Other

Examples:

```text
FullTime       -> Full-time
Permanent      -> Full-time
Contractor     -> Contract
Trainee        -> Internship
Seasonal       -> Temporary
```

### Workplace type

Supported values:

- Remote
- Hybrid
- On-site
- Unknown

Examples:

```text
WFH             -> Remote
Remote First    -> Remote
Hybrid Remote   -> Hybrid
In Office       -> On-site
```

### Experience level

Supported values:

- Entry
- Junior
- Mid
- Senior
- Lead
- Executive
- Unknown

Examples:

```text
Graduate       -> Entry
Associate      -> Junior
Intermediate   -> Mid
Senior Level   -> Senior
Principal      -> Lead
Director       -> Executive
```

These mappings are implemented using provider-independent dictionaries.

## 9.2 Text normalization

The utility module provides:

- Whitespace normalization.
- Accent removal.
- Title normalization.
- Location normalization.
- HTML entity decoding.
- URL validation.

For example:

```text
"Senior Software Engineer"
             |
             v
"senior software engineer"
```

The original title remains available for display.

The normalized title is used for comparison and matching.

Location normalization similarly converts text into a consistent lowercase representation.

## 9.3 Compensation normalization

Salary values are parsed into Python `Decimal` values.

The normalization service:
- Parses numeric values.
- Rejects negative values.
- Rejects invalid minimum/maximum combinations.
- Normalizes currency codes.
- Standardizes salary intervals.

Supported interval representations include:

- Year
- Month
- Week
- Day
- Hour

The implementation standardizes salary representation but does not perform currency conversion.

## 9.4 Date normalization

Provider dates may arrive as:
- ISO-formatted strings.
- Date-only strings.
- Unix timestamps.
- Millisecond timestamps.

The utility layer converts supported representations into timezone-aware UTC datetimes.

Lever timestamps are handled as milliseconds when appropriate.

## 9.5 HTML and description handling

Descriptions are preserved as HTML where supplied.

Greenhouse HTML entities are decoded during normalization.

Lever and SmartRecruiters descriptions can be divided into:
- General description.
- Requirements.
- Responsibilities.

Description snippets are generated separately for job-list responses.

## 9.6 Skills normalization

The skills cleaner:
- Accepts list-based input.
- Ignores non-string values.
- Normalizes whitespace.
- Removes case-insensitive duplicates.
- Limits individual values to 80 characters.
- Limits the list to 50 entries.

Missing provider fields remain nullable rather than being fabricated.

### Normalization design decision

Provider-specific extraction and provider-independent normalization are deliberately separated.

An ATS adapter should understand how to extract a value from its provider's response.

It should not decide the application's canonical employment type, experience-level policy or database matching strategy.

This makes the normalization rules reusable across all integrations.

---

# 10. Deduplication Strategy

**Location:** `backend/app/services/deduplication_service.py`

EmployBoard distinguishes between an external posting and a canonical job record.

The same underlying vacancy can potentially be represented by multiple external sources.

The deduplication service uses a hierarchical matching strategy.

## Level 1: External source identity

The strongest matching mechanism is:

```text
ATS provider + External job ID
```

The database checks `job_sources`.

A matching record means EmployBoard has already encountered that specific external posting.

The existing canonical job is updated instead of creating another one.

A unique database constraint reinforces this:

```sql
UNIQUE (ats_provider, external_job_id)
```

## Level 2: Requisition identifier

If the external identifier differs, the system checks for an existing active job with:

```text
Same company_id
Same requisition_id
```

This match is scoped to one company because requisition identifiers are not necessarily globally unique.

When a match is found:
- The existing canonical job is reused.
- A new `job_sources` record is created.
- The external posting is associated with the existing canonical job.

## Level 3: Cross-source candidate detection

When a requisition match is unavailable, the system checks:

- Same company.
- Same normalized title.
- Same normalized location.
- At least one existing source from a different ATS provider.

A matching record is treated as a possible duplicate.

The incoming job is flagged using:

```python
duplicate_of_job_id
```

It is not automatically merged.

### Why conservative matching?

Two vacancies can legitimately have the same title and location.

Automatically merging records based only on similar text could destroy valid job information.

EmployBoard therefore distinguishes confirmed identity matches from potential duplicates.

### Deduplication summary

| Level | Matching criteria | Action |
|---|---|---|
| 1 | Provider + external ID | Update existing job |
| 2 | Company + requisition ID | Reuse canonical job |
| 3 | Company + normalized title + location + different provider | Flag possible duplicate |

The current implementation does not use machine learning or fuzzy similarity scoring for duplicate detection.

---

# 11. Synchronization and Job Lifecycle Management

**Location:** `backend/app/services/job_sync_service.py`

Synchronization maintains the internal representation of external job postings over time.

It handles three primary scenarios:

1. New jobs.
2. Updated jobs.
3. Missing or withdrawn jobs.

## 11.1 Insert-or-update behaviour

For every incoming normalized job:

1. Search for an existing source record.
2. If found, update its canonical job.
3. Otherwise, search for a requisition match.
4. If found, associate the new source with that job.
5. Otherwise, create a new canonical job.
6. Check for a possible cross-source duplicate.
7. Create the corresponding source record.

The synchronization service also updates:
- `last_seen_at`
- `last_verified_at`
- `fetched_at`
- `missing_sync_count`

## 11.2 Preserve missing information

External APIs do not always return every optional field.

An existing job might contain a description or salary range that is absent from a later API response.

The `_apply_job_fields()` function uses:

```python
if value is None and preserve_missing:
    continue
```

This prevents missing optional values from unnecessarily overwriting previously available information.

When a job is observed again:
- It is reactivated.
- Its missing counter is reset.
- Its last-seen timestamp is updated.

## 11.3 Detect missing jobs

After processing the latest API response, the system compares the external identifiers seen during the run with previously active source-linked jobs.

A missing posting is not immediately deleted.

Instead, the system increments:

```text
missing_sync_count
```

The default threshold is:

```env
DEACTIVATION_MISS_THRESHOLD=2
```

After the configured number of consecutive confirmed absences, the canonical job can be deactivated.

## 11.4 Deactivation safeguards

The system has additional checks before deactivation.

**Empty response protection**

If an API returns zero jobs, deactivation is skipped.

**Fetch-ratio protection**

The system compares the current fetched count against the previously active job count for that provider and company.

The default minimum fetch ratio is:

```env
DEACTIVATION_MIN_FETCH_RATIO=0.25
```

If the latest response is suspiciously small, deactivation is skipped.

**Multiple-source protection**

If a canonical job is still supported by another ATS provider, the disappearance of one provider's source does not automatically deactivate the canonical job.

## 11.5 Soft deactivation

Jobs are retained in PostgreSQL.

Their status changes through:

```text
is_active = TRUE
```

or:

```text
is_active = FALSE
```

This avoids immediately destroying historical records.

It also allows the application to distinguish currently discoverable vacancies from previously collected postings.

---

# 12. Database Architecture

EmployBoard uses PostgreSQL with SQLAlchemy 2.0's asynchronous ORM.

The core relational model consists of four tables:

1. `companies`
2. `jobs`
3. `job_sources`
4. `ingestion_runs`

## 12.1 Entity relationship overview

```text
                 COMPANIES
                 ----------
                 company_id PK
                 company_name
                 ats_provider
                 board_identifier
                      |
                      | 1
                      |
                      | N
                    JOBS
                    ----
                    job_id PK
                    company_id FK
                    title
                    normalized_title
                    location
                    employment_type
                    workplace_type
                    experience_level
                    salary_min
                    salary_max
                    is_active
                    duplicate_of_job_id
                      |
                      | 1
                      |
                      | N
                 JOB_SOURCES
                 -----------
                 source_id PK
                 job_id FK
                 ats_provider
                 external_job_id
                 source_payload
                 fetched_at
                 last_verified_at


              INGESTION_RUNS
              --------------
              run_id PK
              company_id FK
              ats_provider
              status
              jobs_fetched
              jobs_inserted
              jobs_updated
              jobs_deactivated
              errors
```

The `ingestion_runs` table independently tracks ingestion activity.

## 12.2 Companies

Stores the company registry.

Important fields:

| Column | Purpose |
|---|---|
| `company_id` | Primary key |
| `company_name` | Display name |
| `company_slug` | Unique application slug |
| `company_logo_url` | Logo URL |
| `company_website` | Company website |
| `careers_url` | Careers page |
| `ats_provider` | ATS platform |
| `board_identifier` | External board identifier |
| `is_active` | Registry activation state |
| `config` | Provider-specific JSONB configuration |

Constraints:
- Primary key on `company_id`.
- Unique company slug.
- Unique provider and board identifier combination.
- Check constraint for supported ATS providers.

## 12.3 Jobs

Stores canonical job postings.

Important fields:

| Column | Purpose |
|---|---|
| `job_id` | Canonical primary key |
| `company_id` | Company foreign key |
| `title` | Original job title |
| `normalized_title` | Normalized title |
| `normalized_location` | Normalized location |
| `requisition_id` | External requisition identifier |
| `department` | Department |
| `location` | Display location |
| `employment_type` | Canonical employment type |
| `workplace_type` | Canonical workplace type |
| `experience_level` | Canonical experience level |
| `salary_min` | Minimum compensation |
| `salary_max` | Maximum compensation |
| `salary_currency` | Currency code |
| `salary_interval` | Compensation interval |
| `description` | Job description |
| `requirements` | Requirements |
| `responsibilities` | Responsibilities |
| `skills` | JSONB skill list |
| `posted_at` | Posting date |
| `expires_at` | Expiration date |
| `application_url` | Application URL |
| `is_active` | Current discoverability |
| `missing_sync_count` | Consecutive missing count |
| `duplicate_of_job_id` | Possible duplicate reference |
| `first_seen_at` | First ingestion timestamp |
| `last_seen_at` | Latest observation timestamp |

UUIDs are used for canonical identifiers.

The database enforces valid enum values and compensation constraints.

## 12.4 Job sources

Stores the relationship between canonical jobs and external ATS postings.

Important fields:

| Column | Purpose |
|---|---|
| `source_id` | Primary key |
| `job_id` | Canonical job foreign key |
| `ats_provider` | External provider |
| `external_job_id` | Provider-specific identifier |
| `original_job_url` | Original posting URL |
| `source_payload` | Original provider JSON |
| `fetched_at` | Latest fetch timestamp |
| `last_verified_at` | Latest verification timestamp |

The combination of `ats_provider` and `external_job_id` is unique.

### Why separate jobs and job_sources?

A canonical job represents the internal business entity.

A source represents an external provider's representation of that entity.

For example:

```text
Canonical Job: J1
Title: Data Engineer
Location: Bengaluru

       /             \
      /               \
 Ashby Source       Lever Source
 ASH-123             LEV-789
```

This design provides:
- Source traceability.
- External identifier preservation.
- Cross-provider matching.
- A single canonical job representation.
- The ability to associate multiple source records with one job.

It also prevents provider-specific identifiers from becoming the application's primary job identity.

## 12.5 Ingestion runs

Stores synchronization execution history.

Important fields:

| Column | Purpose |
|---|---|
| `run_id` | Primary key |
| `company_id` | Associated company |
| `ats_provider` | Provider |
| `company_name` | Company snapshot |
| `started_at` | Execution start |
| `finished_at` | Execution finish |
| `status` | Run status |
| `jobs_fetched` | Parsed jobs fetched |
| `jobs_inserted` | New jobs |
| `jobs_updated` | Updated or linked jobs |
| `jobs_deactivated` | Deactivated jobs |
| `jobs_skipped` | Skipped jobs |
| `errors` | Structured JSONB errors |
| `error_message` | Overall failure message |

This table provides the foundation for ingestion observability and operational debugging.

---

# 13. Database Design Decisions

Several database decisions are particularly important.

## 13.1 Relational modelling

Company, job and source entities are represented separately.

This reduces duplication and establishes clear ownership of data.

A company can have many jobs, and a canonical job can have many source references.

## 13.2 UUID primary keys

UUIDs are used instead of relying on external ATS identifiers.

External identifiers:
- Are controlled by third parties.
- Can differ across providers.
- Are not guaranteed to be globally unique.

The application's internal identifiers should remain independent of those systems.

## 13.3 JSONB

JSONB is used for:
- Company configuration.
- Original source payloads.
- Skill lists.
- Ingestion error details.

This provides flexibility for semi-structured information without making every provider-specific field part of the canonical relational schema.

## 13.4 Numeric compensation

Salary fields use:

```sql
NUMERIC(14, 2)
```

This avoids floating-point representation issues for monetary values.

## 13.5 Constraints

Database-level constraints protect important invariants.

Examples include:
- Supported ATS providers.
- Supported employment types.
- Supported workplace types.
- Supported experience levels.
- Non-negative salary values.
- Minimum salary not exceeding maximum salary.
- Unique source identifiers.

Validation therefore happens at more than one layer.

## 13.6 Indexing strategy

The schema defines indexes for frequently accessed fields.

These include:
- Company and active status.
- Active status and posting date.
- Active status and update date.
- Employment type.
- Workplace type.
- Experience level.
- Department.
- Location.
- Normalized title.
- Normalized location.
- Job-source relationships.
- Provider verification timestamps.
- Ingestion history timestamps.

The skills JSONB column uses a GIN index.

PostgreSQL's `pg_trgm` extension is also enabled through the initial migration, with trigram indexes for relevant text-search fields.

## 13.7 Transactions and savepoints

Database changes are managed through SQLAlchemy transactions.

Individual job upserts use nested transactions, which provide savepoint isolation.

This allows the pipeline to recover from an individual record failure without necessarily abandoning every other valid record in that company's run.

Company synchronization is committed as a transaction, while ingestion-run creation and completion are recorded separately.

## 13.8 Migrations

Alembic manages schema changes.

The initial schema is defined in:

```text
backend/alembic/versions/
```

This provides versioned database structure rather than relying on manually recreating tables.

---

# 14. Backend Architecture

The backend is organized into modular packages.

```text
backend/app/
│
├── adapters/
│   ├── base.py
│   ├── registry.py
│   ├── ashby.py
│   ├── greenhouse.py
│   ├── lever.py
│   └── smartrecruiters.py
│
├── api/
│   ├── deps.py
│   └── routes/
│       ├── admin.py
│       ├── companies.py
│       ├── health.py
│       ├── jobs.py
│       ├── sources.py
│       └── stats.py
│
├── database/
│   ├── connection.py
│   ├── repositories.py
│   └── seed.py
│
├── models/
│   ├── base.py
│   ├── company.py
│   ├── enums.py
│   ├── ingestion_run.py
│   ├── job.py
│   └── job_source.py
│
├── schemas/
│   ├── job.py
│   └── serializers.py
│
├── services/
│   ├── deduplication_service.py
│   ├── ingestion_service.py
│   ├── job_sync_service.py
│   └── normalization_service.py
│
├── utils/
│   └── text.py
│
├── cli.py
├── config.py
├── logging_config.py
└── main.py
```

### Responsibilities

**Adapters**

External API communication and provider-specific parsing.

**API routes**

HTTP request handling, parameter validation and response generation.

**Database**

Connection management, repository queries and company registry seeding.

**Models**

SQLAlchemy relational models and database constraints.

**Schemas**

Pydantic request and response structures.

**Services**

Business logic for normalization, deduplication and synchronization.

**Utilities**

Shared parsing, formatting and validation functions.

### Asynchronous database architecture

The database engine uses SQLAlchemy's asynchronous interfaces with `asyncpg`.

The session factory is configured with:
- `expire_on_commit=False`
- `autoflush=False`
- Connection pool settings.
- Pool pre-ping.
- Connection recycling.

Alembic uses the synchronous Psycopg driver for migrations.

This separates asynchronous runtime database operations from migration execution.

---

# 15. API Reference

The FastAPI backend exposes public job discovery endpoints and protected administrative endpoints.

Interactive API documentation is available at:

```text
http://localhost:8000/docs
```

## 15.1 Public endpoints

### GET `/api/jobs`

Returns a paginated list of active jobs.

Supported query parameters:

| Parameter | Description |
|---|---|
| `q` | Search query |
| `page` | Page number |
| `limit` | Results per page, maximum 100 |
| `location` | Location filter |
| `company` | Company name or UUID |
| `ats` | ATS provider |
| `employment_type` | Employment type |
| `workplace_type` | Workplace type |
| `experience_level` | Experience level |
| `department` | Department |
| `date_posted` | all, 24h, 7d, 30d |
| `sort` | posted_desc, updated_desc, company_asc |

Example:

```http
GET /api/jobs?q=Data%20Engineer&location=India&page=1&limit=20
```

### GET `/api/jobs/{job_id}`

Returns detailed information about a specific job.

Includes:
- Job description.
- Requirements.
- Responsibilities.
- Skills.
- Company details.
- Source references.
- Requisition identifier.
- Duplicate reference, where present.

### GET `/api/jobs/facets`

Returns available filter values and their counts.

Includes:
- Locations.
- Departments.
- Employment types.
- Workplace types.
- Experience levels.
- ATS providers.
- Total active jobs.

### GET `/api/companies`

Returns registered companies, including:
- Company information.
- Active job count.
- Total job count.
- Last successful or partial synchronization timestamp.
- Verification note.

### GET `/api/sources`

Returns integrated ATS provider information.

Includes:
- Provider display name.
- Documentation URL.
- Company count.
- Active job count.
- Last successful synchronization.
- Provider status.

### GET `/api/stats`

Returns platform statistics, including:
- Active jobs.
- Total companies.
- Active companies.
- Integrated providers.
- Total job-source records.
- Last successful synchronization.
- Latest ingestion status.
- Provider-wise active job counts.

### GET `/api/health`

Checks backend availability and database connectivity.

Returns:
- Application status.
- Database status.
- Version.
- Environment.
- Scheduler configuration.
- Timestamp.

## 15.2 Administrative endpoints

### POST `/api/admin/sync`

Triggers manual synchronization.

Protected using the configured admin secret.

Optional request body:

```json
{
  "company_ids": [],
  "providers": [
    "ashby"
  ]
}
```

By default, the operation runs as a FastAPI background task.

To wait for the result synchronously:

```http
POST /api/admin/sync?wait=true
```

### GET `/api/admin/sync/runs`

Returns recent ingestion history.

Supports:

```text
limit=20
```

Maximum: 100.

This endpoint also requires admin authentication.

---

# 16. Frontend Architecture

The frontend is built with React 18, TypeScript and Vite.

Its primary responsibility is to provide a unified interface for browsing the canonical job dataset.

```text
frontend/src/
│
├── components/
│   ├── ActiveFilters.tsx
│   ├── CompanyLogo.tsx
│   ├── FilterPanel.tsx
│   ├── Footer.tsx
│   ├── Header.tsx
│   ├── JobCard.tsx
│   ├── JobDetailPanel.tsx
│   ├── Pagination.tsx
│   ├── SearchToolbar.tsx
│   └── States.tsx
│
├── hooks/
│   ├── useDebouncedValue.ts
│   ├── useUrlState.ts
│   └── useViewport.ts
│
├── lib/
│   ├── filters.ts
│   └── format.ts
│
├── App.tsx
├── api.ts
├── index.css
├── main.tsx
└── types.ts
```

## 16.1 Component architecture

The interface is divided into reusable components.

**Header**

Displays application branding and platform statistics.

**SearchToolbar**

Provides search and sorting controls.

**FilterPanel**

Provides filtering by company, location, ATS, employment type, workplace type, experience level, department and posting date.

**ActiveFilters**

Displays currently applied filters and allows individual filters to be removed.

**JobCard**

Displays summarized job information.

**JobDetailPanel**

Displays full job information and application links.

**Pagination**

Controls result navigation.

**States**

Handles loading, error and empty-result states.

## 16.2 URL-based application state

The `useUrlState` hook keeps search and filter state synchronized with URL parameters.

This allows users to:
- Preserve their current search.
- Share a filtered results URL.
- Navigate between pages.
- Open a selected job using its identifier.

## 16.3 Debounced search

The main search input uses a 350 ms debounce.

This prevents an API request from being sent for every keystroke.

Location filtering also uses debouncing.

## 16.4 Request cancellation

The frontend uses `AbortController` to cancel obsolete requests when the user changes filters or navigates to another result.

This reduces unnecessary network activity and prevents stale responses from replacing newer results.

## 16.5 API client

All frontend requests are centralized in:

```text
frontend/src/api.ts
```

The API client provides:
- Typed request methods.
- Query-string construction.
- Error parsing.
- Request timeouts.
- Cancellation support.

## 16.6 Job description safety

Job descriptions may contain externally supplied HTML.

The detail component uses DOMPurify before rendering HTML content.

This is an important security measure when displaying externally sourced markup.

---

# 17. Search, Filtering and Pagination

Search operations are performed against PostgreSQL rather than against the frontend's locally loaded job collection.

The repository layer builds SQLAlchemy queries dynamically.

## Search fields

The general search query checks:
- Job title.
- Company name.
- Location.
- Department.
- Skills.

It does not currently perform full-text search across the complete job description.

## Filters

The repository supports:
- Active-job filtering.
- Company matching by UUID or partial company name.
- ATS source filtering.
- Employment type.
- Workplace type.
- Experience level.
- Location.
- Department.
- Posting date.

## Sorting

Three sorting options are supported:

| Sort | Behaviour |
|---|---|
| `posted_desc` | Newest posting dates first |
| `updated_desc` | Recently updated records first |
| `company_asc` | Alphabetical company order |

Null posting dates are handled explicitly in the default posting-date sort.

## Pagination

The repository performs:
1. A filtered count query.
2. A paginated result query.
3. Relationship loading for company and source information.

The default page size is 20.

The maximum page size is 100.

The API returns:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "limit": 20,
  "pages": 0,
  "sort": "posted_desc"
}
```

The actual values depend on the database contents and requested filters.

---

# 18. Error Handling and Reliability

EmployBoard handles failures at multiple layers.

## 18.1 HTTP request handling

The shared HTTP request utility is implemented in:

```text
backend/app/adapters/base.py
```

It provides:
- Configurable request timeouts.
- Network error handling.
- Retry support.
- Retry-After header handling.
- Bounded exponential backoff.
- JSON response validation.

Retryable conditions include:
- Network failures.
- Timeouts.
- HTTP 429.
- HTTP 5xx.

Non-retryable conditions include:
- HTTP 404.
- HTTP 401.
- HTTP 403.
- Other unsuccessful HTTP responses.

## 18.2 Rate-conscious ingestion

The ingestion service:
- Uses a shared asynchronous HTTP client.
- Limits connection pool size.
- Identifies itself using a configured User-Agent.
- Waits briefly between independent company sources.

## 18.3 Record-level failures

A malformed job does not necessarily invalidate an entire company's ingestion.

Normalization failures and individual upsert failures are recorded and skipped.

The maximum number of stored error details per company run is bounded.

## 18.4 Company-level failures

Each company is synchronized independently.

If one company fails, the ingestion service records the failure and proceeds to the next company.

The overall cycle can therefore finish with a `partial` status.

## 18.5 Synchronization locking

A PostgreSQL advisory lock prevents overlapping ingestion cycles using the same lock identifier.

This is useful when scheduled and manually triggered ingestion occur at approximately the same time.

## 18.6 Logging

The application uses Python's logging framework.

HTTP client logs are reduced to warning level to avoid excessive request-level output.

---

# 19. Security and Access Control

EmployBoard is designed as a public job-discovery application.

Ordinary job discovery does not require user authentication.

## Public API

The following endpoints are publicly accessible:
- Job listing.
- Job details.
- Search facets.
- Companies.
- Sources.
- Statistics.
- Health check.

These expose job-discovery information rather than private candidate information.

## Administrative protection

Administrative operations require an `ADMIN_SECRET`.

The application accepts either:

```http
X-Admin-Secret: your-secret
```

or:

```http
Authorization: Bearer your-secret
```

The secret is checked using constant-time comparison.

If no admin secret is configured, administrative operations are disabled.

## CORS

Allowed frontend origins are configurable using:

```env
CORS_ORIGINS=
```

The application does not enable credentialed CORS requests.

## Database credentials

Database connection strings and administrative secrets belong in environment variables.

They should never be committed to version control.

## HTML sanitization

Externally sourced job descriptions are sanitized using DOMPurify before being rendered in the frontend.

## Production considerations

Before operating a public production deployment, additional controls should be considered:

- Rate limiting.
- Request-volume monitoring.
- Secret rotation.
- Restricting API documentation exposure if appropriate.
- Database backup and recovery.
- Monitoring of administrative operations.
- HTTPS enforcement.
- Deployment-specific network restrictions.

---

# 20. Project Structure

The complete repository is organized as:

```text
EmployBoard/
│
├── backend/
│   │
│   ├── app/
│   │   ├── adapters/
│   │   ├── api/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── utils/
│   │   ├── cli.py
│   │   ├── config.py
│   │   ├── logging_config.py
│   │   └── main.py
│   │
│   ├── alembic/
│   │   └── versions/
│   │
│   ├── tests/
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
│
├── frontend/
│   │
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   ├── index.css
│   │   ├── main.tsx
│   │   └── types.ts
│   │
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
│
└── .gitignore
```

Generated dependencies, virtual environments and build output are intentionally excluded from the repository.

---

# 21. Getting Started

## Prerequisites

Install:

- Python 3.12.
- Node.js and npm.
- PostgreSQL.
- Git.

A PostgreSQL instance can be hosted locally or through a managed PostgreSQL provider.

Examples include Neon and other PostgreSQL-compatible services.

## Clone the repository

```bash
git clone <repository-url>
cd EmployBoard
```

## Create the database

Using PostgreSQL:

```sql
CREATE DATABASE employboard;
```

Alternatively, create a hosted PostgreSQL database and obtain its connection string.

---

# 22. Environment Configuration

## Backend configuration

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

For development dependencies:

```bash
pip install -r requirements-dev.txt
```

Create the environment file:

**Windows**

```powershell
Copy-Item .env.example .env
```

**macOS / Linux**

```bash
cp .env.example .env
```

Configure the database connection:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/employboard
```

For a hosted PostgreSQL provider, use its supplied connection string.

The configuration layer converts compatible PostgreSQL connection strings into the appropriate SQLAlchemy driver formats.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | Local PostgreSQL | Database connection |
| `ADMIN_SECRET` | Empty | Admin authentication secret |
| `CORS_ORIGINS` | Local frontend origins | Allowed frontend origins |
| `ENVIRONMENT` | development | Application environment |
| `LOG_LEVEL` | INFO | Logging level |
| `ENABLE_SCHEDULER` | true | Enables in-process scheduling |
| `SYNC_INTERVAL_HOURS` | 6 | Scheduled synchronization interval |
| `SEED_ON_STARTUP` | false | Seeds company registry at startup |
| `HTTP_TIMEOUT_SECONDS` | 30 | External request timeout |
| `HTTP_MAX_RETRIES` | 3 | Maximum retries |
| `USER_AGENT` | EmployBoard identifier | External request identification |
| `SMARTRECRUITERS_DETAIL_LIMIT` | 100 | Default detail enrichment limit |
| `DEACTIVATION_MISS_THRESHOLD` | 2 | Required consecutive absences |
| `DEACTIVATION_MIN_FETCH_RATIO` | 0.25 | Minimum response-size safety ratio |

Generate an administrative secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Store the generated value in `ADMIN_SECRET`.

Do not commit `.env` files.

---

# 23. Running the Application

EmployBoard requires the backend and frontend to run independently during local development.

## Step 1: Apply database migrations

From the backend directory:

```bash
alembic upgrade head
```

This initializes the database schema.

## Step 2: Seed the company registry

```bash
python -m app.cli seed
```

This inserts or updates the configured company registry.

The current seed includes:

- Notion.
- OpenAI.
- Snowflake.
- Spotify.
- Paytm.
- Bosch.
- GitLab.

The seed operation is designed to be repeatable.

## Step 3: Verify external integrations

```bash
python -m app.cli verify
```

This checks the configured ATS integrations by fetching their job boards.

It does not write the retrieved jobs into PostgreSQL.

You can also verify an individual company:

```bash
python -m app.cli verify --company openai
```

Or a particular provider:

```bash
python -m app.cli verify --provider ashby
```

## Step 4: Run initial synchronization

```bash
python -m app.cli sync
```

This retrieves the configured job postings and populates the database.

For an individual company:

```bash
python -m app.cli sync --company openai
```

For one ATS provider:

```bash
python -m app.cli sync --provider greenhouse
```

## Step 5: Start the backend

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Health endpoint:

```text
http://127.0.0.1:8000/api/health
```

## Step 6: Start the frontend

Open another terminal.

Navigate to:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start Vite:

```bash
npm run dev
```

Frontend:

```text
http://localhost:5173
```

The Vite development server proxies `/api` requests to:

```text
http://127.0.0.1:8000
```

Both processes must remain running during local development.

---

# 24. CLI Commands

EmployBoard includes a command-line interface for managing the ingestion pipeline.

All commands are executed from the backend directory.

| Command | Purpose |
|---|---|
| `python -m app.cli seed` | Seed or update companies |
| `python -m app.cli verify` | Verify external API connectivity |
| `python -m app.cli sync` | Run ingestion |
| `python -m app.cli stats` | Display database statistics |
| `python -m app.cli runs` | Display recent ingestion history |

### Additional options

Verify a company:

```bash
python -m app.cli verify --company openai
```

Synchronize a company:

```bash
python -m app.cli sync --company openai
```

Synchronize one provider:

```bash
python -m app.cli sync --provider ashby
```

Display recent runs:

```bash
python -m app.cli runs --limit 10
```

The CLI is useful for initial setup, manual ingestion, troubleshooting and inspecting database state.

---

# 25. Database Migrations

EmployBoard uses Alembic for schema version management.

Initial migration:

```bash
alembic upgrade head
```

Inspect the current revision:

```bash
alembic current
```

Inspect migration history:

```bash
alembic history
```

Generate a migration after changing SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe schema change"
```

Apply the migration:

```bash
alembic upgrade head
```

Downgrade one revision when appropriate:

```bash
alembic downgrade -1
```

Generated migrations should always be reviewed before applying them to a production database.

---

# 26. Deployment Considerations

EmployBoard consists of two independently deployable applications.

**Frontend**

The frontend can be deployed as a static Vite application.

Build:

```bash
npm run build
```

The generated static assets are placed in:

```text
frontend/dist/
```

The repository includes a `_redirects` file for SPA routing on compatible static hosting platforms.

For a production deployment, configure:

```env
VITE_API_BASE_URL=https://your-backend-domain.com/api
```

**Backend**

The FastAPI application can run on an ASGI-compatible hosting service.

Example:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Production deployment should configure:
- PostgreSQL connection.
- Admin secret.
- Allowed CORS origins.
- Environment variables.
- Logging.
- Database migrations.
- Synchronization scheduling.

### Scheduler deployment

The current scheduler runs inside the FastAPI application process.

For a single backend instance, this is suitable for an MVP.

If deploying multiple backend instances, avoid independently scheduling ingestion on every instance.

Set:

```env
ENABLE_SCHEDULER=false
```

when using an external cron or dedicated scheduled process.

The PostgreSQL advisory lock provides protection against overlapping ingestion cycles, but it does not replace a dedicated distributed job-processing system.

### Important deployment distinction

The repository contains the application code and frontend build configuration. It does not include a complete production infrastructure definition or a dedicated distributed worker deployment.

Those deployment components need to be configured separately.

---

# 27. Performance and Scalability

Several implementation decisions support the current application's expected workload.

## Asynchronous I/O

HTTPX and SQLAlchemy use asynchronous interfaces for external requests and database operations.

This avoids blocking the event loop while waiting for I/O.

## Connection pooling

The SQLAlchemy engine uses:
- Pool size: 5.
- Maximum overflow: 10.
- Pool pre-ping.
- Connection recycling.

These are configurable implementation defaults.

## Controlled external requests

The ingestion service uses bounded HTTP connection pools and retries.

It also introduces a short delay between independent company integrations.

## Database indexing

Indexes are defined for frequently filtered fields and source relationships.

This reduces the need for unrestricted table scans for common query patterns.

## Pagination

Job listing endpoints limit the maximum number of returned results to 100.

This avoids returning an unnecessarily large result set in a single API response.

## Bounded detail enrichment

SmartRecruiters detail enrichment is limited by company configuration.

This avoids making one detail request for every posting on every synchronization cycle.

### Future scaling direction

For significantly larger ingestion workloads, the architecture could evolve towards:

- Dedicated ingestion workers.
- A distributed task queue.
- Provider-specific concurrency limits.
- Separate scheduling infrastructure.
- Redis-backed caching.
- Full-text search infrastructure.
- Database query-plan analysis.
- Partitioning or archival policies where justified.

These are potential extensions, not current components.

---

# 28. Current Limitations

EmployBoard is currently designed as a job discovery and aggregation MVP.

The following limitations are important to understand.

## Data availability

Not every ATS provider exposes the same information.

Salary, experience level, workplace type, requirements and skills may be missing from individual postings.

EmployBoard preserves missing values rather than inventing information.

## ATS coverage

The current implementation supports four ATS providers and seven registered companies.

Companies using other recruitment systems require additional integrations.

## Duplicate resolution

External IDs and requisition identifiers provide stronger matching.

Cross-source title and location matching identifies possible duplicates but does not automatically resolve them.

A manual review or more advanced resolution workflow is not currently implemented.

## Search

General search currently checks titles, company names, locations, departments and skills.

It does not provide complete full-text search across descriptions and requirements.

## Synchronization infrastructure

The scheduler runs in-process.

There is no dedicated distributed task queue or durable worker infrastructure.

## User accounts

The current platform does not implement user registration or authentication for job discovery.

## Saved jobs and alerts

User-specific saved jobs, application tracking and job alert subscriptions are not currently implemented.

## Application processing

EmployBoard redirects users to the original application URL.

It does not submit applications or interact with private ATS candidate-management systems.

## Testing

The repository includes a development requirements file with pytest and pytest-asyncio dependencies and a test configuration, but the supplied project archive does not contain an implemented automated test suite.

Automated integration, unit and regression tests remain an important development priority.

---

# 29. Future Improvements

Potential development directions are organized by engineering area.

## Data engineering

- Add more ATS providers.
- Introduce provider-specific ingestion metrics.
- Improve source freshness tracking.
- Add richer field completeness measurements.
- Implement schema drift detection.
- Add a review workflow for potential duplicates.
- Improve historical job lifecycle analytics.

## Database engineering

- Analyze query plans using `EXPLAIN ANALYZE`.
- Add full-text search using PostgreSQL.
- Review indexes against actual query workloads.
- Introduce archival policies for historical records.
- Evaluate materialized views for frequently requested statistics.

## Backend engineering

- Add automated adapter tests.
- Add normalization regression tests.
- Add synchronization failure tests.
- Introduce dedicated background workers.
- Implement API rate limiting.
- Improve structured observability.
- Add more granular administrative controls.

## Frontend engineering

- Add saved searches.
- Add job bookmarking.
- Add personalized job alerts.
- Improve search relevance.
- Introduce richer company profiles.
- Add advanced job-detail navigation.

## Infrastructure

- Add CI/CD.
- Automate database migration checks.
- Add uptime and ingestion monitoring.
- Configure scheduled external ingestion.
- Introduce automated backups.
- Add load testing.

---

# 30. Technical Design Decisions

This section summarizes the major architectural decisions behind EmployBoard.

| Design decision | Reason |
|---|---|
| Public ATS APIs instead of HTML scraping | Consume structured job data directly from recruitment platforms |
| Adapter pattern | Isolate provider-specific API behaviour |
| Common `AdapterJob` representation | Decouple provider parsing from application logic |
| Separate normalization service | Centralize canonical data rules |
| Canonical `jobs` table | Maintain one internal representation of a recognized vacancy |
| Separate `job_sources` table | Preserve external identity and source provenance |
| Hierarchical deduplication | Balance exact identity matching with conservative duplicate detection |
| Soft deactivation | Preserve historical job records |
| Missing-field preservation | Prevent incomplete API responses from unnecessarily erasing information |
| PostgreSQL | Provide relational integrity, transactions, JSONB and indexing |
| UUID identifiers | Keep internal identity independent of external ATS identifiers |
| Async FastAPI and SQLAlchemy | Support I/O-oriented workloads |
| Alembic migrations | Version database schema changes |
| APScheduler | Provide configurable periodic ingestion |
| Public read-only discovery API | Allow frictionless job discovery |
| Protected admin endpoints | Restrict manual ingestion operations |

### Core architectural principle

The most important design principle is the separation of external source representation from canonical application data.

An ATS provider can change its response format, field naming or optional metadata without requiring the entire application to adopt those provider-specific conventions.

The adapter handles extraction.

The normalization service handles standardization.

The deduplication service handles identity matching.

The synchronization service handles persistence and lifecycle management.

The database maintains the resulting canonical dataset.

This separation makes the platform easier to extend and maintain.

---

# 31. Contributing

Contributions and additional ATS integrations are welcome.

A typical integration workflow is:

1. Identify a supported public job-posting API.
2. Document the provider's response structure.
3. Implement a provider-specific adapter extending `ATSAdapter`.
4. Convert the provider response into `AdapterJob`.
5. Register the adapter in `adapters/registry.py`.
6. Add or update the company registry entry in `database/seed.py`.
7. Verify the integration.
8. Test normalization and synchronization behaviour.
9. Update the project documentation.

New integrations should preserve the separation between provider-specific extraction and provider-independent processing.

Before contributing:
- Keep credentials out of source control.
- Follow existing naming conventions.
- Preserve database constraints.
- Avoid unnecessary external API requests.
- Validate changes to normalization rules.
- Review migration changes carefully.

---

# 32. License

A license has not yet been specified in the supplied repository.

Add an appropriate `LICENSE` file before distributing the project under an open-source license.

---

## EmployBoard

**Every job. Every source. One board.**

A unified job discovery platform built around multi-source data ingestion, canonical data modelling, normalization, deduplication and reliable synchronization.

Built with Python, FastAPI, PostgreSQL, SQLAlchemy, React and TypeScript.
