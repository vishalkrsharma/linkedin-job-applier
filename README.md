# LinkedIn Auto Apply Bot 🚀

An automation tool that takes control of your Chrome browser and automatically applies to LinkedIn jobs using the **Easy Apply** feature.

## Features

- 🔐 **Secure Login** — Logs into LinkedIn with your credentials (supports manual 2FA) or uses an existing persistent browser profile.
- 🔍 **Smart Job Search** — Searches for jobs based on your configured list of keywords, locations, and filters. Evaluates crossing all keywords with all target locations.
- 📝 **Auto Form Fill** — Automatically fills out Easy Apply forms (text fields, dropdowns, radio buttons, etc) using regular expression mappings from your configuration.
- 📄 **Resume Strategy** — Optionally upload a local resume PDF or default to using LinkedIn's latest pre-saved resume to save time and prevent repetitive uploads.
- 📊 **Application Tracking** — Eliminates duplicates by continually tracking applied jobs in `applied_jobs.json`. Failures and form blockades are saved safely to `failed_jobs.json` to analyze roadblocks. Provides clean terminal reporting at the end of runs for today's activity.
- ⏱️ **Human-like Behavior** — Randomized delays to mimic human interaction and avoid detection heuristics.
- 🛡️ **Error Recovery** — Gracefully handles errors and skips problematic elements without crashing the bot loop.
- ⚙️ **Configurable** — Fully configurable via `config.yaml`.

## Setup

### 1. Install Dependencies

```bash
cd /home/vishal/projects/personal/job
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

Copy the example config and edit it with your details:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your:

- LinkedIn credentials
- Job search keywords (can be multiple) and locations (can be multiple)
- Your resume path and whether to use the upload feature
- Default answers for application questions
- Filters (experience level, job type, remote preference, etc.)

### 3. Place Your Resume

Put your resume PDF in the project directory (or update the path in `config.yaml`).

### 4. Run

```bash
python main.py
```

Or with options:

```bash
# Run with visible browser (non-headless)
python main.py --no-headless

# Set max number of applications
python main.py --max-applies 50

# Dry run (fill forms but don't submit)
python main.py --dry-run
```

## Configuration

See `config.example.yaml` for all available options. Key settings:

| Setting             | Description                                                                        |
| ------------------- | ---------------------------------------------------------------------------------- |
| `linkedin.email`    | Your LinkedIn email                                                                |
| `linkedin.password` | Your LinkedIn password                                                             |
| `search.keywords`   | List of job search keywords (e.g., "Frontend Developer", "Backend Developer")      |
| `search.locations`  | List of preferred locations (e.g., "Hyderabad, India", "Worldwide")                |
| `search.filters`    | Experience level, job type, remote, etc.                                           |
| `answers`           | Default textual answers for common application questions (including Regex support) |
| `resume_path`       | Path to your resume PDF                                                            |
| `bot.upload_resume` | `false` uses the existing LinkedIn default. `true` attempts to re-upload.          |

## ⚠️ Disclaimer

This tool is for **educational purposes only**. Use at your own risk. Automated interactions with LinkedIn may violate their Terms of Service. The authors are not responsible for any consequences of using this tool, including account restrictions.

## Project Structure

```
job/
├── main.py              # Entry point and CLI
├── config.example.yaml  # Example configuration
├── config.yaml          # Your configuration (gitignored)
├── requirements.txt     # Python dependencies
├── src/
│   ├── __init__.py
│   ├── bot.py           # Main bot orchestrator
│   ├── auth.py          # LinkedIn authentication
│   ├── job_search.py    # Job search and filtering
│   ├── applicant.py     # Form filling and submission
│   ├── tracker.py       # Application tracking/logging
│   └── utils.py         # Helper utilities
└── data/
    └── applied_jobs.json # Tracking log (auto-created)
    └── failed_jobs.json  # Failure logs (auto-created)
```
