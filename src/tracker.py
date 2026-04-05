"""
Application tracker — logs all applied jobs to a JSON file for deduplication and reporting.
"""

import json
import os
from datetime import datetime

from src.utils import ensure_dir, log_info


class Tracker:
    """Tracks applied jobs in a JSON file."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.filepath = os.path.join(data_dir, "applied_jobs.json")
        self.failed_filepath = os.path.join(data_dir, "failed_jobs.json")
        ensure_dir(data_dir)
        self._load()

    def _load(self):
        """Load existing tracking data."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {"applied": [], "skipped": [], "failed": []}
            
        if os.path.exists(self.failed_filepath):
            with open(self.failed_filepath, "r") as f:
                self.failed_data = json.load(f)
        else:
            self.failed_data = {"failed": []}

    def _save(self):
        """Persist tracking data to disk."""
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, indent=2, default=str)
        with open(self.failed_filepath, "w") as f:
            json.dump(self.failed_data, f, indent=2, default=str)

    def is_already_applied(self, job_id: str) -> bool:
        """Check if we've already applied to this job."""
        return any(j.get("job_id") == job_id for j in self.data["applied"])

    def record_applied(self, job_id: str, title: str, company: str,
                       location: str = "", url: str = ""):
        """Record a successful application."""
        self.data["applied"].append({
            "job_id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "applied_at": datetime.now().isoformat(),
        })
        self._save()
        log_info(f"Tracked application — total applied: {len(self.data['applied'])}")

    def record_skipped(self, job_id: str, title: str, company: str, reason: str):
        """Record a skipped job."""
        self.data["skipped"].append({
            "job_id": job_id,
            "title": title,
            "company": company,
            "reason": reason,
            "skipped_at": datetime.now().isoformat(),
        })
        self._save()

    def record_failed(self, job_id: str, title: str, company: str, error: str):
        """Record a failed application attempt."""
        entry = {
            "job_id": job_id,
            "title": title,
            "company": company,
            "error": error,
            "failed_at": datetime.now().isoformat(),
        }
        self.data["failed"].append(entry)
        self.failed_data["failed"].append(entry)
        self._save()

    def get_summary(self) -> dict:
        """Return a summary of today's tracking data."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        today_applied = [j for j in self.data["applied"] if j.get("applied_at", "").startswith(today_str)]
        today_skipped = [j for j in self.data["skipped"] if j.get("skipped_at", "").startswith(today_str)]
        today_failed  = [j for j in self.failed_data["failed"] if j.get("failed_at", "").startswith(today_str)]
        
        return {
            "total_applied": len(today_applied),
            "total_skipped": len(today_skipped),
            "total_failed": len(today_failed),
            "todays_applied_jobs": today_applied,
            "todays_failed_jobs": today_failed
        }

    def print_summary(self):
        """Print a formatted summary of today's activity."""
        from rich.table import Table
        from rich.console import Console

        console = Console()
        summary = self.get_summary()

        console.print("\n")
        console.rule("[bold cyan]📊 Today's Application Summary[/bold cyan]")

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_row("[green]✓ Applied[/green]", str(summary["total_applied"]))
        table.add_row("[yellow]⏭ Skipped[/yellow]", str(summary["total_skipped"]))
        table.add_row("[red]✗ Failed[/red]", str(summary["total_failed"]))
        console.print(table)

        todays_applied = summary["todays_applied_jobs"]
        if todays_applied:
            console.print("\n[bold]Today's Applications:[/bold]")
            recent_table = Table(show_header=True, header_style="bold magenta")
            recent_table.add_column("Job (Role - Company)", style="white")
            recent_table.add_column("Applied At", style="dim")

            for job in todays_applied:
                # Clean up extracted texts to prevent multi-line rows
                title = job.get("title", "Unknown").strip().split("\n")[0]
                company = job.get("company", "").strip().split("\n")[0]
                
                job_str = f"{title} - {company}" if company else title
                
                # Make time a bit prettier
                dt_str = job.get("applied_at", "N/A")
                if "T" in dt_str:
                    dt_str = dt_str[:16].replace("T", " ")
                    
                recent_table.add_row(job_str, dt_str)
            console.print(recent_table)

        todays_failed = summary["todays_failed_jobs"]
        if todays_failed:
            console.print("\n[bold red]Today's Failed Applications:[/bold red]")
            error_table = Table(show_header=True, header_style="bold red")
            error_table.add_column("Job (Role - Company)", style="white")
            error_table.add_column("Error Reason", style="dim")
            
            for job in todays_failed:
                title = job.get("title", "Unknown").strip().split("\n")[0]
                company = job.get("company", "").strip().split("\n")[0]
                job_str = f"{title} - {company}" if company else title
                error_msg = job.get("error", "Unknown error").strip().split("\n")[0][:60]
                
                error_table.add_row(job_str, error_msg)
            console.print(error_table)

        console.print("")
