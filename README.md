# AI-Powered News Agent

This project is an automated AI Agent that collects, filters, categorizes, and analyzes market news to generate a "Daily Market Intelligence" report.

## Pipeline Overview

The pipeline consists of 6 phases, executed sequentially:

1. **Phase 1 (Collection)**: collects news from RSS feeds, Naver Finance, Google News, and other sources.
    - Script: `run_p1.py`
    - Output: `data/news.db` (raw_news table), Google Sheet (Raw News)
2. **Phase 2 (Deduplication)**: Removes duplicate articles based on similarity hashing.
    - Script: `run_p2.py`
    - Output: `data/news.db` (processed_news table)
3. **Phase 3 (Filtering)**: Filters news based on keywords (e.g., Real Estate, Tech) and relevance.
    - Script: `run_p3.py`
4. **Phase 4 (Classification)**: Uses LLM (Gemini 2.5 Flash) to classify news relevance (High/Low) and assign categories.
    - Script: `run_p4.py`
    - Output: Updated database with LLM decisions.
5. **Phase 5 (Clustering)**: Groups related news into Topics.
    - Script: `run_p5.py`
    - Output: `data/topics.db`, Google Sheet (Topics)
6. **Phase 6 (Reporting)**: Generates a comprehensive markdown report.
    - Script: `run_p6.py`
    - Output: `outputs/reports/YYYY-MM-DD_Daily_Report.md`

## Setup & installation

1. **Clone the repository**
2. **Install dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

    *(Note: Create a requirements.txt if not exists)*
3. **Configure Environment**:
    - Copy `.env.example` to `.env` (if provided) or create a new `.env`.
    - Required variables:
        - `OPENAI_API_KEY`, `GOOGLE_API_KEY`
        - `GOOGLE_SHEET_ID`
        - `GOOGLE_SERVICE_ACCOUNT_PATH` (path to json key)

## Daily Automation

To run the full pipeline manually:

```bash
python daily_runner.py
```

### Option A: GitHub Actions (Recommended)

You can run this pipeline entirely for free on GitHub without a dedicated server.

1. **Push the code** to a GitHub repository.
2. **Go to Settings > Secrets and variables > Actions**.
3. Add the following **Repository secrets**:
    - `GOOGLE_API_KEY`: Your Gemini API Key
    - `OPENAI_API_KEY`: Your OpenAI API Key
    - `GOOGLE_SHEET_ID`: The ID of your Google Sheet
4. The workflow is configured in `.github/workflows/daily_news.yml` to run daily at **7:00 AM KST** (22:00 UTC).
5. You can also trigger it manually from the **Actions** tab.

### Option B: Windows Task Scheduler (Local)

To schedule on your local Windows PC:

1. Open **Task Scheduler**.
2. Create a new Basic Task.
3. Set trigger to **Daily** (e.g., 7:00 AM).
4. Action: **Start a program**.
5. Program/Script: Select `daily_run.bat` in the project folder.
6. Start in: Set to the project folder path (e.g., `d:\Dev\Developing\News_Agent`).

## Project Structure

- `src/`: Core logic (collectors, processors, utils).
- `config/`: Configuration settings and prompts.
- `storage/`: Database adapters.
- `data/`: SQLite databases (ignored by git).
- `outputs/`: Generated reports (ignored by git).
- `logs/`: Application logs (ignored by git).
