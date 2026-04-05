#!/usr/bin/env python3
"""
LinkedIn Auto Apply Bot — Entry Point

Usage:
    python main.py                     # Run with default config
    python main.py --no-headless       # Run with visible browser
    python main.py --max-applies 50    # Set max applications
    python main.py --dry-run           # Fill forms but don't submit
    python main.py --config my.yaml    # Use custom config file
"""

import argparse
import os
import sys

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.bot import LinkedInBot

console = Console()


def load_config(config_path: str) -> dict:
    """Load and validate the YAML configuration file."""
    if not os.path.exists(config_path):
        console.print(f"[bold red]Error:[/bold red] Config file not found: {config_path}")
        console.print(
            "[yellow]Hint:[/yellow] Copy config.example.yaml to config.yaml and fill in your details:\n"
            "  cp config.example.yaml config.yaml"
        )
        sys.exit(1)

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Validate search keywords
    search = config.get("search", {})
    if not search.get("keywords"):
        console.print("[bold red]Error:[/bold red] Please set search keywords in config.yaml")
        sys.exit(1)

    return config


def print_banner():
    """Print the application banner."""
    banner = Text()
    banner.append("🚀 LinkedIn Auto Apply Bot\n", style="bold cyan")
    banner.append("   Automate your job applications with ease", style="dim")

    console.print(Panel(banner, border_style="cyan", padding=(1, 2)))
    console.print()


def print_config_summary(config: dict):
    """Print a summary of the active configuration."""
    search = config.get("search", {})
    bot = config.get("bot", {})
    filters = search.get("filters", {})

    console.print("[bold]Configuration:[/bold]")
    
    raw_kw = search.get("keywords", "N/A")
    kw_display = ", ".join(raw_kw) if isinstance(raw_kw, list) else raw_kw
    console.print(f"  Keyword(s):      [cyan]{kw_display}[/cyan]")
    
    raw_loc = search.get("locations", search.get("location", "N/A"))
    loc_display = ", ".join(raw_loc) if isinstance(raw_loc, list) else raw_loc
    console.print(f"  Location(s):     [cyan]{loc_display}[/cyan]")
    console.print(f"  Max Applications:[cyan] {bot.get('max_applications', 25)}[/cyan]")
    console.print(f"  Headless:        [cyan]{bot.get('headless', False)}[/cyan]")
    console.print(f"  Dry Run:         [cyan]{bot.get('dry_run', False)}[/cyan]")
    console.print(f"  Easy Apply Only: [cyan]{filters.get('easy_apply_only', True)}[/cyan]")

    exp = filters.get("experience_level", [])
    if exp:
        console.print(f"  Experience:      [cyan]{', '.join(exp)}[/cyan]")

    remote = filters.get("remote", [])
    if remote:
        console.print(f"  Remote:          [cyan]{', '.join(remote)}[/cyan]")

    console.print()


def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn Auto Apply Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to the YAML config file (default: config.yaml)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run with a visible browser window",
    )
    parser.add_argument(
        "--max-applies",
        type=int,
        help="Maximum number of applications to submit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fill forms but do not submit applications",
    )

    args = parser.parse_args()

    print_banner()

    # Load config
    config = load_config(args.config)

    # Override config with CLI arguments
    if args.no_headless:
        config.setdefault("bot", {})["headless"] = False

    if args.max_applies:
        config.setdefault("bot", {})["max_applications"] = args.max_applies

    if args.dry_run:
        config.setdefault("bot", {})["dry_run"] = True

    # Resolve resume path to absolute
    resume_path = config.get("resume_path", "")
    if resume_path and not os.path.isabs(resume_path):
        config["resume_path"] = os.path.abspath(resume_path)

    print_config_summary(config)

    # Run the bot
    bot = LinkedInBot(config)
    bot.run()


if __name__ == "__main__":
    main()
