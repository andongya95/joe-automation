"""Example configuration file. Copy this to settings.py and fill in your values."""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database configuration
DATABASE_PATH = str(BASE_DIR / "data" / "job_listings.db")

# Portfolio path
PORTFOLIO_PATH = str(BASE_DIR / "portfolio")

# LLM Provider: 'deepseek', 'openai', or 'anthropic'
LLM_PROVIDER = 'deepseek'

# API Keys (set via environment variables or update here)
# For security, use environment variables:
# export DEEPSEEK_API_KEY="your-key-here"
# export OPENAI_API_KEY="your-key-here"
# export ANTHROPIC_API_KEY="your-key-here"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# AEA JOE scraping URL
AEA_JOE_URL = "https://www.aeaweb.org/joe/listings/xls"

# Research focal areas for matching
RESEARCH_FOCAL_AREAS = [
    "Labor Economics",
    "Development Economics",
    "Applied Microeconomics",
    # Add your research areas here
]

# Verbose logging
VERBOSE = False

