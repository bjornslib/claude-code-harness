---
title: "Employer Contact Research Agent — Technical Specification"
description: "Technical specification for DSPy-based employer contact research, deduplication, classification, and prioritisation pipeline"
version: "2.0.0"
last-updated: 2026-04-04
status: draft
type: sd
grade: authoritative
prd_id: PRD-EMPLOYER-CONTACT-001
---

# SD-EMPLOYER-CONTACT-E1: Employer Contact Research Agent — Technical Specification

## 0. SD Deviation Notice

The PRD §13 and the prior research (evidence/domain_patterns_employer_contact_v2.md) recommended **PydanticAI + raw Perplexity API + pure Python classification** based on the observation that DSPy is not currently used in the production codebase. This TS **deliberately overrides** that recommendation per explicit human review directive:

| Component | Prior Research Recommendation | This TS (Human-Directed) | Rationale |
|-----------|-------------------------------|--------------------------|-----------|
| Deduplication | Regex/deterministic matching | **DSPy ChainOfThought** | Fuzzy LM-powered dedup across sources |
| Classification + Prioritisation | Pure Python functions | **DSPy Predict** (single step) | LM sees all contacts holistically, applies 7-tier logic |
| Confidence scoring | Separate post-processing module | **Embedded in Perplexity search step** | Source quality signals available at search time |
| Contact data model | New `employer_research/domain.py` | **Extend existing `models/contacts.py`** | Avoids parallel model; reuses discriminator pattern |
| `employer_search/research.py` | Enhance and keep | **Delete** — superseded by `employer_research/researcher.py` | Clean break; new module is DSPy-aware |

**New dependency**: `dspy` (3.1+) will be added to the project. This is the first DSPy integration; the `eddy_validate/dspy_migration_design.md` document (existing in codebase) already outlined a DSPy migration path for education validation, making this a planned technology adoption.

---

## 1. Executive Summary

This TS defines the implementation blueprint for an AI-powered employer contact research pipeline that:

1. Takes **customer-provided contacts** as the starting input (often incomplete)
2. **Researches** the employer via Perplexity API to discover additional contacts (with embedded confidence scoring)
3. **Deduplicates** across all sources using DSPy ChainOfThought (fuzzy LM-powered)
4. **Classifies + prioritises** the deduplicated contacts in a single DSPy Predict step
5. **Stores** enriched contacts in the existing `university_contacts` table (entity_type='employer')

The pipeline produces an exhaustive, prioritised contact list ready for the outreach sequence defined in PRD §6.

---

## 2. Module Design

### 2.1 Directory Structure

```
agencheck-support-agent/
├── employer_research/                 # NEW feature directory (Clean Architecture)
│   ├── __init__.py                    # Public API exports
│   ├── service.py                     # Service layer — orchestrates the pipeline
│   ├── researcher.py                  # Adapter — Perplexity API with embedded confidence
│   ├── deduplicator.py                # DSPy ChainOfThought — fuzzy contact deduplication
│   ├── classifier.py                  # DSPy Predict — classification + prioritisation (one step)
│   ├── repository.py                  # Adapter — Supabase/asyncpg CRUD for employer contacts
│   ├── router.py                      # Entrypoint — FastAPI route / Prefect task wrapper
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                # Fixtures: mock Perplexity responses, sample contacts
│       ├── test_service.py            # Integration tests for full pipeline
│       ├── test_researcher.py         # Tests for Perplexity researcher
│       ├── test_deduplicator.py       # Tests for DSPy deduplication
│       ├── test_classifier.py         # Tests for DSPy classification + prioritisation
│       └── test_repository.py         # Tests for database CRUD
├── employer_search/                   # EXISTING — to be DELETED (superseded)
│   └── research.py                    # DELETE — replaced by employer_research/researcher.py
├── models/
│   └── contacts.py                    # EXTEND — add contact_type, has_contact_form, contact_form_url, source_url
└── utils/
    └── background_task_helpers.py     # EXTEND — add 4 new CallResultStatus enum values
```

### 2.2 Layer Responsibilities (Clean Architecture)

| Layer | Files | Responsibility | Dependencies |
|-------|-------|---------------|-------------|
| **Domain** | `models/contacts.py` (extended) | Pydantic models, enums, field validation. Pure Python, no I/O. | None |
| **Service** | `service.py` | Orchestrates: customer contacts → research → dedup → classify+prioritise → store | Calls adapters + domain |
| **Adapters** | `researcher.py`, `repository.py`, `deduplicator.py`, `classifier.py` | External integrations: Perplexity API, asyncpg DB, DSPy LM | Implements interfaces for service |
| **Entrypoints** | `router.py` | FastAPI routes / Prefect task wrappers. Thin — delegates to service immediately | Calls service only |

**Dependency flow**: entrypoints → service → domain ← adapters

### 2.3 Files to Delete

| File | Reason |
|------|--------|
| `employer_search/research.py` | Superseded by `employer_research/researcher.py` |
| `employer_search/__init__.py` | Module no longer needed |
| `employer_search/test_employer_research.py` | Superseded by `employer_research/tests/` |
| `employer_search/validate_ground_truth.py` | Ground truth data retained for reference; validator superseded |

**Retain for reference** (read-only): `employer_search/ground_truth_employers.json`, `employer_search/ground_truth_validation_results.json`, `employer_search/direct_api_test_results.json`, `employer_search/test_results.json`.

### 2.4 Files to Extend

| File | Changes |
|------|---------|
| `models/contacts.py` | Add fields to `EmployerContact`: `contact_type`, `has_contact_form`, `contact_form_url`, `source_url` |
| `utils/background_task_helpers.py` | Add 4 new `CallResultStatus` enum values |
| `prefect_flows/flows/tasks/channel_dispatch.py` | Add `research` channel type dispatch |
| `prefect_flows/flows/tasks/sla_config.py` | Add default employer outreach sequence |

---

## 3. API Contracts

### 3.1 service.py — EmployerResearchService

The service layer is the pipeline orchestrator. It receives customer-provided contacts, runs research, deduplication, classification+prioritisation, and stores results.

```python
from typing import List, Optional
from models.contacts import EmployerContact, AdditionalContact

class CustomerProvidedContact:
    """Input: what the background check company's client provides."""
    employer_name: str                           # Required
    country: str                                 # Required
    city: Optional[str] = None
    website_url: Optional[str] = None
    phone_number: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None

class ResearchPipelineResult:
    """Output: the full result of the research pipeline."""
    employer_name: str
    country: str
    success: bool
    primary_contact: Optional[EmployerContact]       # Highest-priority contact stored as primary
    additional_contacts: List[AdditionalContact]      # Remaining contacts stored in JSONB
    total_contacts_discovered: int
    total_after_dedup: int
    sources_used: List[str]
    research_duration_seconds: float
    error_message: Optional[str] = None

class EmployerResearchService:
    """
    Service layer: orchestrates the employer contact research pipeline.

    Pipeline:
    1. Accept customer-provided contacts as input
    2. Research employer via Perplexity API (enrich + discover new contacts)
    3. Deduplicate across all sources (DSPy ChainOfThought)
    4. Classify + prioritise in one step (DSPy Predict)
    5. Store to database via repository
    """

    async def research_employer_contacts(
        self,
        customer_contact: CustomerProvidedContact,
        customer_id: int,
        case_id: Optional[int] = None,
    ) -> ResearchPipelineResult:
        """
        Run the full research pipeline.

        Args:
            customer_contact: Customer-provided employer information (often incomplete)
            customer_id: FK to customers table
            case_id: Optional FK to cases table (for linking results)

        Returns:
            ResearchPipelineResult with all discovered, deduped, classified contacts

        Pipeline steps:
            1. researcher.research(customer_contact) → raw contacts + confidence
            2. Merge customer-provided contacts with discovered contacts
            3. deduplicator.deduplicate(merged_contacts) → unique contacts
            4. classifier.classify_and_prioritise(unique_contacts, employer_context)
               → classified + prioritised contacts
            5. repository.store_contacts(classified_contacts, customer_id)
        """
        ...

    async def get_prioritised_contacts(
        self,
        employer_name: str,
        customer_id: int,
    ) -> List[AdditionalContact]:
        """Retrieve stored contacts for an employer, ordered by priority tier."""
        ...

    async def validate_poc(
        self,
        contact_id: int,
        verified_by: str,
    ) -> EmployerContact:
        """
        Promote a contact to validated_poc status.

        Called when a voice agent confirms the person has HR/Payroll system access.
        Updates contact_type from 'named_poc' → 'validated_poc' in DB.
        """
        ...

    async def add_alternate_contact(
        self,
        employer_name: str,
        customer_id: int,
        new_contact: AdditionalContact,
        source: str = "call_discovered",
    ) -> AdditionalContact:
        """
        Store a new contact discovered during a call (alternate_contact_received).

        Runs deduplication against existing contacts before storing.
        """
        ...
```

### 3.2 researcher.py — EmployerContactResearcher

The Perplexity API adapter. **Confidence scoring is embedded in the research step** — not a separate post-processing module.

```python
from typing import List, Optional
from pydantic import BaseModel, Field

class RawDiscoveredContact(BaseModel):
    """A single contact extracted from Perplexity research response."""
    name: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    source_url: Optional[str] = None
    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Confidence score derived from search source quality, "
                    "citation count, and contact completeness — computed "
                    "during the research step, not post-hoc."
    )
    has_contact_form: bool = False
    contact_form_url: Optional[str] = None
    notes: Optional[str] = None

class PerplexityResearchResult(BaseModel):
    """Full result from Perplexity research including embedded confidence."""
    employer_name: str
    country: str
    success: bool
    contacts: List[RawDiscoveredContact] = Field(default_factory=list)
    sources_used: List[str] = Field(default_factory=list)
    raw_response: Optional[str] = None
    error_message: Optional[str] = None

class EmployerContactResearcher:
    """
    Adapter: Perplexity API researcher with embedded confidence scoring.

    Confidence is computed DURING the research step because:
    - Source quality signals (citation count, URL domain) are available in the API response
    - Contact completeness can be assessed at extraction time
    - Per-contact source attribution is captured alongside the data

    Replaces employer_search/research.py (Spike 2.5).
    """

    PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
    MODEL_NAME = "sonar-reasoning-pro"

    # Source reliability tiers (used in confidence calculation)
    SOURCE_CONFIDENCE = {
        "customer_provided": 1.0,
        "employer_website": 0.85,
        "perplexity_citation": 0.80,
        "linkedin": 0.75,
        "business_directory": 0.60,
        "web_search": 0.55,
    }

    async def research(
        self,
        customer_contact: "CustomerProvidedContact",
    ) -> PerplexityResearchResult:
        """
        Research employer contacts via Perplexity API.

        Takes customer-provided contact info as input context for the search.
        Always runs research even if customer provided a phone number —
        the goal is an exhaustive contact list for compliance.

        Confidence scoring is embedded:
        - base_confidence from source type (SOURCE_CONFIDENCE dict)
        - +0.15 if contact has name
        - +0.10 if contact has title
        - +0.20 if contact has email
        - +0.20 if contact has phone
        - +0.10 if contact has department
        - Capped at 1.0

        Args:
            customer_contact: Customer-provided employer info (used to seed the search)

        Returns:
            PerplexityResearchResult with contacts and per-contact confidence scores
        """
        ...

    def _build_research_prompt(
        self,
        customer_contact: "CustomerProvidedContact",
    ) -> str:
        """
        Build the Perplexity research prompt.

        Includes customer-provided context so the LM can enrich/verify existing data.
        Requests:
        - HR/Payroll/Finance department contacts
        - Named individuals with titles
        - Phone numbers and email addresses
        - Website contact forms
        - Per-contact source attribution
        - Department classification per contact
        """
        ...

    def _parse_response_with_confidence(
        self,
        response_data: dict,
        customer_contact: "CustomerProvidedContact",
    ) -> PerplexityResearchResult:
        """
        Parse Perplexity API response into structured contacts with embedded confidence.

        Confidence formula per contact:
            source_reliability = SOURCE_CONFIDENCE[source_type]
            completeness = sum(
                0.15 if name else 0,
                0.10 if title else 0,
                0.20 if email else 0,
                0.20 if phone else 0,
                0.10 if department else 0,
            )
            confidence = min(source_reliability * 0.5 + completeness * 0.5, 1.0)

        Also extracts citations from Perplexity response annotations.
        """
        ...
```

### 3.3 deduplicator.py — DSPy ChainOfThought Deduplication

Fuzzy LM-powered deduplication runs **before** classification. Uses DSPy ChainOfThought so the LM can reason about which contacts are duplicates across different sources with slightly different formatting.

```python
import dspy
from typing import List
from pydantic import BaseModel, Field

class DeduplicatedContact(BaseModel):
    """A contact after deduplication, with merge provenance."""
    name: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    source_urls: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    has_contact_form: bool = False
    contact_form_url: Optional[str] = None
    notes: Optional[str] = None
    is_customer_provided: bool = False
    merged_from_count: int = 1          # How many raw contacts were merged into this one

class DeduplicateContacts(dspy.Signature):
    """
    Deduplicate employer contacts discovered from multiple sources.

    Given a list of raw contacts (some from the customer, some from web research),
    identify duplicates using fuzzy matching on name, email, phone, and department.
    Merge duplicates by keeping the most complete information from each source.
    Preserve the is_customer_provided flag — customer contacts always take precedence
    when merging conflicting fields.
    """
    raw_contacts_json: str = dspy.InputField(
        desc="JSON array of raw contacts with fields: name, title, department, "
             "phone, email, source_url, confidence_score, is_customer_provided"
    )
    employer_context: str = dspy.InputField(
        desc="Employer name, country, and any known aliases to aid matching"
    )
    deduplicated_contacts_json: str = dspy.OutputField(
        desc="JSON array of deduplicated contacts. Each has merged_from_count >= 1. "
             "Duplicates are merged: keep best name, highest confidence, all source_urls, "
             "customer-provided fields take precedence. Output valid JSON only."
    )
    dedup_reasoning: str = dspy.OutputField(
        desc="Step-by-step reasoning explaining which contacts were identified as "
             "duplicates and why (e.g., 'Contact 3 and Contact 7 share the same email "
             "hr@acme.com and similar phone numbers — merged into one')"
    )

class EmployerContactDeduplicator:
    """
    DSPy ChainOfThought deduplication for employer contacts.

    Why LM-powered (not regex/deterministic):
    - Phone numbers appear in different formats across sources (+61 3 9876 5432 vs 03-9876-5432)
    - Names may be partial ("J. Smith" vs "Jane Smith")
    - Email addresses may differ but belong to same person (jane.smith@ vs j.smith@)
    - Department names vary ("HR" vs "Human Resources" vs "People & Culture")
    """

    def __init__(self, lm: Optional[dspy.LM] = None):
        """
        Args:
            lm: DSPy language model. Defaults to configured LM.
                Recommended: gpt-4o-mini for cost efficiency (dedup is reasoning-heavy
                but doesn't need the strongest model).
        """
        self.dedup = dspy.ChainOfThought(DeduplicateContacts)
        if lm:
            self._lm = lm

    async def deduplicate(
        self,
        raw_contacts: List[RawDiscoveredContact],
        employer_name: str,
        country: str,
        customer_contacts: List["CustomerProvidedContact"],
    ) -> List[DeduplicatedContact]:
        """
        Deduplicate contacts using DSPy ChainOfThought.

        Steps:
        1. Convert customer-provided contacts to RawDiscoveredContact format
           with is_customer_provided=True and confidence_score=1.0
        2. Merge customer + research contacts into a single list
        3. Serialise to JSON for DSPy signature input
        4. Run ChainOfThought deduplication
        5. Parse output JSON into DeduplicatedContact list
        6. Validate: ensure no contacts were silently dropped

        Args:
            raw_contacts: Contacts from Perplexity research
            employer_name: Company name for context
            country: Country for context
            customer_contacts: Customer-provided contacts (always preserved)

        Returns:
            List[DeduplicatedContact] — unique contacts with merge provenance
        """
        ...
```

### 3.4 classifier.py — DSPy Predict Classification + Prioritisation (One Step)

The LM sees **all** deduplicated contacts at once and classifies + prioritises them in a **single step**. The 7-tier prioritisation logic from PRD §5.2 is provided as guidance to the LM via the signature docstring and dspy.Example demonstrations.

```python
import dspy
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class EmployerContactType(str, Enum):
    """Contact type taxonomy per PRD §3.2."""
    GENERAL = "general"
    NAMED_POC = "named_poc"
    VALIDATED_POC = "validated_poc"

class EmployerDepartment(str, Enum):
    """Department classification per PRD §5.1."""
    HR = "HR"
    PAYROLL = "Payroll"
    FINANCE = "Finance"
    RECEPTION = "Reception"
    GENERAL = "General"

class ClassifiedPrioritisedContact(BaseModel):
    """A contact after classification and prioritisation."""
    name: Optional[str] = None
    title: Optional[str] = None
    department: EmployerDepartment = EmployerDepartment.GENERAL
    phone: Optional[str] = None
    email: Optional[str] = None
    contact_type: EmployerContactType = EmployerContactType.GENERAL
    priority_tier: int = Field(ge=1, le=7, description="1=highest, 7=lowest")
    confidence_score: float = Field(ge=0.0, le=1.0)
    source_urls: List[str] = Field(default_factory=list)
    has_contact_form: bool = False
    contact_form_url: Optional[str] = None
    notes: Optional[str] = None
    is_customer_provided: bool = False

class ClassifyAndPrioritiseContacts(dspy.Signature):
    """
    Classify and prioritise employer contacts for verification outreach.

    CLASSIFICATION RULES (PRD §3.2):
    - GENERAL: Department/reception without a named individual (e.g., "HR Department" + phone, info@ email)
    - NAMED_POC: Specific individual with name AND at least phone or email (e.g., "Jane Smith, HR Manager")
    - Exception: CEO/Founder/Managing Director counts as NAMED_POC for small employers (<50 employees)

    DEPARTMENT DETECTION:
    - HR: titles containing "hr", "human resources", "people operations", "talent"
    - Payroll: titles containing "payroll", "compensation", "benefits"
    - Finance: titles containing "finance", "cfo", "accounting"
    - Reception: titles containing "receptionist", "front desk", "office manager"

    PRIORITISATION TIERS (PRD §5.2):
    - Tier 1: Named POC in HR/Payroll with direct phone + email
    - Tier 2: Named POC in HR/Payroll with phone only
    - Tier 3: HR department general phone number
    - Tier 4: Named POC with email only
    - Tier 5: General reception/main line phone number
    - Tier 6: Department email addresses (hr@, payroll@, info@)
    - Tier 7: Website contact form only

    CUSTOMER-PROVIDED contacts always take top position WITHIN their assigned tier.
    """
    contacts_json: str = dspy.InputField(
        desc="JSON array of deduplicated contacts to classify and prioritise"
    )
    employer_context: str = dspy.InputField(
        desc="Employer name, country, estimated size (if known), and industry"
    )
    classified_contacts_json: str = dspy.OutputField(
        desc="JSON array of contacts with added fields: contact_type (general|named_poc), "
             "department (HR|Payroll|Finance|Reception|General), "
             "priority_tier (1-7). Sorted by priority_tier ascending, "
             "customer-provided contacts first within each tier. Output valid JSON only."
    )
    classification_reasoning: str = dspy.OutputField(
        desc="Brief reasoning for classification and prioritisation decisions"
    )

# dspy.Example demonstrations for the classifier
CLASSIFIER_EXAMPLES = [
    dspy.Example(
        contacts_json='[{"name": "Sarah Chen", "title": "HR Manager", "phone": "+61 3 9876 5432", "email": "sarah.chen@acme.com.au", "is_customer_provided": false}]',
        employer_context="Acme Corp Pty Ltd, Australia, ~200 employees, Manufacturing",
        classified_contacts_json='[{"name": "Sarah Chen", "title": "HR Manager", "department": "HR", "phone": "+61 3 9876 5432", "email": "sarah.chen@acme.com.au", "contact_type": "named_poc", "priority_tier": 1, "confidence_score": 0.85, "is_customer_provided": false}]',
        classification_reasoning="Sarah Chen is a named individual (HR Manager) with both phone and email → named_poc, HR department, Tier 1."
    ).with_inputs("contacts_json", "employer_context"),

    dspy.Example(
        contacts_json='[{"name": null, "title": null, "department": "HR", "phone": "+61 3 9876 0000", "email": "hr@acme.com.au", "is_customer_provided": true}, {"name": "John Lee", "title": "CEO", "phone": "+61 3 9876 0001", "email": "john@smallco.com.au", "is_customer_provided": false}]',
        employer_context="SmallCo Pty Ltd, Australia, ~15 employees, Retail",
        classified_contacts_json='[{"name": null, "department": "HR", "phone": "+61 3 9876 0000", "email": "hr@acme.com.au", "contact_type": "general", "priority_tier": 3, "confidence_score": 1.0, "is_customer_provided": true}, {"name": "John Lee", "title": "CEO", "department": "General", "phone": "+61 3 9876 0001", "email": "john@smallco.com.au", "contact_type": "named_poc", "priority_tier": 1, "confidence_score": 0.75, "is_customer_provided": false}]',
        classification_reasoning="First contact is unnamed HR department phone (general, Tier 3, customer-provided so top of tier). John Lee is CEO of a small employer (<50 employees) → named_poc exception applies, Tier 1 with both phone+email."
    ).with_inputs("contacts_json", "employer_context"),

    dspy.Example(
        contacts_json='[{"name": null, "has_contact_form": true, "contact_form_url": "https://acme.com/contact", "is_customer_provided": false}]',
        employer_context="Acme Corp, United States, ~5000 employees, Technology",
        classified_contacts_json='[{"name": null, "department": "General", "contact_type": "general", "priority_tier": 7, "has_contact_form": true, "contact_form_url": "https://acme.com/contact", "confidence_score": 0.3, "is_customer_provided": false}]',
        classification_reasoning="Only a contact form with no name/phone/email → general, Tier 7."
    ).with_inputs("contacts_json", "employer_context"),
]

class EmployerContactClassifier:
    """
    DSPy Predict classifier + prioritiser in ONE step.

    The LM sees ALL contacts at once (not one-at-a-time) because:
    - Relative prioritisation requires seeing the full picture
    - Customer-provided contacts need to be ranked within their tier
    - Department detection benefits from seeing the employer context holistically
    - Small employer exception requires knowing ALL contacts, not just one

    Uses dspy.Example demonstrations to show the LM the 7-tier prioritisation logic.
    """

    def __init__(self, lm: Optional[dspy.LM] = None):
        """
        Args:
            lm: DSPy language model. Defaults to configured LM.
                Recommended: gpt-4o-mini or claude-haiku for cost efficiency.
        """
        self.classify = dspy.Predict(ClassifyAndPrioritiseContacts)
        if lm:
            self._lm = lm

    async def classify_and_prioritise(
        self,
        contacts: List[DeduplicatedContact],
        employer_name: str,
        country: str,
        employer_size_estimate: Optional[int] = None,
        industry: Optional[str] = None,
    ) -> List[ClassifiedPrioritisedContact]:
        """
        Classify and prioritise all contacts in one DSPy Predict call.

        Args:
            contacts: Deduplicated contacts from deduplicator
            employer_name: Company name
            country: Country
            employer_size_estimate: Approximate employee count (for small employer exception)
            industry: Industry sector (for context)

        Returns:
            List[ClassifiedPrioritisedContact] sorted by priority_tier ascending,
            customer-provided contacts first within each tier.
        """
        ...
```

### 3.5 repository.py — EmployerContactRepository

```python
from typing import List, Optional
from models.contacts import EmployerContact, AdditionalContact

class EmployerContactRepository:
    """
    Adapter: asyncpg CRUD for employer contacts in university_contacts table.

    Uses the existing discriminator pattern (entity_type='employer').
    Primary contact → table-level columns.
    Additional contacts → additional_contacts JSONB column.
    """

    async def store_contacts(
        self,
        employer_name: str,
        country: str,
        customer_id: int,
        primary_contact: ClassifiedPrioritisedContact,
        additional_contacts: List[ClassifiedPrioritisedContact],
        case_id: Optional[int] = None,
    ) -> int:
        """
        Store classified contacts to university_contacts table.

        The highest-priority contact becomes the primary (table-level columns).
        All others go into additional_contacts JSONB array.

        Returns: database ID of the created/updated employer contact record.
        """
        ...

    async def get_contacts_for_employer(
        self,
        employer_name: str,
        customer_id: int,
    ) -> Optional[EmployerContact]:
        """
        Retrieve the employer contact record including additional_contacts JSONB.
        Filters by entity_type='employer'.
        """
        ...

    async def update_contact_type(
        self,
        contact_id: int,
        new_type: str,  # 'general' | 'named_poc' | 'validated_poc'
    ) -> bool:
        """Update contact_type field. Used when promoting to validated_poc."""
        ...

    async def mark_contact_invalid(
        self,
        contact_id: int,
        reason: str,
    ) -> bool:
        """Mark a contact as invalid (wrong number, refused, etc.)."""
        ...

    async def find_validated_poc(
        self,
        employer_name: str,
        customer_id: int,
    ) -> Optional[AdditionalContact]:
        """Find an existing validated_poc for this employer (contact reuse across checks)."""
        ...

    async def upsert_additional_contact(
        self,
        contact_id: int,
        new_contact: AdditionalContact,
    ) -> bool:
        """
        Add a new contact to the additional_contacts JSONB array.
        Runs a dedup check against existing additional_contacts before inserting.
        """
        ...
```

### 3.6 router.py — Entrypoints

```python
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/v1/employer-research", tags=["employer-research"])

@router.post("/research")
async def research_employer(
    request: EmployerResearchRequest,
    user: AuthenticatedUser = Depends(require_dual_auth),
) -> EmployerResearchResponse:
    """
    Trigger employer contact research.

    Thin entrypoint — delegates immediately to EmployerResearchService.
    Called by:
    1. The Prefect orchestrator (via channel_dispatch for 'research' channel_type)
    2. Manual API call for ad-hoc research
    """
    ...

# Prefect task wrapper (for integration with verification_orchestrator_flow)
async def prefect_research_task(
    case_id: int,
    customer_id: int,
    employer_name: str,
    country: str,
    customer_contacts: List[dict],
) -> dict:
    """
    Prefect task wrapper for employer contact research.

    Called by channel_dispatch.py when channel_type='research'.
    Returns dict with task result for process_result.py consumption.
    """
    ...
```

---

## 4. Data Model Changes

### 4.1 Extensions to `models/contacts.py` — EmployerContact

Add the following fields to the existing `EmployerContact` class:

```python
class EmployerContact(BaseContact):
    """
    Employer-specific contact for employment verification.
    (Existing class — add these new fields)
    """

    # Existing fields (unchanged):
    # employer_name: str

    # NEW fields:
    contact_type: str = Field(
        default="general",
        description="Contact classification: general | named_poc | validated_poc"
    )
    has_contact_form: bool = Field(
        default=False,
        description="Whether the employer website has a contact form"
    )
    contact_form_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="URL of the employer's contact form"
    )
    source_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="URL where the primary contact was discovered"
    )

    @field_validator("contact_type")
    @classmethod
    def validate_contact_type(cls, v: str) -> str:
        valid_types = {"general", "named_poc", "validated_poc"}
        if v not in valid_types:
            raise ValueError(f"contact_type must be one of {valid_types}, got '{v}'")
        return v
```

### 4.2 Extensions to `AdditionalContact` in `models/contacts.py`

Add fields to support classification and prioritisation metadata in JSONB:

```python
class AdditionalContact(BaseModel):
    """
    Additional contact person within the same entity.
    (Existing class — add these new fields)
    """

    # Existing fields (unchanged):
    # contact_name, department, email, phone, position, routing_metadata

    # NEW fields:
    contact_type: str = Field(
        default="general",
        description="Contact classification: general | named_poc | validated_poc"
    )
    priority_tier: Optional[int] = Field(
        default=None,
        ge=1, le=7,
        description="Outreach priority tier (1=highest, 7=lowest)"
    )
    source_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="URL where this contact was discovered"
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0, le=1.0,
        description="Confidence in contact accuracy"
    )
    is_customer_provided: bool = Field(
        default=False,
        description="Whether this contact was provided by the customer"
    )
    has_contact_form: bool = Field(
        default=False,
        description="Whether this is a contact form entry"
    )
    contact_form_url: Optional[str] = Field(
        default=None,
        description="URL of the contact form"
    )
```

### 4.3 New CallResultStatus Enum Values

Add to `utils/background_task_helpers.py`:

```python
class CallResultStatus(str, Enum):
    # ... existing values ...

    # NEW: Employer contact research states
    CONTACTS_DISCOVERED = "contacts_discovered"
    ALTERNATE_CONTACT_RECEIVED = "alternate_contact_received"
    CONTACT_VALIDATED = "contact_validated"
    COMPLETED_DISCREPANCIES = "completed_discrepancies"
```

**Database migration required**: `ALTER TYPE call_result_status ADD VALUE` for each new value.

### 4.4 Database Schema Changes

**Migration file**: `0XX_employer_research_fields.sql`

```sql
-- Add contact_type to university_contacts table
ALTER TABLE university_contacts
    ADD COLUMN IF NOT EXISTS contact_type VARCHAR(50) DEFAULT 'general';

-- Add has_contact_form to university_contacts table
ALTER TABLE university_contacts
    ADD COLUMN IF NOT EXISTS has_contact_form BOOLEAN DEFAULT FALSE;

-- Add contact_form_url to university_contacts table
ALTER TABLE university_contacts
    ADD COLUMN IF NOT EXISTS contact_form_url TEXT;

-- Add source_url to university_contacts table
ALTER TABLE university_contacts
    ADD COLUMN IF NOT EXISTS source_url TEXT;

-- Add new call_result_status enum values
ALTER TYPE call_result_status ADD VALUE IF NOT EXISTS 'contacts_discovered';
ALTER TYPE call_result_status ADD VALUE IF NOT EXISTS 'alternate_contact_received';
ALTER TYPE call_result_status ADD VALUE IF NOT EXISTS 'contact_validated';
ALTER TYPE call_result_status ADD VALUE IF NOT EXISTS 'completed_discrepancies';

-- Index for employer contact lookups
CREATE INDEX IF NOT EXISTS idx_university_contacts_employer_lookup
    ON university_contacts (employer_name, entity_type)
    WHERE entity_type = 'employer';

-- Index for contact_type filtering
CREATE INDEX IF NOT EXISTS idx_university_contacts_contact_type
    ON university_contacts (contact_type)
    WHERE entity_type = 'employer';

-- Seed default employer outreach sequence
INSERT INTO background_check_sequence (check_type_config_id, step_order, step_name, channel_type, delay_hours, max_attempts)
SELECT ct.id, s.step_order, s.step_name, s.channel_type, s.delay_hours, s.max_attempts
FROM check_type_configs ct
CROSS JOIN (VALUES
    (1, 'contact_research', 'research', 0, 1),
    (2, 'call_attempt', 'voice', 0, 3),
    (3, 'email_outreach', 'email', 0, 1),
    (4, 'call_retry', 'voice', 24, 2),
    (5, 'email_reminder', 'email', 48, 1)
) AS s(step_order, step_name, channel_type, delay_hours, max_attempts)
WHERE ct.name = 'work_history'
ON CONFLICT DO NOTHING;
```

### 4.5 verification_metadata JSONB Structure (on cases)

No new model — this is already stored as JSONB on the `cases` table. The structure for employer verification:

```json
{
  "employer": {
    "name": "Acme Corp Pty Ltd",
    "country": "Australia",
    "city": "Melbourne",
    "website_url": "https://acmecorp.com.au"
  },
  "candidate": {
    "name": "John Doe",
    "job_title": "Software Engineer",
    "start_date": "2020-01-15",
    "end_date": "2023-06-30",
    "reason_for_leaving": "Resigned"
  },
  "verify_fields": ["job_title", "dates_of_employment", "reason_for_leaving"],
  "customer_provided_contacts": [
    {"phone_number": "+61 3 9876 5432", "contact_name": null}
  ]
}
```

---

## 5. File-by-File Implementation Plan

### Phase 1: Core Pipeline (Files 1–8)

| # | File | Purpose | Dependencies | Tests |
|---|------|---------|-------------|-------|
| 1 | `models/contacts.py` | Extend EmployerContact + AdditionalContact with new fields | None | Existing tests + new field validation tests |
| 2 | `utils/background_task_helpers.py` | Add 4 new CallResultStatus values | None | Enum membership tests |
| 3 | `database/migrations/0XX_employer_research_fields.sql` | Schema changes + seed data | PostgreSQL | Manual migration verification |
| 4 | `employer_research/__init__.py` | Public exports | — | — |
| 5 | `employer_research/researcher.py` | Perplexity API with embedded confidence | `models/contacts.py` | `test_researcher.py` |
| 6 | `employer_research/deduplicator.py` | DSPy ChainOfThought dedup | `dspy` package | `test_deduplicator.py` |
| 7 | `employer_research/classifier.py` | DSPy Predict classify + prioritise | `dspy` package | `test_classifier.py` |
| 8 | `employer_research/repository.py` | asyncpg CRUD | `models/contacts.py`, DB | `test_repository.py` |

### Phase 2: Service + Entrypoints (Files 9–10)

| # | File | Purpose | Dependencies | Tests |
|---|------|---------|-------------|-------|
| 9 | `employer_research/service.py` | Pipeline orchestrator | Files 5–8 | `test_service.py` |
| 10 | `employer_research/router.py` | FastAPI + Prefect entrypoints | File 9 | Integration tests |

### Phase 3: Orchestrator Integration (Files 11–12)

| # | File | Purpose | Dependencies | Tests |
|---|------|---------|-------------|-------|
| 11 | `prefect_flows/flows/tasks/channel_dispatch.py` | Add 'research' channel type | File 10 | `test_task_wiring.py` |
| 12 | `prefect_flows/flows/tasks/sla_config.py` | Add employer default sequence | DB seed | `test_check_sequence_service.py` |

### Phase 4: Cleanup (Files 13–14)

| # | File | Purpose | Dependencies | Tests |
|---|------|---------|-------------|-------|
| 13 | `employer_search/research.py` | DELETE | — | — |
| 14 | `employer_search/__init__.py` | DELETE | — | — |

### Recommended Implementation Sequence

```
┌────────────┐   ┌────────────────────┐
│ File 1     │   │ File 2             │   ← Can be done in PARALLEL
│ contacts.py│   │ background_task_   │
│ (extend)   │   │ helpers.py (extend)│
└─────┬──────┘   └─────┬──────────────┘
      │                 │
      ▼                 ▼
┌────────────────────────┐
│ File 3: Migration SQL  │   ← Depends on both above
└─────────┬──────────────┘
          │
          ▼
┌──────────┐ ┌──────────────┐ ┌──────────────┐
│ File 5   │ │ File 6       │ │ File 7       │   ← Can be done in PARALLEL
│ researcher│ │ deduplicator │ │ classifier   │
└────┬─────┘ └──────┬───────┘ └──────┬───────┘
     │              │                │
     ▼              ▼                ▼
┌────────────────────────────────────────────┐
│ File 8: repository.py                       │
│ File 9: service.py (integrates 5–8)         │   ← Sequential
│ File 10: router.py                          │
└─────────────────┬──────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────┐
│ Files 11-12: Prefect integration           │   ← Sequential
│ Files 13-14: Delete employer_search/       │
└────────────────────────────────────────────┘
```

---

## 6. Test Strategy

### 6.1 Test Categories

| Category | Files | Coverage Target | Runner |
|----------|-------|----------------|--------|
| Unit — Domain models | `tests/unit/test_contacts.py` (extend) | 100% branches | pytest |
| Unit — Deduplicator | `employer_research/tests/test_deduplicator.py` | 90%+ | pytest + DSPy mock |
| Unit — Classifier | `employer_research/tests/test_classifier.py` | 90%+ | pytest + DSPy mock |
| Unit — Researcher | `employer_research/tests/test_researcher.py` | 85%+ | pytest + aiohttp mock |
| Unit — Repository | `employer_research/tests/test_repository.py` | 80%+ | pytest + asyncpg mock |
| Integration — Service | `employer_research/tests/test_service.py` | Full pipeline | pytest |
| Integration — Prefect | `tests/prefect/test_task_wiring.py` (extend) | Channel dispatch | pytest |

### 6.2 conftest.py — Test Fixtures

```python
# employer_research/tests/conftest.py

import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def sample_customer_contact():
    """Minimal customer-provided contact (often incomplete)."""
    return CustomerProvidedContact(
        employer_name="Acme Corp Pty Ltd",
        country="Australia",
        city="Melbourne",
        phone_number="+61 3 9876 5432",
    )

@pytest.fixture
def sample_customer_contact_complete():
    """Fully-specified customer contact."""
    return CustomerProvidedContact(
        employer_name="TechStart Pty Ltd",
        country="Australia",
        city="Sydney",
        website_url="https://techstart.com.au",
        phone_number="+61 2 1234 5678",
        contact_name="Jane Smith",
        contact_email="jane@techstart.com.au",
    )

@pytest.fixture
def mock_perplexity_response():
    """Realistic Perplexity API response with citations."""
    return {
        "choices": [{
            "message": {
                "content": "HR Department contacts for Acme Corp...\n"
                    "1. Sarah Chen, HR Manager — sarah.chen@acme.com.au, +61 3 9876 5433\n"
                    "2. HR Department general: hr@acme.com.au, +61 3 9876 5400\n"
                    "3. Contact form: https://acme.com.au/contact",
                "annotations": [
                    {"url": "https://acme.com.au/about/team"},
                    {"url": "https://linkedin.com/company/acme-corp"},
                ]
            }
        }],
        "citations": ["https://acme.com.au/about/team"]
    }

@pytest.fixture
def sample_raw_contacts():
    """Contacts as returned by researcher.research()."""
    return [
        RawDiscoveredContact(
            name="Sarah Chen", title="HR Manager", department="HR",
            phone="+61 3 9876 5433", email="sarah.chen@acme.com.au",
            source_url="https://acme.com.au/about/team",
            confidence_score=0.85,
        ),
        RawDiscoveredContact(
            name=None, department="HR",
            phone="+61 3 9876 5400", email="hr@acme.com.au",
            source_url="https://acme.com.au/contact",
            confidence_score=0.70,
        ),
        RawDiscoveredContact(
            name=None, has_contact_form=True,
            contact_form_url="https://acme.com.au/contact",
            confidence_score=0.30,
        ),
    ]

@pytest.fixture
def mock_dspy_dedup_response():
    """Mocked DSPy ChainOfThought output for deduplication."""
    return {
        "deduplicated_contacts_json": '[...]',  # Parsed in test
        "dedup_reasoning": "No duplicates found in this set.",
    }

@pytest.fixture
def mock_dspy_classify_response():
    """Mocked DSPy Predict output for classification + prioritisation."""
    return {
        "classified_contacts_json": '[...]',  # Parsed in test
        "classification_reasoning": "Sarah Chen is named HR Manager with phone+email → Tier 1.",
    }
```

### 6.3 Key Test Scenarios

#### Deduplicator Tests (`test_deduplicator.py`)

| Scenario | Input | Expected |
|----------|-------|----------|
| No duplicates | 3 distinct contacts | 3 contacts, all merged_from_count=1 |
| Exact email match | 2 contacts with same email | 1 merged contact, merged_from_count=2 |
| Fuzzy phone match | "+61 3 9876 5432" vs "03 9876 5432" | 1 merged contact |
| Fuzzy name match | "J. Smith" vs "Jane Smith" (same email) | 1 merged contact |
| Customer-provided precedence | Customer contact merged with research contact | Customer fields take precedence |
| No contacts | Empty list | Empty list returned |
| All duplicates | 5 contacts, all same person | 1 merged contact, merged_from_count=5 |

#### Classifier Tests (`test_classifier.py`)

| Scenario | Input | Expected |
|----------|-------|----------|
| Named HR with phone+email | name + HR title + phone + email | named_poc, Tier 1 |
| Named HR phone only | name + HR title + phone | named_poc, Tier 2 |
| General HR phone | no name + HR dept + phone | general, Tier 3 |
| Named email only | name + email, no phone | named_poc, Tier 4 |
| General reception | no name + phone | general, Tier 5 |
| Department email | hr@ email, no name | general, Tier 6 |
| Contact form only | has_contact_form=True | general, Tier 7 |
| Small employer CEO | CEO + <50 employees | named_poc (exception) |
| Customer first in tier | 2 Tier 1 contacts, one customer-provided | Customer contact listed first |
| Multiple tiers sorted | Contacts across tiers 1-7 | Sorted ascending by tier |

#### Researcher Tests (`test_researcher.py`)

| Scenario | Input | Expected |
|----------|-------|----------|
| Successful research | Valid company + country | success=True, contacts > 0 |
| No API key | Missing PERPLEXITY_API_KEY | success=False, error message |
| API error (500) | Server error response | success=False, error captured |
| Confidence embedded | Response with citations | Per-contact confidence_score > 0 |
| Customer context in prompt | Customer-provided phone | Phone mentioned in prompt |
| Contact form detection | Response mentions contact form | has_contact_form=True |

#### Service Tests (`test_service.py`)

| Scenario | Input | Expected |
|----------|-------|----------|
| Full pipeline happy path | Customer contact → research → dedup → classify → store | ResearchPipelineResult with contacts |
| No additional contacts found | Research finds nothing beyond customer contact | Customer contact stored as primary |
| Research failure | Perplexity API fails | Graceful degradation, customer contacts still stored |
| Alternate contact addition | New contact during call | Dedup check + store |
| POC validation | validate_poc called | contact_type updated to validated_poc |

#### Repository Tests (`test_repository.py`)

| Scenario | Input | Expected |
|----------|-------|----------|
| Store new employer | New employer + contacts | Row created with entity_type='employer' |
| Store with additional_contacts | 1 primary + 3 additional | JSONB populated correctly |
| Get contacts | employer_name + customer_id | EmployerContact with additional_contacts |
| Update contact_type | named_poc → validated_poc | Updated in DB |
| Mark invalid | wrong_number | routing_metadata updated |

### 6.4 DSPy Testing Strategy

DSPy modules are tested by **mocking the LM** rather than making real API calls:

```python
# In test files:
import dspy

def test_classifier_with_mock_lm():
    """Test classifier with mocked DSPy LM."""
    # Configure a mock LM that returns predictable JSON
    mock_lm = MagicMock(spec=dspy.LM)
    # ... configure mock responses ...

    classifier = EmployerContactClassifier(lm=mock_lm)
    result = classifier.classify_and_prioritise(
        contacts=sample_contacts,
        employer_name="Acme Corp",
        country="Australia",
    )

    assert len(result) == 3
    assert result[0].priority_tier <= result[1].priority_tier
```

For integration testing with real LMs, use `@pytest.mark.integration` and gate behind `DSPY_INTEGRATION_TESTS=1` env var.

---

## 7. Acceptance Criteria Mapping

| PRD Section | TS Component | Test File | Acceptance Criterion |
|-------------|-------------|-----------|---------------------|
| §3.2 Contact Classification | `classifier.py` (DSPy Predict) | `test_classifier.py` | 3-tier taxonomy (general, named_poc, validated_poc) correctly assigned |
| §3.2 Small Employer Exception | `classifier.py` (DSPy Example demo) | `test_classifier.py` | CEO/Founder counts as named_poc when employer <50 employees |
| §5.1 Research Agent | `researcher.py` (Perplexity API) | `test_researcher.py` | Exhaustive contact list with per-contact source attribution |
| §5.1 Confidence Scoring | `researcher.py` (embedded) | `test_researcher.py` | Confidence 0.0–1.0 based on source reliability + completeness |
| §5.2 Contact Prioritisation | `classifier.py` (DSPy Predict, 7-tier) | `test_classifier.py` | Contacts sorted by tier, customer-provided first within tier |
| §7.1 employer_contacts table | `models/contacts.py` + migration | `test_contacts.py` | EmployerContact extended with contact_type, has_contact_form, source_url |
| §7.2 New result_status values | `utils/background_task_helpers.py` | Unit test | 4 new enum values present |
| §7.3 New action_type values | Migration SQL + sla_config | `test_check_sequence_service.py` | contact_research, scheduled_callback, calendar_invite in sequence |
| §8.1 Research step type | `channel_dispatch.py` | `test_task_wiring.py` | 'research' channel_type dispatches to employer_research service |
| §9 Success metrics | `service.py` pipeline | `test_service.py` | Research produces 8-15 contacts, <2 min, full audit trail |
| §13 Clean Architecture | Directory structure | Code review | Feature-first directory, layers respected |
| PRD §4 Customer contacts as input | `service.py` pipeline entry | `test_service.py` | Customer contacts always provided as pipeline input |
| Review #1 Dedup before classify | `deduplicator.py` before `classifier.py` | `test_service.py` | Dedup runs first, classifier sees unique contacts only |
| Review #2 DSPy for classify+prioritise | `classifier.py` uses dspy.Predict | `test_classifier.py` | Single LM call classifies AND prioritises all contacts |
| Review #3 DSPy ChainOfThought for dedup | `deduplicator.py` uses dspy.ChainOfThought | `test_deduplicator.py` | LM-powered fuzzy dedup with reasoning trace |
| Review #4 Delete employer_search | Files deleted | Directory inspection | employer_search/research.py removed |

---

## 8. Implementation Sequence (Recommended Order)

### Sprint 1: Foundation (Parallel-safe)

1. **File 1**: `models/contacts.py` — extend EmployerContact + AdditionalContact
2. **File 2**: `utils/background_task_helpers.py` — add CallResultStatus values
3. **File 3**: Migration SQL
4. **File 4**: `employer_research/__init__.py`
5. **Install DSPy**: `pip install dspy` — add to requirements.txt

### Sprint 2: Core Adapters (Parallelisable ⚡)

6. **File 5**: `employer_research/researcher.py` + `test_researcher.py`
7. **File 6**: `employer_research/deduplicator.py` + `test_deduplicator.py` ⚡
8. **File 7**: `employer_research/classifier.py` + `test_classifier.py` ⚡

(Files 6 and 7 can be developed in parallel — they have no mutual dependency.)

### Sprint 3: Integration

9. **File 8**: `employer_research/repository.py` + `test_repository.py`
10. **File 9**: `employer_research/service.py` + `test_service.py`
11. **File 10**: `employer_research/router.py`

### Sprint 4: Orchestrator + Cleanup

12. **File 11**: `prefect_flows/flows/tasks/channel_dispatch.py` — add research dispatch
13. **File 12**: `prefect_flows/flows/tasks/sla_config.py` — add employer sequence
14. **Files 13–14**: Delete `employer_search/research.py` and `employer_search/__init__.py`

---

## 9. DSPy Configuration

### 9.1 LM Configuration

```python
import dspy

# For employer research pipeline
# Use cost-efficient models for classification/dedup (high volume, moderate complexity)
employer_lm = dspy.LM(
    "openai/gpt-4o-mini",
    temperature=0.2,      # Low temperature for classification consistency
    max_tokens=4000,
    cache=True,           # Enable caching during development
)

# Configure as default for employer_research module
dspy.configure(lm=employer_lm)
```

### 9.2 Future Optimisation Path

Once sufficient training data exists (50+ examples from production usage):

```python
# Phase 3: Optimise with MIPROv2
trainset = load_training_examples()  # From production call outcomes

optimizer = dspy.MIPROv2(
    metric=classification_accuracy,
    auto="light",
    num_threads=8,
)
optimized_classifier = optimizer.compile(
    EmployerContactClassifier(),
    trainset=trainset,
)
optimized_classifier.save("models/employer_classifier_v1")
```

### 9.3 Async Integration

DSPy modules are synchronous by default. Wrap with `dspy.asyncify` for use in async service layer:

```python
# In service.py
async_dedup = dspy.asyncify(self.deduplicator.dedup)
result = await async_dedup(
    raw_contacts_json=contacts_json,
    employer_context=context,
)
```

---

## 10. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| DSPy is new dependency (no existing usage) | Medium | Medium | `eddy_validate/dspy_migration_design.md` already planned this; start with simple Predict/CoT modules |
| LM classification inconsistency | Medium | Low | dspy.Example demonstrations anchor expected behavior; add MIPROv2 optimisation in Phase 3 |
| Perplexity API rate limits | Low | Medium | Implement exponential backoff; cache results per employer |
| Dedup false positives (merges distinct contacts) | Low | Medium | ChainOfThought reasoning trace enables auditing; conservative merge policy |
| Migration breaks existing employer queries | Low | High | All new columns have defaults; partial indexes scoped to entity_type='employer' |
| DSPy JSON output parsing failures | Medium | Low | Wrap in try/except with retry; validate against Pydantic models |

---

## 11. Integration with Existing Prefect Pipeline

### 11.1 New `research` Channel Type

In `prefect_flows/flows/tasks/channel_dispatch.py`:

```python
async def dispatch_channel_verification(
    case_id: int,
    customer_id: int,
    task_id: int,
    check_type: str,
    channel_type: str,       # 'voice' | 'email' | 'research'
    step_config: dict,
) -> dict:
    if channel_type == "research":
        from employer_research.router import prefect_research_task
        return await prefect_research_task(
            case_id=case_id,
            customer_id=customer_id,
            employer_name=step_config["employer_name"],
            country=step_config["country"],
            customer_contacts=step_config.get("customer_contacts", []),
        )
    elif channel_type == "voice":
        # ... existing voice dispatch ...
    elif channel_type == "email":
        # ... existing email dispatch ...
```

### 11.2 Research Step Must Complete Before Outreach

The orchestrator already processes steps sequentially (step_order 1 → 2 → 3...). The research step (step_order=1) will complete and store contacts before the call_attempt step (step_order=2) executes.

### 11.3 Alternate Contact Injection

When `result_status = alternate_contact_received`:

```python
# In process_result.py or orchestrator
if result_status == "alternate_contact_received":
    new_contact = result_data["alternate_contact"]
    await employer_research_service.add_alternate_contact(
        employer_name=employer_name,
        customer_id=customer_id,
        new_contact=AdditionalContact(**new_contact),
    )
    # Schedule immediate call to new contact (next step, not append)
    await schedule_immediate_call(case_id, new_contact)
```

---

## 12. Open Design Decisions

| Decision | Current Position | Rationale | Revisit When |
|----------|-----------------|-----------|-------------|
| DSPy model choice for classify/dedup | gpt-4o-mini | Cost-efficient, sufficient for classification | If accuracy drops below 90% in production |
| Contact reuse TTL | Not implemented (Phase 3) | Needs usage data to determine freshness | 3 months after launch |
| Research depth threshold | Time-bounded (60s timeout) | Compliance requires "reasonable effort", not exhaustive | If <5 contacts discovered average |
| IVR navigation depth | Basic DTMF only (Phase 1) | Complex IVR traversal is Phase 3 scope | Phase 3 planning |

---

## 13. Glossary

| Term | Definition |
|------|-----------|
| **Customer-provided contact** | Contact info submitted by the background check company's client alongside the verification request |
| **General contact** | Department/reception without a named individual |
| **Named POC** | Specific individual with name AND phone or email |
| **Validated POC** | Person confirmed during a call to have HR/Payroll system access |
| **Priority tier** | 1–7 ranking determining outreach order (1 = highest priority) |
| **Deduplication** | Merging duplicate contacts from different sources into a single record |
| **ChainOfThought** | DSPy module that produces step-by-step reasoning before the answer |
| **Predict** | DSPy module for direct input→output prediction |
| **dspy.Example** | Training/demonstration example that shows the LM expected behavior |
