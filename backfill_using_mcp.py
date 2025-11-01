#!/usr/bin/env python3
"""
Backfill script that uses downloaded artifacts to populate CHANGELOG.md.
This version works without direct GitHub API access by processing artifacts
that have been downloaded via the GitHub MCP server.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import List, Set, Tuple
from dataclasses import dataclass
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class HistoricalSnapshot:
    """Historical data from a workflow run."""
    run_date: datetime
    run_id: int
    outdated_packages: Set[str]
    all_tracked_packages: Set[str]
    total_checked: int
    outdated_count: int


def load_artifact_data(artifact_file: str) -> dict:
    """Load JSON data from an artifact file."""
    try:
        with open(artifact_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load artifact {artifact_file}: {e}")
        return None


def build_snapshots_from_artifacts(artifacts_dir: str) -> List[HistoricalSnapshot]:
    """Build snapshots from downloaded artifact JSON files."""
    snapshots = []
    artifacts_path = Path(artifacts_dir)
    
    if not artifacts_path.exists():
        logger.error(f"Artifacts directory does not exist: {artifacts_dir}")
        return snapshots
    
    # Each artifact file should be named with the run_id and date
    for artifact_file in sorted(artifacts_path.glob("*.json")):
        logger.info(f"Processing artifact: {artifact_file.name}")
        
        data = load_artifact_data(artifact_file)
        if not data:
            continue
        
        # Extract run info from filename (format: runID_YYYY-MM-DD.json)
        filename = artifact_file.stem
        parts = filename.split('_')
        if len(parts) >= 2:
            run_id = int(parts[0])
            date_str = '_'.join(parts[1:])
            try:
                run_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                logger.warning(f"Could not parse date from filename: {filename}")
                run_date = datetime.now()
        else:
            run_id = 0
            run_date = datetime.now()
        
        outdated_ids = set(pkg['flatpak_id'] for pkg in data.get('outdated_packages', []))
        all_tracked_ids = set(data.get('all_tracked_packages', []))
        
        snapshot = HistoricalSnapshot(
            run_date=run_date,
            run_id=run_id,
            outdated_packages=outdated_ids,
            all_tracked_packages=all_tracked_ids,
            total_checked=data.get('total_checked', 0),
            outdated_count=data.get('outdated_count', 0)
        )
        snapshots.append(snapshot)
        logger.info(f"  Loaded snapshot from {run_date.strftime('%Y-%m-%d')}: {len(outdated_ids)} outdated packages")
    
    # Sort by date (oldest first)
    snapshots.sort(key=lambda s: s.run_date)
    return snapshots


def detect_changes_between_snapshots(old_snapshot: HistoricalSnapshot, 
                                    new_snapshot: HistoricalSnapshot) -> Tuple[Set[str], Set[str], Set[str]]:
    """Detect what changed between two snapshots."""
    # Apps that were updated (were outdated, now up to date)
    updated = old_snapshot.outdated_packages - new_snapshot.outdated_packages
    
    # Apps that were added to tracking
    added = new_snapshot.all_tracked_packages - old_snapshot.all_tracked_packages
    
    # Apps that were removed from tracking
    removed = old_snapshot.all_tracked_packages - new_snapshot.all_tracked_packages
    
    return updated, added, removed


def generate_historical_changelog_sections(snapshots: List[HistoricalSnapshot]) -> str:
    """Generate changelog sections from historical snapshots."""
    if len(snapshots) < 2:
        logger.info("Not enough historical data to generate backfilled changelog")
        return ""
    
    historical_sections = []
    
    # Process each pair of consecutive snapshots
    for i in range(len(snapshots) - 1):
        old_snapshot = snapshots[i]
        new_snapshot = snapshots[i + 1]
        
        # Detect changes
        updated, added, removed = detect_changes_between_snapshots(old_snapshot, new_snapshot)
        
        # Calculate week range for this snapshot
        run_date = new_snapshot.run_date
        start_of_week = run_date - timedelta(days=run_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        week_range = f"{start_of_week.strftime('%B %d')} - {end_of_week.strftime('%B %d, %Y')}"
        
        # Extract compliance rate calculation for readability
        if len(new_snapshot.all_tracked_packages) > 0:
            compliance_rate = ((len(new_snapshot.all_tracked_packages) - len(new_snapshot.outdated_packages)) / len(new_snapshot.all_tracked_packages) * 100)
        else:
            compliance_rate = 0

        section = f"""## Week of {week_range}

**Run Date:** {run_date.strftime('%Y-%m-%d')}
**Total Applications:** {len(new_snapshot.all_tracked_packages)}
**Outdated:** {len(new_snapshot.outdated_packages)}
**Compliance Rate:** {compliance_rate:.1f}%

"""
        
        if updated:
            section += f"### 🎉 Updated ({len(updated)} applications)\n\n"
            for flatpak_id in sorted(updated):
                app_name = flatpak_id.replace('app/', '').split('.')[-1]
                section += f"- ✅ **{app_name}** (`{flatpak_id}`)\n"
            section += "\n"
        
        if added:
            section += f"### 📦 Added to Tracking ({len(added)} applications)\n\n"
            for flatpak_id in sorted(added):
                app_name = flatpak_id.replace('app/', '').split('.')[-1]
                section += f"- 🆕 **{app_name}** (`{flatpak_id}`)\n"
            section += "\n"
        
        if removed:
            section += f"### 🗑️ Removed from Tracking ({len(removed)} applications)\n\n"
            for flatpak_id in sorted(removed):
                app_name = flatpak_id.replace('app/', '').split('.')[-1]
                section += f"- ❌ **{app_name}** (`{flatpak_id}`)\n"
            section += "\n"
        
        if not updated and not added and not removed:
            section += "*No changes this week*\n\n"
        
        section += "---\n\n"
        historical_sections.append(section)
    
    # Reverse to show newest first
    historical_sections.reverse()
    
    if historical_sections:
        return "# Historical Updates\n\n" + "".join(historical_sections)
    
    return ""


def generate_changelog(artifacts_dir: str, output_file: str = "CHANGELOG.md"):
    """Generate the complete changelog from artifacts."""
    logger.info("=" * 60)
    logger.info("BACKFILL HISTORICAL CHANGELOG DATA")
    logger.info("=" * 60)
    
    # Build snapshots from artifacts
    logger.info("Step 1: Loading historical snapshots from artifacts...")
    snapshots = build_snapshots_from_artifacts(artifacts_dir)
    
    if len(snapshots) < 2:
        logger.warning("Not enough historical data found (need at least 2 snapshots)")
        logger.warning("At least 2 artifact files are required")
        sys.exit(1)
    
    logger.info(f"Found {len(snapshots)} historical snapshots")
    logger.info("")
    
    # Generate historical changelog sections
    logger.info("Step 2: Generating historical changelog sections...")
    historical_changelog = generate_historical_changelog_sections(snapshots)
    
    # Get the most recent snapshot for the dashboard
    latest_snapshot = snapshots[-1]
    
    # Create initial changelog structure
    logger.info("Step 3: Creating changelog structure...")
    
    total_tracked = len(latest_snapshot.all_tracked_packages)
    up_to_date = total_tracked - len(latest_snapshot.outdated_packages)
    compliance_rate = (up_to_date / total_tracked * 100) if total_tracked > 0 else 0
    
    initial_content = f"""# 📊 Flatpak Runtime Tracker
*Historical data backfilled from {len(snapshots)} scheduled workflow runs. Updates automatically every Monday at 09:00 UTC*

## Overview Statistics
*(As of {latest_snapshot.run_date.strftime('%B %d, %Y')})*

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
        with open(output_file, 'w') as f:
            f.write(full_changelog)
        logger.info(f"✅ Successfully created {output_file}")
        logger.info("")
        logger.info("=" * 60)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 60)
        logger.info(f"The changelog has been initialized with {len(snapshots)} historical snapshots.")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Review CHANGELOG.md")
        logger.info("2. Commit and push to repository")
    except Exception as e:
        logger.error(f"Failed to write changelog: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate changelog from downloaded artifact files')
    parser.add_argument('artifacts_dir', help='Directory containing artifact JSON files')
    parser.add_argument('--output', default='CHANGELOG.md', help='Output file (default: CHANGELOG.md)')
    args = parser.parse_args()
    
    generate_changelog(args.artifacts_dir, args.output)


if __name__ == '__main__':
    main()
