# Development Documentation

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Principles](#core-principles)
3. [Workflow Stages](#workflow-stages)
4. [Component Details](#component-details)
5. [LLM Integration](#llm-integration)
6. [Database Schema](#database-schema)
7. [Configuration](#configuration)
8. [Testing & Troubleshooting](#testing--troubleshooting)

---

## Architecture Overview

The AEA JOE Automation Tool processes job postings through three main stages:

1. **Scraping**: Downloads raw job data from AEA JOE
2. **LLM Processing**: Extracts and enriches structured information
3. **Matching**: Calculates fit scores and difficulty estimates

### Project Structure

```
aea-joe-tool/
├── scraper/              # Web scraping and data download
│   ├── joe_scraper.py
│   └── scheduler.py
├── processor/            # LLM processing and text extraction
│   ├── llm_parser.py
│   └── text_processor.py
├── matcher/              # Portfolio matching and scoring
│   ├── portfolio_reader.py
│   ├── fit_calculator.py
│   ├── llm_fit_evaluator.py
│   └── job_assessor.py
├── database/             # Database operations
│   ├── job_db.py
│   ├── models.py
│   └── migrate.py
├── config/               # Configuration settings
│   └── settings.py
├── webapp/               # Web interface
│   ├── app.py
│   ├── static/
│   └── templates/
└── main.py               # Main entry point
```

---

## Core Principles

### 1. Field Preservation

- **Existing values are preserved** unless new values are more complete or meaningful
- Empty/None values from LLM do NOT overwrite existing data
- Only meaningful values (non-None, non-empty strings) are used for updates
- User-edited fields (like `application_status`) are preserved during scraping

### 2. Incremental Processing

- All operations process in batches and save after each batch completes
- Processing can be interrupted and resumed safely
- Only unprocessed jobs are targeted for LLM processing
- Only changed jobs are recomputed for matching (unless forced)
- **Batch Size**: Configurable via `LLM_PROCESSING_BATCH_SIZE` (default: 20 jobs per batch)

### 3. Separation of Concerns

- **LLM Processing** updates: `position_type`, `field`, `level`, `requirements`, `extracted_deadline`, `application_portal_url`, `country`, `application_materials`, `references_separate_email`, `requires_separate_application`, `position_track`
- **Matching** updates: `fit_score`, `difficulty_score`, `difficulty_reasoning`, `fit_updated_at`, `fit_portfolio_hash`
- **Scraping** updates: Raw fields from AEA JOE (title, institution, description, deadline, location, etc.)

---

## Workflow Stages

### Stage 1: Scraping (`--update`)

**What it does:**
- Downloads latest job listings from AEA JOE XLS export
- Parses XML data into structured job objects
- Saves raw data to database

**Field Updates:**
- Updates: `title`, `institution`, `description`, `deadline`, `location`, `contact_info`, `posted_date`
- Preserves: `application_status` (if user-set), `fit_score` (if manually set)

**Auto-Processing Logic:**
- If ≤100 new postings: Automatically runs LLM processing + matching
- If >100 new postings: Warns user to run processing manually
- Web dashboard displays live batch progress (processing/matching) through the floating status panel powered by `/api/progress`.

**Database Operations:**
- Creates backup before scraping (if database changed)
- Marks expired jobs automatically
- Uses inter-process locking for concurrent access

### Stage 2: LLM Processing (`--process`)

**What it does:**
- Extracts structured information from job descriptions
- Classifies position track (junior tenure-track, senior tenure-track, teaching, industry, non-tenure track, other academia)
- Parses deadlines and application requirements
- Enriches fields with extracted data

**Field Updates (only if meaningful):**
- `position_type`: Job type classification
- `field`: Research field focus
- `level`: Position level (Assistant, Associate, Full, etc.)
- `requirements`: Extracted requirements and research areas
- `extracted_deadline`: Parsed deadline date
- `application_portal_url`: Application URL if found
- `country`: Country extracted from location
- `application_materials`: Required materials list
- `references_separate_email`: Boolean flag
- `requires_separate_application`: Boolean flag
- `position_track`: Classification (junior tenure-track, senior tenure-track, teaching, industry, non-tenure track, other academia)

**Preservation Logic:**
- Only updates fields that are currently empty/None OR if new value is more complete
- For `requirements` and `application_materials`: Appends new info if both exist
- For `field`, `level`, `position_type`: Only updates if existing value is missing
- Never overwrites with empty/None values

**Needs Processing Check (`needs_llm_processing`):**
A job needs LLM processing if ANY of these fields are empty:
- `extracted_deadline` (None or empty string)
- `application_portal_url` (None or empty string)
- `country` (None or empty string)
- `application_materials` (None or empty string)
- `requires_separate_application` (None only; False is a valid processed value)
- `references_separate_email` (None only; False is a valid processed value)
- `position_track` (None or empty string)

**Unified Function**: `database.needs_llm_processing(job)` - single source of truth used by both CLI and web interface.

**Concurrency & Batch Processing:**
- Uses `ThreadPoolExecutor` with configurable max concurrency (default: 3)
- Rate limiting via minimum call interval
- **Processes in batches of 20 jobs** (configurable via `LLM_PROCESSING_BATCH_SIZE`)
- **Saves after each batch completes** (not after all jobs finish)
- Logs progress: "Batch X/Y complete: N saved"
- If interrupted, completed batches are preserved

### Stage 3: Matching (`--match`)

**What it does:**
- Calculates fit scores based on portfolio alignment
- Estimates application difficulty (0-100 scale)
- Updates fit-related metadata
- Uses a single joint LLM prompt to return both fit and difficulty context per job

**Field Updates:**
- `fit_score`: Portfolio alignment score (0-100)
- `difficulty_score`: Application difficulty estimate (0-100)
- `difficulty_reasoning`: LLM reasoning for difficulty score
- `fit_updated_at`: Timestamp of last fit calculation
- `fit_portfolio_hash`: Hash of portfolio used for calculation

**Important:** Matching does NOT update `position_track` - that's only set during LLM processing.

**Needs Recompute Check (`needs_fit_recompute`):**
A job needs fit recomputation if:
- Either `fit_score` or `difficulty_score` is missing
- `position_track` is missing (needs LLM processing first)
- `fit_portfolio_hash` doesn't match current portfolio hash
- `fit_updated_at` is missing
- Job was updated after last fit calculation (`last_updated` > `fit_updated_at`)
- Force mode overrides the skip logic and recomputes regardless of existing scores

**Unified Function**: `database.needs_fit_recompute(job, portfolio_hash)` - single source of truth used by both CLI and web interface.

**Force Recompute (`--force-match`):**
- Overrides all checks and recomputes all jobs
- Useful when portfolio changes or you want fresh scores

**Caching:**
- Fit scores are cached based on `fit_updated_at` timestamp
- Only recomputes if portfolio changed or job updated
- Prevents unnecessary LLM API calls

**Execution Pattern:**
- Still chunks work into batches of `LLM_PROCESSING_BATCH_SIZE` for progress logging
- Within each batch, jobs run sequentially so the joint prompt can persist results immediately
- Saves after every job, providing resumability even mid-batch
- Skips jobs that already have both scores unless force mode is enabled
- Logs heuristic fallbacks when the LLM call fails and the heuristic score is used

---

## Component Details

### Scraper Module (`scraper/joe_scraper.py`)

Handles downloading and parsing job data from AEA JOE's export endpoint.

**Key Functions:**
- `download_job_data()`: Downloads XLS data from JOE
- `parse_job_listings()`: Converts raw data to structured format
- `identify_new_postings()`: Detects new vs. existing postings

### Database Module (`database/job_db.py`)

Manages the local job database with CRUD operations.

**Key Features:**
- Job posting storage with unique identifiers
- Update and query operations
- Status tracking (pending, new, applied, rejected, expired, unrelated)
- Inter-process locking for concurrent access
- WAL mode for better concurrency

**Unified Checking Functions:**
- `needs_llm_processing(job)`: Determines if job needs LLM processing
- `needs_fit_recompute(job, portfolio_hash)`: Determines if job needs fit recomputation

### Processor Module (`processor/llm_parser.py`)

Uses LLMs to extract structured information from job descriptions.

**Key Functions:**
- `extract_job_details()` / `extract_job_details_batch()`: Extracts position type, field, requirements
- `parse_deadlines()` / `parse_deadlines_batch()`: Identifies application deadlines
- `classify_position()` / `classify_position_batch()`: Categorizes position level and type
- `execute_llm_tasks()`: Concurrent LLM task execution with rate limiting

### Matcher Module (`matcher/`)

**fit_calculator.py**: Calculates job fit/difficulty scores based on portfolio alignment
- `calculate_fit_score()`: Single job fit calculation
- `calculate_fit_scores_with_difficulty()`: Sequential fit/difficulty calculation using the joint prompt
- `score_job_with_joint_prompt()`: Helper that wraps the joint LLM call with heuristic fallbacks
- `rank_jobs()`: Ranks jobs by fit score

**llm_fit_evaluator.py**: LLM-based fit score evaluation
- `evaluate_fit_with_llm()`: Single job LLM fit evaluation
- `evaluate_fit_with_llm_batch()`: Batch LLM fit evaluation
- `evaluate_fit_and_difficulty()`: Joint prompt returning both fit and difficulty details per job

**job_assessor.py**: Position track and difficulty assessment
- `evaluate_position_track_batch()`: Classifies position tracks

**Matching Criteria:**
- Research Alignment (40%)
- Qualification Match (30%)
- Position Level (20%)
- Institution Type (10%)

---

## LLM Integration

### What the LLM Does

The LLM processing performs several tasks to extract structured information from job postings:

1. **Extract Job Details**: Reads full job description and extracts structured information
2. **Parse Deadlines**: Normalizes deadline text to standard date format (YYYY-MM-DD)
3. **Classify Position**: Analyzes job title and description to classify level and type
4. **Position Track Classification**: Assigns each posting to a track category
5. **Difficulty Estimation**: Scores application difficulty based on portfolio and job requirements
6. **Fit Evaluation**: Evaluates portfolio alignment with job requirements
7. **Joint Fit/Difficulty Prompt**: Consolidates matching calls into a single LLM evaluation per job

### LLM Prompts

#### 1. Extract Job Details (`extract_job_details`)

**System Prompt:**
```
You are an expert at parsing job postings. Extract structured information from job descriptions.
Return a JSON object with the following fields:
- position_type: Type of position (e.g., "Assistant Professor", "Postdoc", "Research Associate")
- field: Primary field of economics (e.g., "Public Economics", "Development Economics", "Microeconomics")
- level: Position level (e.g., "Assistant", "Associate", "Postdoc", "Senior")
- requirements: Key requirements and qualifications (as a string)
- research_areas: List of research areas mentioned
- teaching_load: Teaching requirements if mentioned
- location_preference: Geographic location preferences if mentioned
- extracted_deadline: Application deadline date extracted from the description text (in YYYY-MM-DD format, or null if not found)
- requires_separate_application: Boolean indicating if the job requires applying through a separate platform/portal (not just AEA JOE)
- application_portal_url: URL of the application portal/website if mentioned (e.g., "https://jobs.university.edu/apply"), or null if not found
```

**User Prompt:**
```
Extract structured information from this job posting:

{job_description}

Return only valid JSON with the fields specified.
```

#### 2. Parse Deadlines (`parse_deadlines`)

**System Prompt:**
```
Extract the deadline date from text. Return only the date in YYYY-MM-DD format, or null if no date found.
```

**User Prompt:**
```
Extract the deadline date from: {deadline_text}
Return only YYYY-MM-DD or null.
```

#### 3. Classify Position (`classify_position`)

**System Prompt:**
```
Classify the job position. Return JSON with:
- level: "Assistant", "Associate", "Full", "Postdoc", "Other"
- type: "Tenure-track", "Tenured", "Non-tenure", "Postdoc", "Other"
- field_focus: Primary field (e.g., "Public Economics", "Development Economics")
```

**User Prompt:**
```
Classify this position:

Title: {title}
Description: {description[:500]}

Return only valid JSON.
```

#### 4. Position Track (`evaluate_position_track_batch`)

**System Prompt:**
```
You are an expert academic career advisor. Review the job posting and assign it to one of the predefined categories. Use domain knowledge about economics job market roles. Respond ONLY with JSON in the following shape:
{
  "track_label": <one of: junior tenure-track, senior tenure-track, teaching, industry, non-tenure track, other academia>,
  "reasoning": <short explanation>
}
Junior tenure-track generally means assistant-level or early-career tenure-track positions. Senior tenure-track implies associate/full rank or leadership roles. Teaching refers to lecturer/instructor/teaching professor roles. Industry covers private-sector, consulting, or non-academic employers. Non-tenure track covers research associate, visiting, postdoc, adjunct, or contract academic positions. Other academia is a catch-all for remaining academic roles (e.g., research centers) not fitting the earlier buckets.
```

**User Prompt:**
```
Title: {title}
Institution: {institution}
Position Type: {position_type}
Field: {field}
Location: {location}
Status: {application_status}
Requirements:
{requirements}

Description:
{description}
```

#### 5. Joint Fit & Difficulty (`evaluate_fit_and_difficulty`)

**System Prompt:**
```
You are an experienced economics job-market advisor. Analyze the candidate profile and the job posting to assess BOTH fit and application difficulty. Return JSON with this schema only:
{
  "fit_score": <float 0-100>,
  "fit_reasoning": <string explanation (<= 200 words)>,
  "fit_alignment": {
    "research": <string>,
    "teaching": <string>,
    "other": <string>
  },
  "difficulty_score": <float 0-100>,
  "difficulty_reasoning": <string explanation (<= 120 words)>
}
Fit focuses on research/qualification alignment; difficulty reflects how challenging it is for the candidate to secure the role given institution selectivity and requirements.
```

**User Prompt:**
```
Evaluate the candidate's overall fit and application difficulty for this economics job.

== Candidate Summary ==
{portfolio_summary}

== Job Details ==
Title: {job_title}
Institution: {institution}
Position Type/Level: {position_type}
Location: {location}
Description:
{description}

Key Requirements:
{requirements}

Return only the JSON structure specified in the system prompt.
```

**Editing Prompts:**
- The active system/user prompts are stored in `config/prompts.json` (defaults ship in code).
- The web dashboard exposes a **Prompt Settings** page (`/prompts`) with side-by-side editors for updating both prompts without modifying source files.
- Progress feedback for long-running tasks is also surfaced via `/api/progress`, which feeds the floating dashboard widget.

### Concurrency & Rate Limiting

- All LLM helpers share a concurrent executor governed by `LLM_MAX_CONCURRENCY`
- Rate limiting via `LLM_MIN_CALL_INTERVAL` (minimum time between calls)
- Gracefully falls back to heuristic logic if API is unavailable
- Batch processing with incremental saves (20 jobs per batch)

---

## Database Schema

### Key Fields

**Scraped Fields:**
- `job_id`, `title`, `institution`, `description`, `deadline`, `location`, `contact_info`, `posted_date`

**LLM-Enriched Fields:**
- `position_type`, `field`, `level`, `requirements`, `extracted_deadline`, `application_portal_url`, `country`, `application_materials`, `references_separate_email`, `requires_separate_application`, `position_track`

**Matching Fields:**
- `fit_score`, `difficulty_score`, `difficulty_reasoning`, `fit_updated_at`, `fit_portfolio_hash`

**User-Managed Fields:**
- `application_status` (pending, new, applied, rejected, expired, unrelated)

**Metadata:**
- `last_updated` (timestamp of last database update)

### Field Update Rules

#### LLM Processing Updates

| Field | Update Rule |
|-------|-------------|
| `position_type` | Only if existing value is empty/None |
| `field` | Only if existing value is empty/None |
| `level` | Only if existing value is empty/None |
| `requirements` | Append if both exist, otherwise replace if empty |
| `extracted_deadline` | Update if meaningful value extracted |
| `application_portal_url` | Update if found and existing is empty |
| `country` | Update if extracted and existing is empty |
| `application_materials` | Append if both exist, otherwise replace if empty |
| `references_separate_email` | Update if boolean value extracted |
| `requires_separate_application` | Update if boolean value extracted |
| `position_track` | Always update (this is the primary LLM processing output) |

#### Matching Updates

| Field | Update Rule |
|-------|-------------|
| `fit_score` | Always update (calculated from portfolio) |
| `difficulty_score` | Always update (LLM estimation) |
| `difficulty_reasoning` | Always update (LLM reasoning) |
| `fit_updated_at` | Always update (timestamp) |
| `fit_portfolio_hash` | Always update (portfolio hash) |

#### Scraping Updates

| Field | Update Rule |
|-------|-------------|
| Raw fields (title, institution, etc.) | Always update from scraped data |
| `application_status` | Preserve if user-set (not 'new') |
| `fit_score` | Preserve if manually set |

---

## Configuration

### Settings File (`config/settings.py`)

```python
import os

# Database settings
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/job_listings.db")

# LLM settings
LLM_PROVIDER = "deepseek"  # or "anthropic", "openai"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "20"))
LLM_MIN_CALL_INTERVAL = float(os.getenv("LLM_MIN_CALL_INTERVAL", "1.0"))
LLM_PROCESSING_BATCH_SIZE = int(os.getenv("LLM_PROCESSING_BATCH_SIZE", "20"))

# Scraping settings
SCRAPE_INTERVAL_HOURS = 6
JOE_EXPORT_URL = "https://www.aeaweb.org/joe/resultset_xls_output.php?mode=xls_xml"

# Portfolio settings
PORTFOLIO_PATH = os.getenv("PORTFOLIO_PATH", "portfolio/")
```

### Environment Variables

- `DEEPSEEK_API_KEY`: DeepSeek API key
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `LLM_MAX_CONCURRENCY`: Maximum concurrent LLM calls (default: 20)
- `LLM_MIN_CALL_INTERVAL`: Minimum seconds between LLM calls (default: 1.0)
- `LLM_PROCESSING_BATCH_SIZE`: Jobs per batch (default: 20)

---

## Testing & Troubleshooting

### Common Issues

#### Fields showing as N/A after LLM processing
- **Cause**: LLM returned empty/None values
- **Fix**: Check LLM API status, verify job descriptions are complete
- **Prevention**: Fixed in code - empty values no longer overwrite existing data

#### Fit scores not updating
- **Cause**: Caching logic preventing recomputation
- **Fix**: Use `--force-match` or check "Force Recompute" checkbox
- **Check**: Verify `fit_portfolio_hash` matches current portfolio

#### Position track missing
- **Cause**: Job hasn't been processed with LLM yet
- **Fix**: Run `--process` to classify position tracks
- **Check**: Verify `needs_llm_processing()` returns True for job

#### Difficulty scores missing
- **Cause**: Matching hasn't been run or LLM failed
- **Fix**: Run `--match` to calculate difficulty scores
- **Note**: Difficulty requires both LLM processing (for position_track) and matching

### Error Handling

#### LLM Failures
- Individual job failures don't block others
- Failed jobs are logged but processing continues
- Heuristic fallbacks available for fit scores if LLM fails

#### Database Errors
- Uses WAL mode for concurrent access
- Inter-process locking prevents conflicts
- Transactions ensure atomicity
- Errors are logged with full context

#### Graceful Degradation
- Missing portfolio files: Matching still works with reduced accuracy
- LLM API failures: Falls back to heuristic scoring
- Network errors: Retries with exponential backoff

### Verification

**Check LLM Processing Progress:**
```bash
python3 scripts/check_llm_progress.py
```

**Test with Small Batches:**
```bash
python main.py --process --process-limit 10
```

**Force Full Recompute:**
```bash
python main.py --match --force-match
```

---

## Best Practices

1. **Run scraping first** to get latest data
2. **Let auto-processing handle small batches** (≤100 jobs)
3. **Manually process large batches** to control API usage
4. **Use force recompute** when portfolio changes
5. **Check logs** for processing errors
6. **Backup database** regularly (automatic backups on date boundaries)
7. **Export to CSV** for manual review and editing
8. **Import CSV changes** to update database

---

## Summary

The system is designed to be:
- **Incremental**: Saves progress continuously in batches
- **Resumable**: Can be interrupted and continued safely
- **Preservative**: Doesn't overwrite existing meaningful data
- **Efficient**: Only processes what's needed
- **Safe**: Uses locking and transactions for data integrity
- **Flexible**: Supports both CLI and web interfaces

