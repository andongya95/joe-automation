# Chat Session Summary - November 8, 2025

## Update - Enhanced LLM Processing, UI Improvements, and Concurrent Matching

### Highlights
- Position track normalization for ambiguous titles (defaults to junior tenure-track/assistant level)
- Level extraction now shows all levels from job titles (comma-separated)
- Status button replaced with dropdown menu for direct status selection
- Selected jobs operations: Process Selected and Match Selected with force options
- Added listing ID column to job table
- Concurrent matching with incremental saves (up to 20 parallel LLM calls)
- Clarified difficulty score interpretation in prompts (lower = harder)

### Files Touched
- `matcher/job_assessor.py` - Position track normalization
- `processor/llm_parser.py` - Level extraction enhancement
- `matcher/llm_fit_evaluator.py` - Concurrent batch evaluation
- `main.py` - Concurrent matching, position track normalization, level handling
- `webapp/app.py` - Concurrent matching, selected jobs API, position track normalization
- `webapp/templates/index.html` - Status dropdown, selected jobs buttons, ID column
- `webapp/static/js/main.js` - Status dropdown handler, selected jobs operations
- `webapp/static/css/style.css` - Status dropdown styling
- `config/prompts.json` - Difficulty score clarification
- `config/prompt_loader.py` - Difficulty score clarification
- `matcher/__init__.py` - Export new batch function

### Key Changes

#### 1. Position Track Normalization
**Problem**: Ambiguous titles like "faculty position" without specific rank (assistant/associate/full) led to unclear position track classification.

**Solution**:
- Added `_normalize_position_track_for_ambiguous_title()` function
- Detects ambiguous titles (contains "faculty position", "professor" without rank)
- Defaults to "junior tenure-track" (assistant level) when LLM returns "senior tenure-track" for ambiguous titles
- Applied in both CLI and web processing flows

**Files Changed**:
- `matcher/job_assessor.py` - Normalization function
- `main.py` - Apply normalization after position track evaluation
- `webapp/app.py` - Apply normalization after position track evaluation

#### 2. Level Extraction Enhancement
**Problem**: Level field only showed single value, but postings may list multiple ranks (e.g., "Assistant or Associate Professor").

**Solution**:
- Updated LLM prompts to request ALL levels found in title
- Modified extraction to return comma-separated levels when multiple exist
- Updated processing logic to handle list/array levels and convert to comma-separated strings

**Files Changed**:
- `processor/llm_parser.py` - Updated prompts and extraction logic
- `main.py` - Level handling for multiple values
- `webapp/app.py` - Level handling for multiple values

#### 3. Status Dropdown Menu
**Problem**: Status button cycled through statuses on click, making it hard to jump to specific status.

**Solution**:
- Replaced status button with `<select>` dropdown menu
- Shows all available statuses: pending, new, applied, expired, rejected, unrelated
- Updates immediately on change (no confirmation needed)
- Added CSS styling for dropdown

**Files Changed**:
- `webapp/templates/index.html` - Status dropdown HTML
- `webapp/static/js/main.js` - Dropdown change handler
- `webapp/static/css/style.css` - Dropdown styling

#### 4. Selected Jobs Operations
**Problem**: No way to process/match only selected jobs with force options.

**Solution**:
- Added "Process Selected" and "Match Selected" buttons in bulk actions
- Added force toggles for both operations
- Modified API endpoints to accept `job_ids` array and `force` flag
- When `job_ids` provided, filters jobs to only those IDs before processing/matching

**Files Changed**:
- `webapp/app.py` - API endpoints accept job_ids and force
- `webapp/templates/index.html` - Bulk action buttons
- `webapp/static/js/main.js` - Selected jobs processing functions

#### 5. Listing ID Column
**Added**: New "ID" column showing job listing ID for easy reference.

**Files Changed**:
- `webapp/templates/index.html` - ID column header
- `webapp/static/js/main.js` - ID column rendering

#### 6. Concurrent Matching with Incremental Saves
**Problem**: Matching processed jobs sequentially, not utilizing full LLM concurrency.

**Solution**:
- Refactored matching to use concurrent processing (up to `LLM_MAX_CONCURRENCY` parallel calls)
- Uses `as_completed()` to process results as they finish
- Saves each job immediately when its LLM call completes (incremental saves)
- Maintains resumability while maximizing throughput

**How It Works**:
1. Submit all jobs in batch concurrently (up to 20 parallel LLM calls)
2. As each call completes → save that job immediately to database
3. Log progress: "Saved match results for Job X [5/20]"
4. If interrupted: All completed jobs are already saved

**Files Changed**:
- `matcher/llm_fit_evaluator.py` - Added `evaluate_fit_and_difficulty_batch()`
- `main.py` - Concurrent matching in `_match_job_batch()`
- `webapp/app.py` - Concurrent matching in `_match_job_batch_web()`

#### 7. Difficulty Score Prompt Clarification
**Problem**: Difficulty score interpretation was ambiguous - unclear if lower scores meant harder or easier.

**Solution**:
- Added explicit clarification: "Lower scores mean HIGHER difficulty (harder to get)"
- Added specific benchmarks:
  - Top 30 US universities: difficulty_score < 5 (very difficult, ~5% chance)
  - Top 5 China universities: difficulty_score around 10 (difficult, ~10% chance)
  - Mid-tier R1: 15-30 (moderately difficult)
  - Regional/less selective: 30-60 (moderate difficulty)
  - Non-tenure/teaching: 50-80 (moderate to easier)
  - Senior tenure-track: near 0 (extremely difficult for early-career)

**Files Changed**:
- `config/prompts.json` - Updated system prompt
- `config/prompt_loader.py` - Updated default prompts

## Impact

### Before:
- Ambiguous titles could get incorrect position track classification
- Level field only showed single value
- Status changes required cycling through all options
- No way to process/match selected jobs
- Matching processed sequentially (slow)
- Difficulty score interpretation unclear

### After:
- Ambiguous titles default to junior tenure-track (assistant level)
- Level field shows all levels found (comma-separated)
- Status dropdown allows direct selection
- Selected jobs can be processed/matched with force options
- Matching uses concurrent processing (up to 20x faster)
- Difficulty scores clearly interpreted (lower = harder)
- Incremental saves maintained even with concurrency

## Configuration

No new configuration needed. Uses existing:
- `LLM_MAX_CONCURRENCY`: Maximum concurrent LLM calls (default: 20)
- `LLM_PROCESSING_BATCH_SIZE`: Jobs per batch (default: 20)

## Testing

To test concurrent matching:
1. Select multiple jobs in web interface
2. Click "Match Selected" with force toggle
3. Watch logs - should see concurrent processing and incremental saves
4. Interrupt mid-process - completed jobs should be saved

## Files Modified

### Core Logic:
- `matcher/job_assessor.py` - Position track normalization
- `matcher/llm_fit_evaluator.py` - Concurrent batch evaluation
- `processor/llm_parser.py` - Level extraction enhancement
- `main.py` - Concurrent matching, normalization, level handling
- `webapp/app.py` - Concurrent matching, selected jobs API, normalization

### UI:
- `webapp/templates/index.html` - Status dropdown, selected jobs buttons, ID column
- `webapp/static/js/main.js` - Dropdown handler, selected jobs operations
- `webapp/static/css/style.css` - Dropdown styling

### Configuration:
- `config/prompts.json` - Difficulty score clarification
- `config/prompt_loader.py` - Difficulty score clarification

---

# Chat Session Summary - November 7, 2025

## Update - Joint Fit/Difficulty Prompt

### Highlights
- Replaced the dual fit/difficulty flows with a single joint LLM prompt that returns both scores in one call.
- Matching now evaluates jobs sequentially inside each batch and saves after every job, skipping entries that already have both scores unless forced.
- Updated `needs_fit_recompute` so existing scored jobs are bypassed unless one of the scores is missing or force mode is enabled.
- Aligned README, development docs, and local context with the new workflow.

### Files Touched
- `database/job_db.py`
- `main.py`
- `webapp/app.py`
- `matcher/fit_calculator.py`
- `matcher/llm_fit_evaluator.py`
- `matcher/__init__.py`
- `tests/test_matching_flow.py`
- `README.md`
- `docs/DEVELOPMENT.md`
- `.cursor/context.md`
- `tests/test_progress.py`

### Tests
- `python3 -m unittest tests.test_matching_flow tests.test_progress`

## Overview
This session focused on fixing critical bugs, consolidating checking logic, and implementing batch processing with incremental saves to ensure partial progress is preserved.

## Key Changes Made

### 1. Field Preservation Fix
**Problem**: LLM processing was overwriting existing fields with N/A/empty values when LLM returned empty results.

**Solution**:
- Added `has_meaningful_value()` helper function to check if values are meaningful
- Modified LLM processing to only update fields that are currently empty/None
- For `requirements` and `application_materials`: Append if both exist, otherwise replace only if empty
- For `field`, `level`, `position_type`: Only update if existing value is missing
- Never overwrite with empty/None values

**Files Changed**:
- `main.py` - `process_jobs_incrementally()` function
- `webapp/app.py` - `api_process_jobs()` function

### 2. Consolidated Checking Logic
**Problem**: Duplicate checking logic in `main.py` and `webapp/app.py` with inconsistencies.

**Solution**:
- Created unified `needs_llm_processing()` function in `database/job_db.py`
- Created unified `needs_fit_recompute()` function in `database/job_db.py`
- Both functions exported from `database/__init__.py`
- Updated both `main.py` and `webapp/app.py` to use unified functions
- Fixed `pending_llm` calculation to use unified function

**Logic**:
- **LLM Processing**: Job needs processing if ANY of these fields are empty:
  - `extracted_deadline`, `application_portal_url`, `country`, `application_materials`
  - `requires_separate_application`, `references_separate_email` (None only, False is valid)
  - `position_track`
- **Fit Recompute**: Job needs recomputation if:
  - `fit_score` is None
  - `position_track` is missing (needs LLM processing first)
  - `difficulty_score` is None
  - `fit_portfolio_hash` doesn't match current portfolio hash
  - `fit_updated_at` is missing
  - Job was updated after last fit calculation

**Files Changed**:
- `database/job_db.py` - Added unified checking functions
- `database/__init__.py` - Exported new functions
- `main.py` - Updated to use unified functions
- `webapp/app.py` - Updated to use unified functions

### 3. Batch Processing with Incremental Saves
**Problem**: LLM processing and match score calculation waited for ALL batch calls to complete before saving. If interrupted, completed work was lost.

**Solution**:
- Added `LLM_PROCESSING_BATCH_SIZE` configuration (default: 20 jobs per batch)
- Refactored LLM processing to process in batches, saving after each batch
- Refactored match score calculation to process in batches, saving after each batch
- Created helper functions: `_process_job_batch()`, `_match_job_batch()`, `_process_job_batch_web()`, `_match_job_batch_web()`

**How It Works**:
1. Jobs split into batches of 20 (configurable)
2. For each batch:
   - Run LLM calls for that batch
   - Process results and save immediately
   - Log progress: "Batch X/Y complete: N saved"
3. If interrupted: Completed batches are already saved
4. Resume: Automatically skips already-processed jobs

**Files Changed**:
- `config/settings.py` - Added `LLM_PROCESSING_BATCH_SIZE`
- `main.py` - Refactored `process_jobs_incrementally()` and `match_jobs()`
- `webapp/app.py` - Refactored `api_process_jobs()` and `api_match_jobs()`

### 4. Match Function Fix
**Problem**: Match function was updating `position_track`, which should only be set during LLM processing.

**Solution**:
- Removed `position_track` from match update payloads
- Match now only updates: `fit_score`, `difficulty_score`, `difficulty_reasoning`, `fit_updated_at`, `fit_portfolio_hash`

**Files Changed**:
- `main.py` - `match_jobs()` function
- `webapp/app.py` - `api_match_jobs()` function

### 5. Auto-Processing Enhancement
**Problem**: After scraping, only LLM processing ran automatically, not matching.

**Solution**:
- Updated auto-processing logic to also run matching after LLM processing completes
- Web interface: Prompts user for matching if >100 jobs, auto-runs if ≤100
- CLI: Auto-runs both processing and matching if ≤100 new jobs

**Files Changed**:
- `main.py` - Auto-processing after scrape
- `webapp/app.py` - Auto-processing after scrape
- `webapp/static/js/main.js` - Auto-processing logic

### 6. UI Improvements
- Fixed "Match Fit Scores" button styling to match other buttons
- Added "Force Recompute" checkbox for match scores
- Added processing state animations

**Files Changed**:
- `webapp/static/css/style.css` - Button styling
- `webapp/static/js/main.js` - Button states and force toggle
- `webapp/templates/index.html` - UI elements

### 7. Verification Script
Created `scripts/check_llm_progress.py` to verify partial progress is saved.

## Testing & Verification

### How to Verify Batch Processing Works:
1. Click "Process with LLM" on web interface
2. Wait for 1-2 batches to complete (watch logs)
3. Stop the server (Ctrl+C) or close browser
4. Run: `python3 scripts/check_llm_progress.py`
5. Should show processed count > 0
6. Restart and click "Process with LLM" again
7. Should continue from where it left off

## Configuration

New environment variable:
- `LLM_PROCESSING_BATCH_SIZE`: Number of jobs to process per batch (default: 20)

## Files Modified

### Core Logic:
- `main.py` - Batch processing, unified checks, field preservation
- `webapp/app.py` - Batch processing, unified checks, field preservation
- `database/job_db.py` - Unified checking functions
- `database/__init__.py` - Export new functions
- `config/settings.py` - Batch size configuration

### UI:
- `webapp/static/css/style.css` - Button styling
- `webapp/static/js/main.js` - Auto-processing, button states
- `webapp/templates/index.html` - UI elements

### Scripts:
- `scripts/check_llm_progress.py` - Progress verification script (new)

## Impact

### Before:
- Fields could be overwritten with N/A values
- Duplicate checking logic with inconsistencies
- No partial progress saving (all-or-nothing)
- Match function incorrectly updated position_track

### After:
- Fields preserved unless meaningful new values available
- Single source of truth for checking logic
- Partial progress saved after each batch (20 jobs)
- Clear separation: LLM processing sets position_track, matching sets fit/difficulty
- Resumable processing - can interrupt and continue safely

## Next Steps

1. Test batch processing with real data
2. Monitor API usage with batch size of 20
3. Adjust `LLM_PROCESSING_BATCH_SIZE` if needed based on performance
4. Consider adding progress indicators in web UI

## New Feature - Progress Panel & Prompt Editor

### Highlights
- Added a floating dashboard panel that displays real-time progress for LLM processing and matching, backed by the new `/api/progress` endpoint.
- Introduced prompt persistence via `config/prompts.json` and a **Prompt Settings** web page that allows editing system/user prompts without code changes.
- Updated UI components (templates, CSS, JS) to support the panel, prompt editor, and difficulty display tweaks.

### Files Touched
- `webapp/app.py`
- `webapp/templates/index.html`
- `webapp/templates/prompts.html`
- `webapp/static/js/main.js`
- `webapp/static/css/style.css`
- `config/prompt_loader.py`
- `config/prompts.json`
- `README.md`
- `docs/DEVELOPMENT.md`
- `tests/test_progress.py`

### Tests
- `python3 -m unittest tests.test_matching_flow tests.test_progress`

