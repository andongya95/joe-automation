# AEA JOE Automation Tool - Complete Workflow Guide

## Overview

This tool automates the process of scraping, processing, and matching job postings from AEA JOE. The workflow is designed to be incremental and resumable.

## Complete Workflow

### Step 1: Scrape and Save Raw Data

```bash
python main.py --update
```

This will:
- Download latest job listings from AEA JOE
- Parse the XLS/XML data
- Save all raw job data to SQLite database
- Mark expired jobs automatically

**Result**: Database contains all scraped jobs with raw data (no LLM processing yet)

### Step 2: Process with LLM (Incremental)

```bash
# Process all unprocessed jobs
python main.py --process

# Or process in batches (e.g., first 10 jobs for testing)
python main.py --process --process-limit 10
```

This will:
- Load jobs from database that haven't been processed yet
- Process each job one by one with LLM API calls
- **Save immediately after each job** (incremental saving)
- Extract: position_type, field, level, requirements, research_areas, etc.

**Result**: Database updated with LLM-extracted structured information

**Note**: This step can be interrupted and resumed - it only processes jobs that haven't been processed yet.

### Step 3: Calculate Fit Scores

```bash
python main.py --match
```

This will:
- Load portfolio materials (CV, research statement, etc.)
- Calculate fit scores for each job based on:
  - Research Alignment (40%)
  - Qualification Match (30%)
  - Position Level (20%)
  - Institution Type (10%)
- Update fit scores in database

**Result**: All jobs have fit scores calculated

### Step 4: Export to CSV

```bash
python main.py --export
# Or specify custom output file
python main.py --export --output my_jobs.csv
```

This will:
- Export all jobs to CSV file
- Include all fields: job_id, title, institution, position_type, field, level, deadline, location, fit_score, application_status, posted_date, last_updated, description, requirements, contact_info
- Sort by fit_score (highest first)

**Result**: `data/exports/job_matches.csv` file ready for visualization and editing

### Step 5: Edit CSV (Manual)

1. Open `data/exports/job_matches.csv` in Excel, Google Sheets, or any spreadsheet editor
2. Make changes:
   - Update `application_status` (e.g., "new" → "applied", "rejected", "accepted")
   - Adjust `fit_score` if needed
   - Add notes or other custom fields
3. Save the CSV file

### Step 6: Import Changes from CSV

```bash
python main.py --import-csv data/exports/job_matches.csv
```

This will:
- Read the CSV file
- For each row, update the corresponding job in database
- Only update fields that have values (empty cells are ignored)
- Validate job_id exists before updating

**Result**: Database updated with your manual changes

## Example Complete Session

```bash
# 1. Scrape latest jobs
python main.py --update

# 2. Process first 5 jobs to test
python main.py --process --process-limit 5

# 3. If successful, process all remaining jobs
python main.py --process

# 4. Calculate fit scores
python main.py --match

# 5. Export to CSV
python main.py --export

# 6. (Edit CSV manually in Excel/Sheets)

# 7. Import changes back
python main.py --import-csv data/exports/job_matches.csv
```

## Key Features

### Incremental Processing
- LLM processing saves after each job
- Can be interrupted and resumed
- Only processes unprocessed jobs

### CSV as Interface
- Export for visualization
- Edit manually
- Import changes back to database

### Error Handling
- Failed jobs don't block others
- Detailed logging with timestamps
- Graceful degradation

## LLM Prompts

See `PROMPTS.md` for details on the prompts used for:
- Extracting job details
- Parsing deadlines
- Classifying positions

## Database Schema

The database stores:
- Raw scraped data (title, institution, description, etc.)
- LLM-extracted fields (position_type, field, level, requirements, etc.)
- Calculated fit scores
- Application status tracking
- Timestamps for tracking updates

## Tips

1. **Test with small batches**: Use `--process-limit 10` to test LLM processing before processing all jobs
2. **Monitor API usage**: LLM processing makes API calls - monitor your usage
3. **Backup database**: The SQLite database is in `data/job_listings.db` - back it up regularly
4. **CSV editing**: Keep `job_id` column intact - it's used to match rows to database entries
5. **Resume processing**: If interrupted, just run `--process` again - it will continue from where it left off

