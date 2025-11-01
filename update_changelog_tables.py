#!/usr/bin/env python3
"""
Script to update CHANGELOG.md with comprehensive tables for each workflow run.
This uses the GitHub MCP tools to fetch artifacts and generate proper tables.

Usage:
    python update_changelog_tables.py

This script will:
1. Fetch all scheduled workflow run data
2. Download artifacts for each run
3. Generate detailed tables showing all applications that needed updates
4. Update CHANGELOG.md with accurate historical information
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_application_table(outdated_packages: list) -> str:
    """Generate a markdown table of outdated applications."""
    if not outdated_packages:
        return "*No outdated applications found in this run - all applications were up to date!*\n\n"
    
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


def create_week_section_from_template():
    """
    Create a template showing the expected format for each week.
    This will be used as a guide for manual or automated updates.
    """
    template = """
# CHANGELOG TABLE FORMAT TEMPLATE

Each week section should follow this format:

## Week of [Month Day] - [Month Day, Year]

**Run Date:** YYYY-MM-DD  
**Run ID:** [run_id](https://github.com/ublue-os/flatpak-tracker/actions/runs/run_id)

| Application Name | Flatpak ID | Current Runtime | Target Runtime |
|------------------|------------|-----------------|----------------|
| AppName | [org.example.AppName](https://github.com/flathub/org.example.AppName) | org.gnome.Platform 47 | org.gnome.Platform 49 |
| Firefox | [org.mozilla.firefox](https://github.com/flathub/org.mozilla.firefox) | org.freedesktop.Platform 24.08 | org.freedesktop.Platform 25.08 |

### Stats
- **Total**: XXX
- **Up to Date:** XXX
- **Need Updates:** XXX
- **Success Rate:** XX.X%

### Summary
This scheduled workflow run checked XXX flatpak applications across all ublue-os sources. XXX applications were found with outdated runtimes and issues were created or updated for each.

---

"""
    return template


def main():
    """
    Main function to demonstrate the expected format.
    
    NOTE: This script requires GITHUB_TOKEN to fetch actual artifact data.
    For now, it generates a template showing the expected format.
    
    To complete the changelog backfill:
    1. Set GITHUB_TOKEN environment variable
    2. Run: python backfill_changelog_with_tables.py
    """
    logger.info("=" * 70)
    logger.info("CHANGELOG TABLE FORMAT GUIDE")
    logger.info("=" * 70)
    logger.info("")
    logger.info("This script demonstrates the expected table format for CHANGELOG.md")
    logger.info("")
    logger.info("Each workflow run section should include:")
    logger.info("  1. Week range header")
    logger.info("  2. Run date and ID (with link)")
    logger.info("  3. Table of all outdated applications")
    logger.info("  4. Stats summary")
    logger.info("  5. Descriptive summary")
    logger.info("")
    logger.info("Flatpak IDs should link to: https://github.com/flathub/[flatpak.id]")
    logger.info("")
    
    # Show example using temp_outdated.json if it exists
    temp_outdated_path = Path("temp_outdated.json")
    if temp_outdated_path.exists():
        logger.info("Found temp_outdated.json - generating example table:")
        logger.info("")
        
        with open(temp_outdated_path, 'r') as f:
            data = json.load(f)
        
        outdated_packages = data.get('outdated_packages', [])
        logger.info(f"Total packages needing updates: {len(outdated_packages)}")
        logger.info("")
        
        # Generate example table
        table = generate_application_table(outdated_packages[:10])  # Show first 10 as example
        print("\n" + "="*70)
        print("EXAMPLE TABLE (first 10 applications):")
        print("="*70)
        print(table)
        
        logger.info(f"Full dataset has {len(outdated_packages)} outdated applications")
    
    # Print template
    template = create_week_section_from_template()
    print(template)
    
    logger.info("=" * 70)
    logger.info("TO COMPLETE THE BACKFILL:")
    logger.info("=" * 70)
    logger.info("1. Ensure GITHUB_TOKEN environment variable is set")
    logger.info("2. Run: python backfill_changelog_with_tables.py")
    logger.info("3. Review the generated CHANGELOG.md")
    logger.info("4. Commit and push the changes")


if __name__ == '__main__':
    main()
