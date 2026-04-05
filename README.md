# LinkedIn Auto Apply Bot 🚀

An automation tool that takes control of your Chrome browser and automatically applies to LinkedIn jobs using the **Easy Apply** feature.

## Features

- 🔐 **Secure Login** — Logs into LinkedIn with your credentials (supports manual 2FA)
- 🔍 **Smart Job Search** — Searches for jobs based on your configured keywords, location, and filters
- 📝 **Auto Form Fill** — Automatically fills out Easy Apply forms (text fields, dropdowns, radio buttons)
- 📄 **Resume Upload** — Attaches your resume to applications
- 📊 **Application Tracking** — Tracks all applied jobs in a JSON log file
- ⏱️ **Human-like Delays** — Randomized delays to mimic human behavior
- 🛡️ **Error Recovery** — Gracefully handles errors and skips problematic applications
- ⚙️ **Configurable** — Fully configurable via `config.yaml`

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
- Job search keywords and location
- Your resume path
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

| Setting | Description |
|---------|-------------|
| `linkedin.email` | Your LinkedIn email |
| `linkedin.password` | Your LinkedIn password |
| `search.keywords` | Job search keywords (e.g., "Python Developer") |
| `search.location` | Preferred location |
| `search.filters` | Experience level, job type, remote, etc. |
| `answers` | Default answers for common application questions |
| `resume_path` | Path to your resume PDF |

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
```
