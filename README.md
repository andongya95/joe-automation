# AEA JOE Automation Tool

Automated tool for scraping, processing, and matching job postings from AEA JOE (American Economic Association Job Openings for Economists).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Automated Scraping**: Downloads job listings from AEA JOE XLS export
- **LLM Processing**: Extracts structured information using DeepSeek, OpenAI, or Anthropic
- **Portfolio Matching**: Calculates fit scores based on your qualifications
- **Track & Difficulty Insights**: Classifies each role type and estimates application difficulty using LLMs
- **Database Management**: SQLite database for local storage and querying
- **Web Dashboard**: Interactive web interface for visualization and management
- **CSV Export/Import**: Export data for editing, then import changes back
- **Portfolio Management**: Upload and manage CV, research statement, teaching statement
- **Automatic Backups**: Daily database backups when operations cross date boundaries

## Installation

1. Clone the repository:
```bash
git clone https://github.com/andongya95/joe-automation.git
cd joe-automation
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure settings:
```bash
# Copy example settings file
cp config/settings.example.py config/settings.py

# Edit config/settings.py and add your API keys
# Or set environment variables:
export DEEPSEEK_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"
```

4. Create necessary directories:
```bash
mkdir -p data/exports data/backups portfolio
```

## Quick Start

### Command Line

```bash
# Scrape and save new job listings
python main.py --update

# Process jobs with LLM (extracts structured info)
python main.py --process

# Calculate fit scores
python main.py --match        # incremental
python main.py --match --force-match   # full recompute

# Export to CSV
python main.py --export

# Import changes from CSV
python main.py --import-csv data/exports/job_matches.csv

# Start web server
python main.py --web
```

> ℹ️ When you scrape via CLI or the dashboard, the app automatically runs LLM parsing if ≤100 new postings were retrieved. For larger batches you’ll be prompted (web) or warned (CLI) to trigger `--process` manually so you stay within rate limits.

### Batch Files (Windows)

Windows batch files are provided in the `scripts/` directory for easy startup:
- `scripts/start_web.bat` - Start web server (default port 5000)
- `scripts/start_web_port.bat [PORT]` - Start web server on custom port
- `scripts/scrape_jobs.bat` - Scrape and update job listings
- `scripts/process_jobs.bat [LIMIT]` - Process jobs with LLM (optional limit)
- `scripts/match_jobs.bat` - Calculate fit scores
- `scripts/export_csv.bat [FILENAME]` - Export to CSV (optional filename)

Simply double-click any batch file to run the corresponding command.

### Shell Scripts (macOS / Linux)

Shell scripts are provided for Unix-like environments:

- `scripts/start_web.sh` - Start the web server (default port 5000)
- `scripts/start_web_port.sh [PORT]` - Start the web server on a custom port

From the project root:

```bash
# Ensure scripts are executable (first time only)
chmod +x scripts/*.sh

# Start the dashboard on macOS/Linux
bash ./scripts/start_web.sh

# Specify a custom port
bash ./scripts/start_web_port.sh 8000
```

The script automatically uses the Python interpreter on your `$PATH` (override with `PYTHON_BIN=/path/to/python bash ./scripts/start_web.sh`).

## Command-Line Options

- `--update`: Scrape and download latest job listings
- `--process`: Process jobs with LLM incrementally (processes in batches, saves after each batch)
- `--process-limit N`: Limit number of jobs to process (default: all)
- `--match`: Calculate fit & difficulty scores sequentially per job (saves after each job, skips already-scored entries unless `--force-match`)
- `--export`: Export results to CSV file
- `--import-csv PATH`: Import changes from CSV file and update database
- `--web`: Start web server for database visualization
- `--port N`: Port for web server (default: 5000)
- `--verbose`: Enable detailed logging
- `--output PATH`: Specify output CSV file path (default: `data/exports/job_matches.csv`)

### Workflow

1. **Scrape & Save**: Download latest job postings and save raw data to database (`--update`)
2. **Process with LLM**: Extract structured information in batches, saving after each batch (`--process`)
3. **Match**: Run the joint fit/difficulty prompt job-by-job, saving after each update and only recomputing if either score is missing (or when forced) (`--match`)
4. **Export**: Export to CSV for visualization and editing (`--export`)
5. **Import**: Import changes from CSV back to database (`--import-csv`)
6. **Web Interface**: Use web dashboard for interactive management (`--web`)

## Project Structure

```
.
├── config/              # Configuration settings
│   ├── settings.py      # Your configuration (not in repo)
│   └── settings.example.py  # Example configuration
├── data/               # Database and data files
│   ├── exports/        # CSV export files
│   └── backups/        # Database backups
├── database/           # Database operations
├── docs/               # Documentation files
├── matcher/            # Portfolio matching logic
├── portfolio/          # Portfolio files (CV, statements)
├── processor/           # LLM processing
├── scraper/            # Web scraping
├── scripts/            # Batch files for Windows
├── webapp/             # Web interface
│   ├── static/         # CSS and JavaScript
│   └── templates/      # HTML templates
├── main.py             # Main entry point
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Web Interface

The web interface provides an interactive dashboard for visualizing and managing job postings:

**Main Dashboard Features:**
- **Statistics Dashboard**: View total jobs, counts by status, average fit score
- **Scrape New Jobs**: Click "Scrape New Jobs" button to download latest listings from AEA JOE
- **Process with LLM**: Click "Process with LLM" button to extract structured information from job descriptions (processes in batches, saves progress)
- **Match Fit Scores**: Click "Match Fit Scores" button to run the joint fit/difficulty prompt per job (sequential saves, skips already-scored jobs unless "Force" is enabled)
- **Background Tasks Panel**: A floating card on the right tracks real-time progress for long-running tasks (LLM processing, matching) and stays visible as you scroll without covering the table.
- **Prompt Settings**: Manage system & user prompts from the **Prompt Settings** page (accessible via the dashboard header) without touching source code
- **Filtering**: Filter by status, field, level, minimum fit score
- **Search**: Text search across titles, institutions, and descriptions
- **Sorting**: Click column headers to sort by fit score, deadline, institution, etc.
- **Job Details**: Click "View" to see full job description and requirements
- **Status Updates**: Click "Status" to cycle through application statuses (pending → new → applied → expired → rejected)
- **Force Recompute Toggle**: Use "Force full recompute" next to "Match Fit Scores" when you need to refresh every job (default only updates changed postings)
- **Edit Jobs**: Click "Edit" to modify job information inline, then "Save Changes" to update database
- **AEA JOE Links**: Direct links to view original job postings on AEA JOE website
- **Responsive Design**: Works on desktop and mobile devices

**Portfolio Management Page:**
- **File Status**: View which portfolio files are present (CV, research statement, teaching statement)
- **Upload Files**: Upload new portfolio documents (PDF, DOC, DOCX, TXT formats)
- **View Files**: View uploaded portfolio files in browser
- **Delete Files**: Remove portfolio files
- **Text Extraction Status**: See how much text has been extracted from portfolio files

**Usage:**
```bash
# Start web server
python main.py --web

# Access at http://127.0.0.1:5000
```

The web interface runs locally and connects directly to your SQLite database. All changes made through the web interface are saved immediately to the database.

**Note:** The system handles missing portfolio files gracefully - matching will still work but with reduced accuracy if portfolio files are not available.

## CSV Workflow

The CSV file serves as both a visualization tool and an editing interface:

1. **Export**: `python main.py --export` creates `data/exports/job_matches.csv` with all job data
2. **Edit**: Open the CSV in Excel/Google Sheets, make changes (e.g., mark jobs as "applied", adjust fit scores)
3. **Import**: `python main.py --import-csv data/exports/job_matches.csv` updates the database with your changes

The CSV includes key fields: `job_id`, `title`, `institution`, `position_type`, `field`, `level`, `deadline`, `location`, `fit_score`, `application_status`, `posted_date`

## Database Backups

The system automatically creates database backups when operations cross date boundaries:
- Backups are stored in `data/backups/` directory
- Backup files are named with timestamps: `job_listings_YYYYMMDD_HHMMSS.db`
- Only one backup per day is created (when crossing to a new day)
- Manual backups can be created via the web interface

## Documentation

Additional documentation is available in the `docs/` directory:
- `docs/DEVELOPMENT.md` - Complete development documentation (architecture, components, LLM integration, troubleshooting)
- `docs/CHANGELOG.md` - Change log and version history

## Security Note

⚠️ **Important**: Never commit your `config/settings.py` file with API keys. Use environment variables or keep it in `.gitignore`. The repository includes `config/settings.example.py` as a template.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**Andong Yan**
- GitHub: [@andongya95](https://github.com/andongya95)

## Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/andongya95/joe-automation/issues).

## Acknowledgments

- AEA JOE for providing job listing data
- DeepSeek, OpenAI, and Anthropic for LLM APIs
