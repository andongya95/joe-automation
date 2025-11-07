# What the LLM Does

The LLM (Large Language Model) processing in this tool performs three main tasks to extract structured information from job postings:

## 1. Extract Job Details (`extract_job_details`)

**What it does:**
- Reads the full job description text
- Extracts structured information using natural language understanding
- Returns a JSON object with key fields

**What it extracts:**
- `position_type`: Type of position (e.g., "Assistant Professor", "Postdoc", "Research Associate")
- `field`: Primary field of economics (e.g., "Public Economics", "Development Economics", "Microeconomics")
- `level`: Position level (e.g., "Assistant", "Associate", "Postdoc", "Senior")
- `requirements`: Key requirements and qualifications (as a string)
- `research_areas`: List of research areas mentioned
- `teaching_load`: Teaching requirements if mentioned
- `location_preference`: Geographic location preferences if mentioned

**Why it's needed:**
- Job descriptions are unstructured text
- The LLM intelligently identifies and extracts key information
- This makes the data searchable and filterable in the database

## 2. Parse Deadlines (`parse_deadlines`)

**What it does:**
- Takes deadline text (which can be in various formats)
- Normalizes it to a standard date format (YYYY-MM-DD)
- Handles complex deadline descriptions

**Examples of what it handles:**
- "December 15, 2024"
- "12/15/2024"
- "Applications accepted until filled"
- "Deadline extended to January 1, 2025"

**Why it's needed:**
- Deadlines come in many different formats
- The LLM understands natural language date descriptions
- Standardizes dates for easy sorting and filtering

## 3. Classify Position (`classify_position`)

**What it does:**
- Analyzes the job title and description
- Classifies the position level and type
- Identifies the primary field focus

**What it classifies:**
- `level`: "Assistant", "Associate", "Full", "Postdoc", "Other"
- `type`: "Tenure-track", "Tenured", "Non-tenure", "Postdoc", "Other"
- `field_focus`: Primary field (e.g., "Public Economics", "Development Economics")

**Why it's needed:**
- Helps filter jobs by career stage
- Identifies tenure-track vs non-tenure positions
- Categorizes by field for better matching

## How It Works

1. **When you click "Process with LLM":**
   - The system finds all jobs that haven't been processed yet (missing `position_type` or `field`)
   - For each job, it sends the job description to the LLM API (DeepSeek, OpenAI, or Anthropic)
   - The LLM analyzes the text and returns structured JSON data
   - The system saves the extracted information to the database immediately

2. **Incremental Processing:**
   - Jobs are processed one by one
   - Results are saved after each job (so you don't lose progress if something fails)
   - Rate limiting prevents API overload

3. **Error Handling:**
   - If an LLM call fails, it logs the error and continues with the next job
   - Invalid responses are skipped
   - The system continues processing even if some jobs fail

## Benefits

- **Automation**: No manual data entry needed
- **Accuracy**: LLM understands context and meaning
- **Consistency**: Standardized data format across all jobs
- **Speed**: Processes many jobs quickly
- **Flexibility**: Handles various text formats and styles

## Cost Considerations

- Each job requires 2-3 LLM API calls (extract details, parse deadline, classify)
- Costs depend on your LLM provider:
  - DeepSeek: Very affordable
  - OpenAI: Moderate cost
  - Anthropic: Higher cost but high quality
- Processing is incremental, so you can stop and resume anytime

