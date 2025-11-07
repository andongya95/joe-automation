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

