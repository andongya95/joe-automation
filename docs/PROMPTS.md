# LLM Prompts Used in AEA JOE Automation Tool

## 1. Extract Job Details (`extract_job_details`)

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

## 2. Parse Deadlines (`parse_deadlines`)

**System Prompt:**
```
Extract the deadline date from text. Return only the date in YYYY-MM-DD format, or null if no date found.
```

**User Prompt:**
```
Extract the deadline date from: {deadline_text}
Return only YYYY-MM-DD or null.
```

## 3. Classify Position (`classify_position`)

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

