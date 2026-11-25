# EmployBoard — API Integration & Data Collection Methodology

### External Data Sources · API Communication · Extraction · Parsing · Field Mapping · Data Provenance

---

## 1. Introduction

EmployBoard collects publicly available job postings from multiple companies by integrating with the public job-posting APIs exposed by their Applicant Tracking Systems (ATS).

Rather than scraping individual career websites using HTML selectors or browser automation, EmployBoard consumes structured JSON, XML or RSS responses directly from the underlying recruitment platforms.

The application currently integrates with eight ATS providers:

1. Ashby
2. Greenhouse
3. Lever
4. SmartRecruiters
5. Recruitee
6. Workable
7. Personio
8. Teamtailor

Each provider exposes its own API or structured careers-feed format, endpoint
conventions, field names, metadata formats and data availability.

EmployBoard implements a dedicated adapter for each provider. These adapters retrieve the external information, parse the provider-specific response and transform it into a common intermediate representation.

The resulting records are subsequently passed through the normalization, deduplication and synchronization services before being persisted in PostgreSQL.

### Primary objectives

- Retrieve publicly accessible job postings without accessing private recruitment information.
- Avoid unnecessary HTML scraping when structured APIs are available.
- Minimize provider-specific logic outside the adapter layer.
- Preserve the original external identifiers and source payloads.
- Extract consistent job information from heterogeneous API responses.
- Handle missing fields without inventing information.
- Retrieve additional job details when listing APIs provide incomplete information.
- Maintain source traceability and synchronization history.

---

# 2. Data Collection Architecture

The collection architecture separates external communication from internal data processing.

```text
                    COMPANY REGISTRY
                           |
                           |
                  ATS PROVIDER IDENTIFIED
                           |
                           v
                    ADAPTER REGISTRY
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
        Ashby            Lever          Greenhouse
          |                |                |
          +----------------+----------------+
                           |
                     SmartRecruiters
                           |
                           v
                  EXTERNAL HTTP REQUEST
                           |
                           v
                 JSON/XML/RSS RESPONSE
                           |
                           v
                  PROVIDER-SPECIFIC
                       PARSING
                           |
                           v
                     AdapterJob
                           |
                           v
                  NORMALIZATION SERVICE
                           |
                           v
                   NormalizedJob
                           |
                           v
                  DEDUPLICATION LOGIC
                           |
                           v
                  DATABASE SYNCHRONIZATION
                           |
                           v
                       POSTGRESQL
```

### Architectural separation

The collection process has four important responsibilities:

| Component | Responsibility |
|---|---|
| Company registry | Identifies which company and ATS board to retrieve |
| ATS adapter | Calls the external API and interprets its response |
| Normalization service | Standardizes the extracted information |
| Synchronization service | Inserts, updates and maintains database records |

This separation prevents the application from becoming tightly coupled to any individual ATS provider.

---

# 3. Company and ATS Source Registry

**Implementation:** `backend/app/database/seed.py`

EmployBoard maintains a configurable registry of companies.

Each entry contains the information required to identify the company's public job board.

Example:

```python
{
    "company_name": "OpenAI",
    "company_slug": "openai",
    "ats_provider": "ashby",
    "board_identifier": "openai",
    "careers_url": "https://openai.com/careers",
    "config": {
        "verified_at": "2026-11-24",
        "detail_limit": 0
    }
}
```

### Important registry fields

| Field | Description |
|---|---|
| `company_name` | Company's display name |
| `company_slug` | Internal company identifier |
| `ats_provider` | Identifies the ATS integration |
| `board_identifier` | Company's identifier within the ATS platform |
| `careers_url` | Official company careers website |
| `is_active` | Determines whether the company participates in ingestion |
| `config` | Provider-specific or company-specific configuration |

The `board_identifier` is particularly important.

It allows the application to construct the correct API endpoint without maintaining a separate hardcoded endpoint for every company.

### Current registered companies

| Company | ATS | Board identifier |
|---|---|---|
| Notion | Ashby | `notion` |
| OpenAI | Ashby | `openai` |
| Snowflake | Ashby | `snowflake` |
| Spotify | Lever | `spotify` |
| Paytm | Lever | `paytm` |
| Bosch | SmartRecruiters | `BoschGroup` |
| GitLab | Greenhouse | `gitlab` |

### Registry verification

The company registry contains verification notes dated November 24, 2026.

The recorded observations include:

| Company | Verification observation |
|---|---|
| Notion | Ashby returned 172 listed jobs |
| OpenAI | Ashby returned listed jobs with compensation |
| Snowflake | Ashby returned 374 listed jobs |
| Spotify | Lever returned live postings |
| Paytm | Lever returned 189 live postings |
| Bosch | SmartRecruiters returned 5,195 postings |
| GitLab | Greenhouse returned 252 jobs with content |

These are registry verification observations, not guaranteed current counts. The number of available jobs changes as companies publish and withdraw vacancies.

---

# 4. HTTP Communication Layer

**Implementation:** `backend/app/adapters/base.py`

All ATS integrations share a common asynchronous HTTP request utility.

The application uses:

- HTTPX
- `httpx.AsyncClient`
- Asynchronous GET requests
- JSON response parsing
- Configurable timeouts
- Retry handling
- Exponential backoff

### 4.1 HTTP client initialization

The ingestion service creates a shared HTTP client for the synchronization cycle.

```python
headers = {
    "User-Agent": settings.user_agent,
    "Accept": "application/json",
}

timeout = httpx.Timeout(
    settings.http_timeout_seconds,
    connect=10
)

async with httpx.AsyncClient(
    timeout=timeout,
    headers=headers,
    follow_redirects=True,
    limits=httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5
    )
) as client:
    ...
```

This client is shared across the company integrations in the current ingestion cycle.

### Why use a shared HTTP client?

Creating a new HTTP connection for every individual request introduces unnecessary connection overhead.

HTTPX supports connection pooling and connection reuse.

The shared client also centralizes:
- Request headers.
- Timeout configuration.
- Connection limits.
- Redirect handling.

### 4.2 Request headers

The application sends:

```http
User-Agent: EmployBoard/1.0 (...)
Accept: application/json
```

The User-Agent identifies the application making the request.

The Accept header indicates that the client expects a JSON response.

The current ATS adapters do not configure API authentication credentials or access tokens for these public posting endpoints.

### 4.3 Timeout configuration

Default configuration:

```env
HTTP_TIMEOUT_SECONDS=30
```

Connection timeout:

```python
connect=10
```

This prevents external API calls from waiting indefinitely.

### 4.4 Retry handling

The shared `request_json()` function implements bounded retry behaviour.

Default:

```env
HTTP_MAX_RETRIES=3
```

Retryable failures include:

- Network errors.
- Request timeouts.
- HTTP 429 — Too Many Requests.
- HTTP 5xx — Server-side errors.

The retry sequence uses exponential backoff with random jitter.

Conceptually:

```text
Initial request
      |
      v
Request fails temporarily
      |
      v
Retry after bounded delay
      |
      v
Second attempt
      |
      v
Retry if necessary
      |
      v
Maximum attempts reached
      |
      v
Raise TransientAdapterError
```

For HTTP 429, the implementation checks the `Retry-After` response header.

The value is capped at 60 seconds.

If that header is unavailable or invalid, exponential backoff is used.

For other retryable failures, the delay is calculated using:

```python
min(
    2 ** attempt + random.uniform(0, 0.5),
    20
)
```

For network errors, the implementation uses a similar bounded backoff.

### 4.5 Non-retryable failures

The following conditions are treated as non-retryable:

| HTTP status | Meaning | Behaviour |
|---|---|---|
| 400 | Bad request | Raise adapter error |
| 401 | Unauthorized | Raise adapter error |
| 403 | Forbidden | Raise adapter error |
| 404 | Not found | Raise adapter error |
| Other 4xx | Client error | Raise adapter error |

Invalid JSON responses also raise an adapter error.

This prevents malformed external responses from silently entering the ingestion pipeline.

---

# 5. Adapter Architecture

**Implementation:**

```text
backend/app/adapters/
│
├── base.py
├── registry.py
├── ashby.py
├── greenhouse.py
├── lever.py
└── smartrecruiters.py
```

Each adapter implements the common `ATSAdapter` interface.

The main contract is:

```python
async def fetch_jobs(
    self,
    company: Company
) -> list[AdapterJob]:
```

Adapters may additionally implement:

```python
async def fetch_detail(
    self,
    company: Company,
    external_job_id: str,
    existing_payload: dict | None = None
) -> AdapterJob | None:
```

The second method is optional and is used by SmartRecruiters.

### Adapter registry

The adapter registry maps provider identifiers to Python classes.

```python
_ADAPTERS = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "ashby": AshbyAdapter,
    "smartrecruiters": SmartRecruitersAdapter,
}
```

The ingestion service calls:

```python
adapter = build_adapter(
    company.ats_provider,
    client,
    settings
)
```

This returns the correct provider-specific implementation.

### Why use this design?

Without an adapter architecture, provider-specific API logic would need to be embedded inside the ingestion service.

As integrations increase, that approach becomes difficult to maintain.

With the adapter pattern:

- Each provider has its own request logic.
- Each provider has its own response parser.
- The ingestion service uses one common interface.
- Normalization and synchronization remain provider-independent.

Adding a company using an existing provider generally requires only a registry entry.

Adding an entirely new provider requires implementing and registering another adapter.

---

# 6. Ashby API Integration

**Implementation:** `backend/app/adapters/ashby.py`

**Official documentation:**

https://developers.ashbyhq.com/docs/public-job-posting-api

Ashby provides a public job-posting API that allows applications to retrieve published vacancies from a company's job board.

## 6.1 Endpoint

```http
GET https://api.ashbyhq.com/posting-api/job-board/{board_identifier}
```

Example for OpenAI:

```http
GET https://api.ashbyhq.com/posting-api/job-board/openai
```

The board identifier is retrieved dynamically from the company registry.

## 6.2 Query parameters

The implementation sends:

```python
params = {
    "includeCompensation": "true"
}
```

This requests compensation information where it is available through the public job-posting response.

## 6.3 Response structure

The adapter expects a JSON object containing a `jobs` array.

Conceptually:

```json
{
  "jobs": [
    {
      "id": "job-123",
      "title": "Software Engineer",
      "location": "San Francisco",
      "employmentType": "FullTime",
      "workplaceType": "Hybrid",
      "descriptionHtml": "<p>...</p>",
      "applyUrl": "https://...",
      "jobUrl": "https://...",
      "publishedAt": "...",
      "compensation": {}
    }
  ]
}
```

This is a representative structure, not a captured response.

The adapter validates that:
- The top-level response is a dictionary.
- The `jobs` property is a list.

Invalid top-level structures raise a parsing error.

## 6.4 Job extraction

The Ashby adapter extracts the following fields:

| API field | Internal field |
|---|---|
| `id` | `external_job_id` |
| `title` | `title` |
| `jobUrl` | `original_job_url` |
| `applyUrl` | `application_url` |
| `department` / `team` | `department` |
| `location` | `location` |
| `employmentType` | `employment_type_raw` |
| `workplaceType` | `workplace_type_raw` |
| `descriptionHtml` | `description_html` |
| `publishedAt` | `posted_at` |
| `compensation` | Salary fields |
| Entire job object | `source_payload` |

### Location fallback

If the main location field is unavailable, the adapter attempts to construct the location from:

```text
address.postalAddress.addressLocality
address.postalAddress.addressRegion
address.postalAddress.addressCountry
```

The available parts are joined into a single location string.

### Description fallback

The adapter first checks:

```python
descriptionHtml
```

If unavailable, it checks:

```python
descriptionPlain
```

Plain text is HTML-escaped and wrapped in a paragraph element.

### Listed-job filtering

Jobs explicitly containing:

```json
{
  "isListed": false
}
```

are excluded.

### Required-field validation

A job is skipped when any of the following is missing:
- External job ID.
- Job title.
- Valid application URL.

The adapter prefers `applyUrl` and falls back to `jobUrl`.

## 6.5 Compensation extraction

Ashby compensation is extracted from:

```text
compensation.summaryComponents
```

The implementation looks for a component where:

```text
compensationType = salary
```

It then extracts:

| API field | Internal field |
|---|---|
| `minValue` | `salary_min` |
| `maxValue` | `salary_max` |
| `currencyCode` | `salary_currency` |
| `interval` | `salary_interval` |

Supported interval mappings:

| Ashby interval | Internal value |
|---|---|
| `1 YEAR` | `year` |
| `1 MONTH` | `month` |
| `1 WEEK` | `week` |
| `1 DAY` | `day` |
| `1 HOUR` | `hour` |

If no salary component is available, salary fields remain null.

The adapter does not infer compensation from job descriptions.

## 6.6 Current Ashby integrations

| Company | Board identifier |
|---|---|
| Notion | `notion` |
| OpenAI | `openai` |
| Snowflake | `snowflake` |

The current implementation retrieves the public job board through one request per company. It does not implement additional Ashby pagination.

---

# 7. Greenhouse API Integration

**Implementation:** `backend/app/adapters/greenhouse.py`

**Official documentation:**

https://developers.greenhouse.io/job-board.html

Greenhouse exposes a public Job Board API.

## 7.1 Endpoint

```http
GET https://boards-api.greenhouse.io/v1/boards/{board_identifier}/jobs
```

Example for GitLab:

```http
GET https://boards-api.greenhouse.io/v1/boards/gitlab/jobs
```

## 7.2 Query parameters

The implementation sends:

```python
params = {
    "content": "true"
}
```

This requests job content in the response.

## 7.3 Response structure

The adapter expects:

```json
{
  "jobs": [
    {
      "id": 123,
      "title": "Data Engineer",
      "absolute_url": "https://...",
      "location": {
        "name": "Remote"
      },
      "departments": [],
      "offices": [],
      "metadata": [],
      "content": "<p>...</p>",
      "first_published": "..."
    }
  ]
}
```

The example is illustrative.

The adapter validates that the response contains a `jobs` list.

## 7.4 Job extraction

| API field | Internal field |
|---|---|
| `id` | `external_job_id` |
| `title` | `title` |
| `absolute_url` | `application_url` |
| `absolute_url` | `original_job_url` |
| `location.name` | `location` |
| `offices[].name` | Location fallback |
| `departments[].name` | `department` |
| `metadata` | Employment/workplace/experience fields |
| `content` | `description_html` |
| `first_published` | `posted_at` |
| `updated_at` | Publication-date fallback |
| `application_deadline` | `expires_at` |
| `requisition_id` | `requisition_id` |
| Entire job object | `source_payload` |

### Location extraction

The adapter first attempts:

```text
location.name
```

If unavailable, it examines the available office names.

The first non-empty office name becomes the selected location.

### Department extraction

The adapter examines:

```text
departments[].name
```

The first non-empty department is selected.

### Metadata extraction

Greenhouse metadata is particularly useful because employment and workplace information can be configured differently by individual organizations.

The adapter supports multiple aliases.

Employment metadata aliases:

```text
employment type
employment_type
worker type
job type
```

Workplace metadata aliases:

```text
workplace type
workplace_type
remote type
work environment
```

Experience metadata aliases:

```text
experience level
experience_level
seniority
```

The matching is performed using lowercase metadata names.

Values such as empty strings and `n/a` are ignored.

### HTML handling

Greenhouse content is passed through HTML entity decoding before being stored.

### Required-field validation

The adapter skips records without:
- External job ID.
- Title.
- Valid absolute URL.

## 7.5 Current Greenhouse integration

| Company | Board identifier |
|---|---|
| GitLab | `gitlab` |

The current implementation makes one listing request per company and does not implement additional pagination for this endpoint.

---

# 8. Lever API Integration

**Implementation:** `backend/app/adapters/lever.py`

**Official documentation:**

https://github.com/lever/postings-api

Lever provides a public Postings API for retrieving vacancies from an organization's posting board.

## 8.1 Endpoint

```http
GET https://api.lever.co/v0/postings/{board_identifier}
```

Example for Spotify:

```http
GET https://api.lever.co/v0/postings/spotify
```

## 8.2 Query parameters

The implementation sends:

```python
params = {
    "mode": "json"
}
```

This requests JSON-formatted posting data.

## 8.3 Response structure

Lever returns a list of posting objects.

Conceptually:

```json
[
  {
    "id": "posting-123",
    "text": "Software Engineer",
    "hostedUrl": "https://...",
    "applyUrl": "https://...",
    "categories": {
      "location": "Stockholm",
      "department": "Engineering",
      "commitment": "Full-time"
    },
    "description": "...",
    "lists": [],
    "createdAt": 1760000000000
  }
]
```

The actual response depends on the posting and provider configuration.

Unlike Ashby and Greenhouse, the adapter expects the top-level response to be a list rather than an object containing a `jobs` property.

## 8.4 Job extraction

| API field | Internal field |
|---|---|
| `id` | `external_job_id` |
| `text` | `title` |
| `hostedUrl` | `original_job_url` |
| `applyUrl` | `application_url` |
| `categories.location` | `location` |
| `categories.allLocations` | Location fallback |
| `categories.department` | `department` |
| `categories.team` | Department fallback |
| `categories.commitment` | `employment_type_raw` |
| `workplaceType` | `workplace_type_raw` |
| `createdAt` | `posted_at` |
| Description fields | `description_html` |
| Entire posting object | `source_payload` |

The application URL prefers `applyUrl` and falls back to `hostedUrl`.

## 8.5 Description construction

Lever provides descriptions in multiple sections.

The adapter combines available sections into a single description.

It initially checks:

```text
description
descriptionBody
```

It then iterates through:

```text
lists[]
```

Each section can contain:
- A heading.
- HTML content.

The adapter preserves these sections by adding their headings to the combined description.

It also identifies likely requirements and responsibilities through heading-based matching.

### Responsibility heading hints

Examples include:

```text
What you'll do
What you will do
Responsibilities
The role
Your role
Day to day
Key responsibilities
```

### Requirement heading hints

Examples include:

```text
Who you are
Requirements
Qualifications
What you bring
About you
You have
Skills
Experience
What we're looking for
```

Sections matching these hints are additionally stored in:

```text
requirements_html
responsibilities_html
```

Other description sections remain part of the combined job description.

### Additional description content

If an `additional` field exists, it is appended to the combined description.

If structured description content is unavailable, the adapter checks:

```text
descriptionPlain
openingPlain
```

Plain text is HTML-escaped and wrapped in a paragraph.

## 8.6 Current Lever integrations

| Company | Board identifier |
|---|---|
| Spotify | `spotify` |
| Paytm | `paytm` |

The current implementation retrieves the posting list through one request per company and does not implement additional pagination.

---

# 9. SmartRecruiters API Integration

**Implementation:** `backend/app/adapters/smartrecruiters.py`

**Official documentation:**

https://dev.smartrecruiters.com/

SmartRecruiters has two separate collection operations in EmployBoard:

1. Listing retrieval.
2. Posting detail enrichment.

This is important because the listing response does not always provide full job descriptions.

## 9.1 Listing endpoint

```http
GET https://api.smartrecruiters.com/v1/companies/{company}/postings
```

Example for Bosch:

```http
GET https://api.smartrecruiters.com/v1/companies/BoschGroup/postings
```

## 9.2 Pagination

SmartRecruiters listing retrieval implements offset-based pagination.

The initial configuration is:

```python
offset = 0
page_size = 100
```

Each request sends:

```python
params = {
    "limit": 100,
    "offset": offset
}
```

The response is expected to contain:

```json
{
  "content": [],
  "totalFound": 0
}
```

The `content` array contains posting records.

The `totalFound` field indicates the total number of matching records.

### Pagination workflow

```text
Initial offset = 0
Page size = 100
       |
       v
Request page
       |
       v
Parse content array
       |
       v
Append valid postings
       |
       v
Check totalFound
       |
       +---- offset >= totalFound? ---- Yes ---> Stop
       |
       No
       |
       v
Check if page is empty
       |
       +---- Empty? ---- Yes -----------> Stop
       |
       No
       |
       v
Check if fewer than 100 records
       |
       +---- Yes -----------------------> Stop
       |
       No
       |
       v
offset += number of returned records
       |
       v
Request next page
```

There is also a safety boundary:

```python
if offset > 100_000:
    break
```

### Optional sync limit

The adapter supports an optional company configuration:

```python
sync_limit
```

When configured, collection stops after the specified number of valid parsed jobs.

This is distinct from the detail enrichment limit.

## 9.3 Listing response extraction

The adapter extracts:

| API field | Internal field |
|---|---|
| `id` | `external_job_id` |
| `name` | `title` |
| `refNumber` | `requisition_id` |
| `department` | `department` |
| `function` | Department fallback |
| `typeOfEmployment` | `employment_type_raw` |
| `experienceLevel` | `experience_level_raw` |
| `releasedDate` | `posted_at` |
| `location` | `location` |
| Entire posting object | `source_payload` |

### Location extraction

The adapter first checks:

```text
location.fullLocation
```

If available, the location is normalized around comma-separated components.

Otherwise, it combines:

```text
location.city
location.region
location.country
```

### Workplace type extraction

SmartRecruiters provides boolean location indicators.

The implementation maps them as follows:

| Remote | Hybrid | Internal value |
|---|---|---|
| true | Any | Remote |
| false | true | Hybrid |
| false | false | On-site |
| Missing/ambiguous | Missing/ambiguous | Unknown |

### Application URL construction

The listing response is used to construct the public posting URL:

```text
https://jobs.smartrecruiters.com/{company}/{posting_id}
```

This becomes both the original posting URL and the initial application URL.

The detail endpoint can provide a more specific application URL.

---

# 10. SmartRecruiters Detail Enrichment

SmartRecruiters requires special treatment because its listing response does not necessarily include the full job advertisement.

EmployBoard therefore implements a second endpoint.

## 10.1 Detail endpoint

```http
GET https://api.smartrecruiters.com/v1/companies/{company}/postings/{posting_id}
```

Example:

```http
GET https://api.smartrecruiters.com/v1/companies/BoschGroup/postings/123456
```

The posting ID is obtained from the listing response.

## 10.2 Which jobs are enriched?

The synchronization service selects jobs that:

- Belong to the company being synchronized.
- Are currently active.
- Do not yet have a description.
- Have a source record for the current ATS provider.

The records are ordered by:

```text
posted_at DESC NULLS LAST
```

This prioritizes newer postings.

## 10.3 Enrichment limits

The company registry supports:

```python
"detail_limit": 100
```

Bosch currently uses this configuration.

A zero value disables enrichment.

When a company-specific detail limit is not provided, the application falls back to:

```env
SMARTRECRUITERS_DETAIL_LIMIT=100
```

This prevents the application from making an unbounded number of detail requests during a synchronization cycle.

## 10.4 Detail extraction

The detail parser reads:

```text
postingUrl
applyUrl
refNumber
department
function
typeOfEmployment
experienceLevel
location
jobAd.sections
```

The application URL prefers `applyUrl` and falls back to `postingUrl`.

If neither is available, it constructs the public SmartRecruiters posting URL.

### Job description sections

The adapter inspects:

```text
jobAd.sections
```

It supports:

| Section key | Purpose |
|---|---|
| `companyDescription` | Company information |
| `jobDescription` | Job description and responsibilities |
| `qualifications` | Requirements |
| `additionalInformation` | Additional information |

The section's `text` is extracted.

The section title is preserved as an HTML heading when available.

The `qualifications` section is also used to populate requirements.

The `jobDescription` section is also used to populate responsibilities.

### Detail payload preservation

After retrieving detail information, the source payload is stored in a combined structure:

```json
{
  "listing": {},
  "detail": {}
}
```

This preserves the distinction between the original listing response and the subsequently retrieved detail response.

The source's verification timestamp is also updated.

---

# 11. Common Intermediate Representation: AdapterJob

**Implementation:** `backend/app/adapters/base.py`

Each adapter converts its provider-specific JSON response into the same Python dataclass.

```python
@dataclass(slots=True)
class AdapterJob:
    external_job_id: str
    title: str
    application_url: str

    original_job_url: str | None = None
    department: str | None = None
    location: str | None = None

    employment_type_raw: str | None = None
    workplace_type_raw: str | None = None
    experience_level_raw: str | None = None

    description_html: str | None = None
    requirements_html: str | None = None
    responsibilities_html: str | None = None

    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None

    posted_at: datetime | None = None
    expires_at: datetime | None = None

    requisition_id: str | None = None
    skills: list[str] | None = None

    source_payload: dict = field(default_factory=dict)
    detail_fetched: bool = False
```

This object is the boundary between external data extraction and internal data processing.

### Why AdapterJob exists

Without this intermediate representation, the normalization service would need to understand eight different provider response formats.

Instead:

```text
Ashby JSON -----------+
Lever JSON -----------+
Greenhouse JSON ------+----> AdapterJob
SmartRecruiters JSON -+
```

The normalization service receives the same structure regardless of the original source.

### Required fields

The adapters generally require:

- External job ID.
- Job title.
- Valid application URL.

Records without required information are skipped.

### Optional fields

Other fields remain nullable.

This is intentional because not all providers supply every attribute.

EmployBoard does not fabricate salary, experience, skills or description information when a source does not provide it.

---

# 12. Field Mapping and Data Availability

Different providers expose different levels of detail.

The following table summarizes the current extraction implementation.

| Field | Ashby | Greenhouse | Lever | SmartRecruiters |
|---|---|---|---|---|
| External ID | Yes | Yes | Yes | Yes |
| Job title | Yes | Yes | Yes | Yes |
| Application URL | Yes | Yes | Yes | Yes |
| Original posting URL | Yes | Same URL | Yes | Constructed |
| Department | Yes | Yes | Yes | Yes |
| Location | Yes | Yes | Yes | Yes |
| Employment type | Yes | Metadata | Yes | Yes |
| Workplace type | Yes | Metadata | Yes | Boolean flags |
| Experience level | Not mapped | Metadata | Not mapped | Yes |
| Description | Yes | Yes | Yes | Detail endpoint |
| Requirements | Not separately extracted | Not separately extracted | Heading-based | Qualifications section |
| Responsibilities | Not separately extracted | Not separately extracted | Heading-based | Job description section |
| Salary | Yes | Not mapped | Not mapped | Not mapped |
| Publication date | Yes | Yes | Yes | Yes |
| Expiration date | Not mapped | Yes | Not mapped | Not mapped |
| Requisition ID | Not mapped | Yes | Not mapped | Yes |
| Skills | Not separately extracted | Not separately extracted | Not separately extracted | Not separately extracted |

**Important:** A field being supported by an adapter does not mean every posting contains it.

For example, SmartRecruiters may return an experience level for one posting but not another.

Likewise, Ashby compensation is only available when the public response supplies the relevant salary component.

The application preserves missing values as `NULL`.

---

# 13. Data Provenance and Source Payload Preservation

One of the most important collection decisions in EmployBoard is preserving the original provider response.

Every `AdapterJob` contains:

```python
source_payload: dict[str, Any]
```

This stores the original provider-specific job object.

The data is subsequently persisted in the `job_sources.source_payload` JSONB column.

### Why preserve original payloads?

Consider an ATS provider introducing a new field:

```json
{
  "workAuthorization": "Required"
}
```

The current canonical schema might not have a corresponding column.

If only normalized data is retained, the original value could be lost.

Preserving the source payload provides:

- Data provenance.
- Debugging information.
- Provider-response traceability.
- Future field-enrichment opportunities.
- A record of the data used to construct canonical job information.

### Source identity

Every external posting is associated with:

```text
ats_provider
external_job_id
```

The combination is unique.

This ensures that the same external posting is not repeatedly registered as a new source record.

### Canonical identity

The canonical job uses an internal UUID.

This separates EmployBoard's internal identity from the external provider's identifier.

---

# 14. Data Processing After Collection

After the adapter returns `AdapterJob` objects, the collection pipeline hands them to the normalization and synchronization services.

```text
External API
     |
     v
Provider JSON
     |
     v
Adapter parsing
     |
     v
AdapterJob
     |
     v
normalize_adapter_job()
     |
     v
NormalizedJob
     |
     v
JobSyncService
     |
     +---- Existing external ID?
     |          |
     |          +---- Yes: Update existing job
     |
     +---- Requisition match?
     |          |
     |          +---- Yes: Reuse canonical job
     |
     +---- Cross-source candidate?
     |          |
     |          +---- Yes: Flag possible duplicate
     |
     +---- No match
                |
                v
          Insert new job
                |
                v
          Insert job source
```

### Normalization

The normalization service standardizes:
- Employment type.
- Workplace type.
- Experience level.
- Job title.
- Location.
- Salary.
- Currency.
- Dates.
- URLs.
- Skills.

### Deduplication

The synchronization service checks:
1. Provider and external job ID.
2. Company and requisition ID.
3. Company, normalized title, normalized location and a different provider.

Potential cross-source duplicates are flagged rather than automatically merged.

### Persistence

The resulting information is written into:

```text
companies
jobs
job_sources
ingestion_runs
```

The original source payload remains available through the source relationship.

---

# 15. Synchronization Scheduling and Collection Frequency

The ingestion service is implemented in:

```text
backend/app/services/ingestion_service.py
```

The application uses APScheduler.

Default configuration:

```env
ENABLE_SCHEDULER=true
SYNC_INTERVAL_HOURS=6
```

This means the application attempts to synchronize its registered companies every six hours.

The interval is configurable.

## Company-level synchronization

Each company is processed separately.

For each company:
1. An ingestion run is created.
2. Its ATS adapter is selected.
3. The external API is queried.
4. The records are parsed.
5. The records are normalized and synchronized.
6. Optional detail enrichment is performed.
7. Missing records are evaluated.
8. Ingestion statistics are committed.

If one company fails, other companies can still be processed.

## Advisory locking

Before beginning a synchronization cycle, EmployBoard attempts to acquire a PostgreSQL advisory lock.

```sql
SELECT pg_try_advisory_lock(
    hashtext('employboard_ingestion')
);
```

This prevents simultaneous ingestion cycles from processing the same dataset.

The lock is released after the cycle finishes.

## Polite request behaviour

The ingestion service waits:

```python
await asyncio.sleep(0.5)
```

between independent company integrations.

This reduces unnecessary request bursts against public ATS endpoints.

---

# 16. Error Handling During Data Collection

Failures are handled at multiple levels.

### HTTP-level failures

Handled in `request_json()`.

Examples:
- Timeout.
- Network failure.
- HTTP 429.
- HTTP 5xx.
- Invalid JSON.

Retryable failures use bounded retries.

### Response parsing failures

Each adapter validates the expected top-level JSON structure.

Examples:

```text
Ashby       -> dictionary containing jobs[]
Greenhouse  -> dictionary containing jobs[]
Lever       -> list of postings
SmartRecruiters -> dictionary containing content[]
```

Unexpected structures raise parsing errors.

### Record-level failures

A job without a required external ID, title or application URL is skipped.

Normalization errors are recorded.

Individual upsert failures are isolated using nested transactions.

### Company-level failures

A failed company synchronization is recorded as `failed`.

Other companies continue processing.

### Partial synchronization

A company can be marked `partial` if individual records or detail requests fail while the broader ingestion process continues.

The ingestion history preserves error details for investigation.

---

# 17. Operational Statistics and Verification

The company registry stores verification notes.

The CLI provides:

```bash
python -m app.cli verify
```

This fetches and verifies configured public job boards without persisting the retrieved jobs.

Verify an individual company:

```bash
python -m app.cli verify --company openai
```

Verify a provider:

```bash
python -m app.cli verify --provider ashby
```

Run actual collection:

```bash
python -m app.cli sync
```

Inspect aggregate database statistics:

```bash
python -m app.cli stats
```

Inspect ingestion history:

```bash
python -m app.cli runs --limit 10
```

The `ingestion_runs` table records:
- Provider.
- Company.
- Start timestamp.
- Finish timestamp.
- Status.
- Jobs fetched.
- Jobs inserted.
- Jobs updated.
- Jobs deactivated.
- Jobs skipped.
- Errors.

These statistics provide the foundation for measuring source reliability and ingestion quality.

---

# 18. Data Collection Limitations

The collection methodology has several important limitations.

## 18.1 Public data availability

EmployBoard only retrieves information exposed by the public job-posting APIs.

It cannot retrieve private candidate information, recruiter notes or internal hiring decisions.

## 18.2 Provider-specific completeness

Different ATS providers expose different information.

Not every job contains:
- Compensation.
- Experience level.
- Workplace type.
- Requirements.
- Responsibilities.
- Skills.
- Expiration date.

Missing information is represented as `NULL`.

## 18.3 API pagination differences

The current implementations differ:

| Provider | Current collection approach |
|---|---|
| Ashby | Single job-board request |
| Greenhouse | Single job-board request |
| Lever | Single postings request |
| SmartRecruiters | Offset-based pagination |

Pagination behaviour is not assumed to be identical across providers.

## 18.4 Detail enrichment limitations

Only SmartRecruiters currently implements the optional detail-fetching interface.

Its detail enrichment is bounded by configuration.

Other providers rely on the information returned by their listing endpoints.

## 18.5 Duplicate detection limitations

External IDs provide reliable source identity.

Requisition identifiers provide an additional matching mechanism.

Cross-source title and location matching identifies potential duplicates but does not guarantee that two postings represent the same vacancy.

## 18.6 External API dependency

EmployBoard depends on external provider availability.

A provider can:
- Change its response structure.
- Restrict access.
- Return incomplete data.
- Introduce rate limits.
- Temporarily become unavailable.

The retry and validation layers reduce the impact of these failures but cannot eliminate external dependencies.

## 18.7 Collection is not real-time

The default synchronization interval is six hours.

Consequently, a job may appear in EmployBoard after it has already been published externally.

The application should not represent every posting as being verified in real time.

---

# 19. Adding Another Company

Adding a company that uses an existing ATS provider does not require a new adapter.

For example, to add another Ashby company:

1. Identify its public Ashby job board.
2. Obtain the correct board identifier.
3. Verify the public endpoint.
4. Add a company entry to `COMPANY_REGISTRY`.
5. Seed the registry.
6. Run the verification command.
7. Run synchronization.

Example registry entry:

```python
{
    "company_name": "Example Company",
    "company_slug": "example-company",
    "company_logo_url": "...",
    "company_website": "https://example.com",
    "careers_url": "https://example.com/careers",
    "ats_provider": "ashby",
    "board_identifier": "example-company",
    "config": {
        "detail_limit": 0
    }
}
```

Then:

```bash
python -m app.cli seed
python -m app.cli verify --company example-company
python -m app.cli sync --company example-company
```

No frontend modification is necessary for the backend to ingest the new company's postings, provided the API and frontend support displaying the registered company.

---

# 20. Adding a New ATS Provider

A completely new ATS provider requires a new adapter.

The implementation process is:

1. Find the provider's official public job-posting API documentation.
2. Identify the listing endpoint.
3. Understand its authentication requirements, if any.
4. Identify pagination mechanisms.
5. Inspect the response schema.
6. Determine which fields are available.
7. Implement a new adapter extending `ATSAdapter`.
8. Convert its responses into `AdapterJob`.
9. Register the provider in `adapters/registry.py`.
10. Add the provider to the supported ATS enum and validation rules.
11. Add the appropriate company registry entries.
12. Test the integration against real or representative API responses.
13. Verify normalization and database synchronization.

### Adapter contract

A new adapter must implement:

```python
async def fetch_jobs(
    self,
    company: Company
) -> list[AdapterJob]:
    ...
```

If the provider supports separate posting details:

```python
async def fetch_detail(
    self,
    company: Company,
    external_job_id: str,
    existing_payload: dict | None = None
) -> AdapterJob | None:
    ...
```

The new adapter should not independently implement database insertion, canonical matching or synchronization.

Those responsibilities already belong to the shared processing pipeline.

---

# 21. Official API Documentation

The following are the external documentation references used by the integrations.

| Provider | Documentation |
|---|---|
| Ashby | https://developers.ashbyhq.com/docs/public-job-posting-api |
| Greenhouse | https://developers.greenhouse.io/job-board.html |
| Lever | https://github.com/lever/postings-api |
| SmartRecruiters | https://dev.smartrecruiters.com/ |
| Recruitee | https://docs.recruitee.com/reference/offers |
| Workable | https://help.workable.com/hc/en-us/articles/115012771647-Using-the-Workable-API |
| Personio | https://developer.personio.de/v1.0/reference/get_xml |
| Teamtailor | https://support.teamtailor.com/en/articles/11171756-rss-feed-how-to-guide |

These references should be consulted when:
- Adding new integrations.
- Investigating provider response changes.
- Understanding newly supported fields.
- Reviewing pagination behaviour.
- Investigating API access restrictions.

---

# 22. Conclusion

EmployBoard's data collection architecture is designed around a provider-independent ingestion pipeline.

The eight ATS integrations are responsible for understanding their respective
external APIs or structured feeds and converting the retrieved information into
a common intermediate representation.

The shared normalization service then standardizes the extracted information.

The deduplication and synchronization services maintain canonical job records, preserve source relationships and track changes over time.

PostgreSQL stores both the normalized business information and the original external source payloads.

The overall architecture can be summarized as:

**Discover → Retrieve → Parse → Validate → Normalize → Match → Synchronize → Persist**

The most important architectural distinction is that external API formats do not dictate the internal database schema.

Each ATS provider is treated as an independent data source, while EmployBoard maintains a unified representation of the job information collected from those sources.

This makes the system extensible: new companies can be registered against existing integrations, and entirely new ATS platforms can be supported by implementing additional adapters without rewriting the central ingestion pipeline.

---

**EmployBoard — API Integration & Data Collection Methodology**

*Technical reference for external source communication, provider-specific extraction, data mapping, provenance and ingestion operations.*
