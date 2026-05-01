"""
Utility functions for the LinkedIn Auto Apply Bot.
"""

import random
import time
import re
import os
from datetime import datetime

from rich.console import Console

console = Console()

import re

def should_apply(
    title: str,
    role_keywords: list[str] | None = None,
    tech_keywords: list[str] | None = None,
) -> bool:
    tokens = [t.lower() for t in split_role(title)]
    log_info(f" Title tokens : {tokens}")

    _role_kw = set(k.lower() for k in role_keywords) if role_keywords else {"sde", "developer", "engineer"}
    _tech_kw = set(k.lower() for k in tech_keywords) if tech_keywords else {"backend", "nodejs", "node", "golang", "go", "python", "fastapi", "javascript", "typescript", "aws"}

    has_role = any(token in _role_kw for token in tokens)
    has_tech = any(token in _tech_kw for token in tokens)

    log_info(f" has role: {has_role} | has tech: {has_tech}")
    return not (has_role or has_tech)

def split_role(text: str) -> list[str]:
    parts = re.split(r'[^a-zA-Z0-9]+', text)
    log_info(f"parts {parts}")

    seen = set()
    result = []

    for p in parts:
        if p and p not in seen:
            seen.add(p)
            result.append(p)

    return result
def human_delay(min_sec: float = 1.0, max_sec: float = 3.0):
    """Sleep for a random duration to mimic human behavior."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def random_type_delay():
    """Return a random typing delay in milliseconds."""
    return random.randint(30, 120)


def log_info(message: str):
    """Log an info message with timestamp."""
    console.print(f"[bold cyan][{_timestamp()}][/bold cyan] [green]ℹ[/green]  {message}")


def log_success(message: str):
    """Log a success message."""
    console.print(f"[bold cyan][{_timestamp()}][/bold cyan] [bold green]✓[/bold green]  {message}")


def log_warning(message: str):
    """Log a warning message."""
    console.print(f"[bold cyan][{_timestamp()}][/bold cyan] [bold yellow]⚠[/bold yellow]  {message}")


def log_error(message: str):
    """Log an error message."""
    console.print(f"[bold cyan][{_timestamp()}][/bold cyan] [bold red]✗[/bold red]  {message}")


def log_step(step: int, total: int, message: str):
    """Log a step in a process."""
    console.print(
        f"[bold cyan][{_timestamp()}][/bold cyan] "
        f"[bold magenta][{step}/{total}][/bold magenta] {message}"
    )


def _timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def sanitize_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')[:80]


def ensure_dir(path: str):
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)


def match_answer(question_text: str, answers_config: dict) -> str | None:
    """
    Try to find an answer for a question by matching against known patterns.

    Checks direct field mappings first, then custom regex patterns.
    Returns the answer string or None if no match.
    """
    q = question_text.lower().strip()

    # Direct field mappings: (pattern, config_key)
    direct_maps = [
        (r"year.*experience|experience.*year", "years_of_experience"),
        (r"month.*experience|experience.*month", "months_of_experience"),
        (r"phone|mobile|contact number", "phone_number"),
        (r"city|location|where.*based|current.*city", "city"),
        (r"authorized.*work|legally.*work|eligib.*work|work.*authori", "authorized_to_work"),
        (r"sponsor|visa.*sponsor|require.*sponsor", "require_sponsorship"),
        (r"current.*ctc|current.*salary|current.*compensation", "current_ctc"),
        (r"expected.*ctc|expected.*salary|expected.*compensation", "expected_ctc"),
        (r"notice.*period", "notice_period"),
        (r"gender", "gender"),
        (r"degree|education|qualification", "degree"),
        (r"gpa|cgpa|grade|percentage", "gpa"),
        (r"linkedin.*url|linkedin.*profile", "linkedin_url"),
        (r"github.*url|github.*profile|github.*link", "github_url"),
        (r"website|portfolio|personal.*url|personal.*site", "website_url"),
    ]

    for pattern, key in direct_maps:
        if re.search(pattern, q) and key in answers_config:
            return str(answers_config[key])

    # Custom patterns from config
    custom = answers_config.get("custom", [])
    for entry in custom:
        if re.search(entry["pattern"], q, re.IGNORECASE):
            return str(entry["answer"])

    return None


def format_job_info(title: str, company: str, location: str = "") -> str:
    """Format job information for display."""
    parts = [f"[bold]{title}[/bold]", f"at [cyan]{company}[/cyan]"]
    if location:
        parts.append(f"([dim]{location}[/dim])")
    return " ".join(parts)