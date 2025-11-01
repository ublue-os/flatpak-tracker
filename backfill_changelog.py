#!/usr/bin/env python3
"""
One-time backfill script to populate historical changelog data.
This script fetches all previous scheduled workflow runs and generates
a complete historical changelog. Run this once manually to initialize
the changelog history.

Usage:
    export GITHUB_TOKEN="your_token"
    export GITHUB_REPOSITORY="ublue-os/flatpak-tracker"
    python backfill_changelog.py
"""

import os
import sys
import logging

# Import the ChangelogGenerator class
from generate_changelog import ChangelogGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Main entry point for one-time backfill."""
    
    github_token = os.environ.get('GITHUB_TOKEN')
    repo_name = os.environ.get('GITHUB_REPOSITORY')
    
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is required")
        sys.exit(1)
        
    if not repo_name:
        logger.error("GITHUB_REPOSITORY environment variable is required")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("BACKFILL HISTORICAL CHANGELOG DATA")
    logger.info("=" * 60)
    logger.info("This is a ONE-TIME operation to populate historical data")
    logger.info("from all previous scheduled workflow runs.")
    logger.info("")
    
    # Create generator
    generator = ChangelogGenerator(github_token, repo_name, output_file="CHANGELOG.md")
    
    # Build historical snapshots
    logger.info("Step 1: Fetching historical workflow runs...")
    snapshots = generator.build_historical_snapshots()
    
    if len(snapshots) < 2:
        logger.warning("Not enough historical data found (need at least 2 snapshots)")
        logger.warning("The changelog will be created on the next scheduled run")
        sys.exit(0)
    
    logger.info(f"Found {len(snapshots)} historical snapshots")
    logger.info("")
    
    # Generate historical changelog sections
    logger.info("Step 2: Generating historical changelog sections...")
    historical_changelog = generator.generate_historical_changelog_sections(snapshots)
    
    # Get the most recent snapshot for the dashboard
    latest_snapshot = snapshots[-1]
    
    # Create a minimal current week section (placeholder)
    logger.info("Step 3: Creating initial changelog structure...")
    
    total_tracked = len(latest_snapshot.all_tracked_packages)
    up_to_date = total_tracked - len(latest_snapshot.outdated_packages)
    compliance_rate = (up_to_date / total_tracked * 100) if total_tracked > 0 else 0
    
    initial_content = f"""# 📊 Flatpak Runtime Tracker
*Historical data backfilled. Updates automatically every Monday at 11:00 UTC*

## Overview Statistics

| Metric | Count |
|--------|-------|
| **Total Applications Tracked** | {total_tracked} |
| **✅ Up to Date** | {up_to_date} |
| **⏳ Need Updates** | {len(latest_snapshot.outdated_packages)} |
| **Compliance Rate** | {compliance_rate:.1f}% |

---

## 🎯 Runtime Migration Progress

*This section updates weekly with current runtime migration status*

---

# Current Week

*The current week's updates will appear here after the next scheduled workflow run*

---

"""
    
    # Combine with historical data
    full_changelog = initial_content + historical_changelog
    
    # Write to file
    try:
        with open(generator.output_file, 'w') as f:
            f.write(full_changelog)
        logger.info(f"✅ Successfully created {generator.output_file}")
        logger.info("")
        logger.info("=" * 60)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 60)
        logger.info("The changelog has been initialized with historical data.")
        logger.info("Future updates will be appended automatically by the")
        logger.info("scheduled workflow every Monday.")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Review CHANGELOG.md")
        logger.info("2. Commit and push to repository")
        logger.info("3. The next scheduled run will append new updates")
    except Exception as e:
        logger.error(f"Failed to write changelog: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
