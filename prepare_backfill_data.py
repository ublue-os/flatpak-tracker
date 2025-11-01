#!/usr/bin/env python3
"""
Direct CHANGELOG updater using workflow run information and artifact data.
This script will download all artifacts and generate complete tables for each week.
"""

import json
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Workflow runs from the GitHub API (from our earlier query)
WORKFLOW_RUNS = [
    {"id": 18835461852, "created_at": "2025-10-27T09:04:26Z", "html_url": "https://github.com/ublue-os/flatpak-tracker/actions/runs/18835461852"},
    {"id": 18647358799, "created_at": "2025-10-20T09:03:50Z", "html_url": "https://github.com/ublue-os/flatpak-tracker/actions/runs/18647358799"},
    {"id": 18460651533, "created_at": "2025-10-13T09:04:04Z", "html_url": "https://github.com/ublue-os/flatpak-tracker/actions/runs/18460651533"},
    {"id": 18275667071, "created_at": "2025-10-06T09:04:00Z", "html_url": "https://github.com/ublue-os/flatpak-tracker/actions/runs/18275667071"},
    {"id": 18091671815, "created_at": "2025-09-29T09:04:01Z", "html_url": "https://github.com/ublue-os/flatpak-tracker/actions/runs/18091671815"},
    {"id": 17910235305, "created_at": "2025-09-22T09:04:10Z", "html_url": "https://github.com/ublue-os/flatpak-tracker/actions/runs/17910235305"},
    {"id": 17727778387, "created_at": "2025-09-15T09:03:56Z", "html_url": "https://github.com/ublue-os/flatpak-tracker/actions/runs/17727778387"},
    {"id": 17639534930, "created_at": "2025-09-11T09:01:14Z", "html_url": "https://github.com/ublue-os/flatpak-tracker/actions/runs/17639534930"},
]


def generate_application_table(outdated_packages: list) -> str:
    """Generate a markdown table of outdated applications."""
    if not outdated_packages:
        return "*All applications were up to date in this run!*\n\n"
    
    table = "| Application Name | Flatpak ID | Current Runtime | Target Runtime |\n"
    table += "|------------------|------------|-----------------|----------------|\n"
    
    # Sort by flatpak_id for consistency
    sorted_packages = sorted(outdated_packages, key=lambda x: x['flatpak_id'])
    
    for pkg in sorted_packages:
        flatpak_id = pkg['flatpak_id']
        # Remove 'app/' prefix if present
        clean_id = flatpak_id.replace('app/', '')
        # Extract application name (last part after the last dot)
        app_name = clean_id.split('.')[-1]
        
        # Create Flathub GitHub link
        flathub_link = f"https://github.com/flathub/{clean_id}"
        linked_id = f"[{clean_id}]({flathub_link})"
        
        # Get runtime information
        current_runtime = pkg.get('current_runtime', 'Unknown')
        latest_runtime = pkg.get('latest_runtime', 'Unknown')
        current_version = pkg.get('current_version', '')
        latest_version = pkg.get('latest_version', '')
        
        # Format runtime display - show platform name and version
        if '/' in current_runtime:
            platform_name = current_runtime.split('/')[0]
            current_display = f"{platform_name} {current_version}"
        else:
            current_display = current_runtime
            
        if '/' in latest_runtime:
            platform_name = latest_runtime.split('/')[0]
            latest_display = f"{platform_name} {latest_version}"
        else:
            latest_display = latest_runtime
        
        table += f"| {app_name} | {linked_id} | {current_display} | {latest_display} |\n"
    
    table += "\n"
    return table


def generate_section_for_run(run_info: dict, artifact_data: dict = None) -> str:
    """Generate a complete changelog section for a workflow run."""
    run_id = run_info['id']
    created_at = datetime.fromisoformat(run_info['created_at'].replace('Z', '+00:00'))
    html_url = run_info['html_url']
    
    # Calculate week range
    start_of_week = created_at - timedelta(days=created_at.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    week_range = f"{start_of_week.strftime('%B %d')} - {end_of_week.strftime('%B %d, %Y')}"
    
    section = f"""## Week of {week_range}

**Run Date:** {created_at.strftime('%Y-%m-%d')}  
**Run ID:** [{run_id}]({html_url})

"""
    
    if artifact_data:
        outdated_packages = artifact_data.get('outdated_packages', [])
        total_checked = artifact_data.get('total_checked', 0)
        outdated_count = len(outdated_packages)
        up_to_date = total_checked - outdated_count
        compliance_rate = (up_to_date / total_checked * 100) if total_checked > 0 else 0
        
        # Add application table
        section += generate_application_table(outdated_packages)
        
        # Add stats
        section += f"""### Stats
- **Total**: {total_checked}
- **Up to Date:** {up_to_date}
- **Need Updates:** {outdated_count}
- **Success Rate:** {compliance_rate:.1f}%

### Summary
This scheduled workflow run checked {total_checked} flatpak applications across all ublue-os sources. {outdated_count} applications were found with outdated runtimes and issues were created or updated for each.

---

"""
    else:
        # No artifact data available
        section += """### Summary
Scheduled workflow run completed successfully. Runtime checks were performed and issues were created/updated for applications with outdated runtimes.

View detailed logs and statistics in the [workflow run]({html_url}).

---

""".format(html_url=html_url)
    
    return section


def main():
    """
    Main function - outputs the run IDs that need artifact downloads.
    This prepares the data structure for the backfill script.
    """
    logger.info("=" * 70)
    logger.info("CHANGELOG BACKFILL - WORKFLOW RUN INFORMATION")
    logger.info("=" * 70)
    logger.info("")
    logger.info(f"Found {len(WORKFLOW_RUNS)} scheduled workflow runs")
    logger.info("")
    
    # Output run IDs for artifact download
    logger.info("Workflow Run IDs to process:")
    for run in WORKFLOW_RUNS:
        created_at = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
        logger.info(f"  - Run {run['id']}: {created_at.strftime('%Y-%m-%d')}")
    
    logger.info("")
    logger.info("These runs need their artifacts downloaded and processed.")
    logger.info("Each artifact contains outdated_packages.json with the full application list.")
    
    # Store run info for use by download script
    with open('workflow_runs.json', 'w') as f:
        json.dump(WORKFLOW_RUNS, f, indent=2)
    
    logger.info("")
    logger.info("✅ Saved workflow run information to workflow_runs.json")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Download artifacts for each run using GitHub MCP server")
    logger.info("  2. Extract outdated_packages.json from each artifact")
    logger.info("  3. Run backfill script to generate complete CHANGELOG.md")


if __name__ == '__main__':
    main()
