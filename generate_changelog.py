#!/usr/bin/env python3
"""
Generate a changelog from the flatpak runtime update data.
This creates a hybrid changelog combining dashboard statistics with a user-friendly timeline.
Supports backfilling from historical workflow run artifacts.
"""

import json
import logging
import os
import sys
import requests
import tempfile
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from github import Github

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class OutdatedPackage:
    """Information about an outdated flatpak package."""
    flatpak_id: str
    sources: List[str]
    current_runtime: str
    latest_runtime: str
    current_version: str
    latest_version: str
    issue_number: Optional[int] = None
    monthly_downloads: int = 0


@dataclass
class HistoricalSnapshot:
    """Historical data from a workflow run."""
    run_date: datetime
    run_id: int
    outdated_packages: Set[str]
    all_tracked_packages: Set[str]
    total_checked: int
    outdated_count: int


class ChangelogGenerator:
    """Generates markdown changelog from flatpak runtime update data."""
    
    def __init__(self, github_token: str, repo_name: str, output_file: str = "index.md"):
        """Initialize the changelog generator."""
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repo_name)
        self.output_file = output_file
        self.current_date = datetime.now()
        self.github_token = github_token
        # Jekyll front matter for the index page
        self.jekyll_front_matter = """---
layout: default
title: Home
---

"""
        
    def fetch_historical_workflow_runs(self, workflow_name: str = "Check Flatpak Runtime Updates") -> List[dict]:
        """Fetch all scheduled workflow runs (not manually triggered) for backfilling."""
        logger.info(f"Fetching historical workflow runs for: {workflow_name}")
        
        try:
            # Get the workflow ID for "Check Flatpak Runtime Updates"
            workflows = self.repo.get_workflows()
            target_workflow = None
            
            for workflow in workflows:
                if workflow_name in workflow.name:
                    target_workflow = workflow
                    break
            
            if not target_workflow:
                logger.warning(f"Could not find workflow: {workflow_name}")
                return []
            
            logger.info(f"Found workflow: {target_workflow.name} (ID: {target_workflow.id})")
            
            # Get all completed workflow runs
            # Filter to only scheduled runs (event == 'schedule')
            runs = target_workflow.get_runs(status='completed', event='schedule')
            
            historical_runs = []
            for run in runs:
                # Only include successful runs
                if run.conclusion == 'success':
                    historical_runs.append({
                        'id': run.id,
                        'created_at': run.created_at,
                        'event': run.event,
                        'conclusion': run.conclusion
                    })
            
            logger.info(f"Found {len(historical_runs)} scheduled workflow runs")
            return historical_runs
            
        except Exception as e:
            logger.error(f"Failed to fetch workflow runs: {e}")
            return []
    
    def download_artifact_data(self, run_id: int) -> Optional[dict]:
        """Download and parse the outdated_packages.json from a workflow run artifact."""
        try:
            # Use GitHub API to get artifacts for this run
            url = f"https://api.github.com/repos/{self.repo.full_name}/actions/runs/{run_id}/artifacts"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            artifacts = response.json()
            
            # Find the outdated-packages-data artifact
            target_artifact = None
            for artifact in artifacts.get('artifacts', []):
                if artifact['name'] == 'outdated-packages-data':
                    target_artifact = artifact
                    break
            
            if not target_artifact:
                logger.debug(f"No artifact found for run {run_id}")
                return None
            
            # Download the artifact
            download_url = target_artifact['archive_download_url']
            download_response = requests.get(download_url, headers=headers)
            download_response.raise_for_status()
            
            # Extract the ZIP file and read the JSON
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, 'artifact.zip')
                with open(zip_path, 'wb') as f:
                    f.write(download_response.content)
                
                # Extract and read JSON
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdir)
                    
                    json_path = os.path.join(tmpdir, 'outdated_packages.json')
                    if os.path.exists(json_path):
                        with open(json_path, 'r') as f:
                            return json.load(f)
            
            return None
            
        except Exception as e:
            logger.debug(f"Could not download artifact for run {run_id}: {e}")
            return None
    
    def build_historical_snapshots(self) -> List[HistoricalSnapshot]:
        """Build a list of historical snapshots from previous workflow runs."""
        logger.info("Building historical snapshots from workflow artifacts...")
        
        workflow_runs = self.fetch_historical_workflow_runs()
        snapshots = []
        
        for run_info in workflow_runs:
            run_id = run_info['id']
            run_date = run_info['created_at']
            
            # Download artifact data
            data = self.download_artifact_data(run_id)
            
            if data:
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
        logger.info(f"Built {len(snapshots)} historical snapshots")
        
        return snapshots
    
    def detect_changes_between_snapshots(self, old_snapshot: HistoricalSnapshot, 
                                        new_snapshot: HistoricalSnapshot) -> Tuple[Set[str], Set[str], Set[str]]:
        """Detect what changed between two snapshots."""
        # Apps that were updated (were outdated, now up to date)
        updated = old_snapshot.outdated_packages - new_snapshot.outdated_packages
        
        # Apps that were added to tracking
        added = new_snapshot.all_tracked_packages - old_snapshot.all_tracked_packages
        
        # Apps that were removed from tracking
        removed = old_snapshot.all_tracked_packages - new_snapshot.all_tracked_packages
        
        return updated, added, removed
        
    def load_outdated_packages(self, file_path: str) -> Tuple[List[OutdatedPackage], List[str], dict]:
        """Load outdated packages from JSON file and return packages, all tracked apps, and metadata."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            packages = []
            for item in data.get('outdated_packages', []):
                package = OutdatedPackage(
                    flatpak_id=item['flatpak_id'],
                    sources=item['sources'],
                    current_runtime=item['current_runtime'],
                    latest_runtime=item['latest_runtime'],
                    current_version=item['current_version'],
                    latest_version=item['latest_version']
                )
                packages.append(package)
            
            all_tracked_packages = data.get('all_tracked_packages', [])
            metadata = {
                'timestamp': data.get('timestamp', ''),
                'total_checked': data.get('total_checked', 0),
                'outdated_count': data.get('outdated_count', 0)
            }
            
            return packages, all_tracked_packages, metadata
            
        except Exception as e:
            logger.error(f"Failed to load outdated packages from {file_path}: {e}")
            return [], [], {}
    
    def get_issue_number_for_package(self, flatpak_id: str) -> Optional[int]:
        """Find the GitHub issue number for a given flatpak ID."""
        try:
            # Search for open issues with the flatpak ID in the title
            issues = self.repo.get_issues(state='open')
            for issue in issues:
                if flatpak_id in issue.title:
                    return issue.number
            return None
        except Exception as e:
            logger.warning(f"Could not find issue for {flatpak_id}: {e}")
            return None
    
    def get_recently_closed_issues(self, days: int = 7) -> List[dict]:
        """Get issues closed in the last N days."""
        try:
            since = self.current_date - timedelta(days=days)
            closed_issues = self.repo.get_issues(state='closed', since=since)
            
            recent_closed = []
            for issue in closed_issues:
                if issue.closed_at and issue.closed_at >= since:
                    # Extract flatpak ID from title
                    if 'Update runtime for app/' in issue.title:
                        flatpak_id = issue.title.replace('Update runtime for ', '')
                        recent_closed.append({
                            'flatpak_id': flatpak_id,
                            'issue_number': issue.number,
                            'closed_at': issue.closed_at,
                            'title': issue.title
                        })
            
            return recent_closed
        except Exception as e:
            logger.warning(f"Could not fetch recently closed issues: {e}")
            return []
    
    def format_runtime_as_label(self, runtime: str, version: str) -> str:
        """Convert runtime format to GitHub label format with backticks.
        
        Examples:
            org.gnome.Platform/x86_64/48 -> `gnome-48`
            org.freedesktop.Platform/x86_64/24.08 -> `freedesktop-24.08`
            org.kde.Platform/x86_64/6.9 -> `kde-6.9`
        """
        if '/' in runtime:
            platform_name = runtime.split('/')[0]  # Extract org.gnome.Platform
        else:
            platform_name = runtime
        
        # Extract the platform type (gnome, freedesktop, kde)
        if 'gnome' in platform_name.lower():
            platform_type = 'gnome'
        elif 'freedesktop' in platform_name.lower():
            platform_type = 'freedesktop'
        elif 'kde' in platform_name.lower():
            platform_type = 'kde'
        else:
            # Fallback to showing full runtime
            return f"`{platform_name} {version}`"
        
        return f"`{platform_type}-{version}`"
    
    def generate_application_table(self, packages: List[OutdatedPackage]) -> str:
        """Generate a markdown table of outdated applications in the CHANGELOG format."""
        if not packages:
            return "*All applications were up to date in this run!*\n\n"
        
        table = "| Application Name | Flatpak ID | Current Runtime | Target Runtime |\n"
        table += "|------------------|------------|-----------------|----------------|\n"
        
        # Sort by flatpak_id for consistency
        sorted_packages = sorted(packages, key=lambda x: x.flatpak_id)
        
        for pkg in sorted_packages:
            flatpak_id = pkg.flatpak_id
            # Remove 'app/' prefix if present
            clean_id = flatpak_id.replace('app/', '')
            # Extract application name (last part after the last dot)
            app_name = clean_id.split('.')[-1]
            
            # Create Flathub GitHub link
            flathub_link = f"https://github.com/flathub/{clean_id}"
            linked_id = f"[{clean_id}]({flathub_link})"
            
            # Format runtimes as GitHub labels
            current_label = self.format_runtime_as_label(pkg.current_runtime, pkg.current_version)
            target_label = self.format_runtime_as_label(pkg.latest_runtime, pkg.latest_version)
            
            table += f"| {app_name} | {linked_id} | {current_label} | {target_label} |\n"
        
        table += "\n"
        return table
    
    def group_packages_by_runtime(self, packages: List[OutdatedPackage]) -> Dict[str, List[OutdatedPackage]]:
        """Group packages by runtime family (GNOME, KDE, Freedesktop)."""
        groups = {
            'GNOME': [],
            'KDE': [],
            'Freedesktop': [],
            'Other': []
        }
        
        for package in packages:
            runtime_name = package.current_runtime.split('/')[0] if '/' in package.current_runtime else package.current_runtime
            if 'gnome' in runtime_name.lower():
                groups['GNOME'].append(package)
            elif 'kde' in runtime_name.lower():
                groups['KDE'].append(package)
            elif 'freedesktop' in runtime_name.lower():
                groups['Freedesktop'].append(package)
            else:
                groups['Other'].append(package)
        
        return groups
    
    def identify_popular_packages(self, packages_by_runtime: Dict[str, List[OutdatedPackage]], top_n: int = 10) -> set:
        """Identify top N most downloaded packages for each runtime group."""
        popular_package_ids = set()
        
        for runtime_name, packages in packages_by_runtime.items():
            if runtime_name == 'Other':
                continue
            # Sort by monthly downloads (descending)
            sorted_packages = sorted(packages, key=lambda p: p.monthly_downloads, reverse=True)
            
            # Take top N packages (or all if fewer than N)
            for package in sorted_packages[:top_n]:
                popular_package_ids.add(package.flatpak_id)
        
        return popular_package_ids
    
    def generate_dashboard_section(self, packages: List[OutdatedPackage], 
                                   all_tracked: List[str], 
                                   metadata: dict) -> str:
        """Generate the dashboard statistics section."""
        total_tracked = len(all_tracked)
        up_to_date = total_tracked - len(packages)
        compliance_rate = (up_to_date / total_tracked * 100) if total_tracked > 0 else 0
        
        # Extract run date from metadata if available
        run_date = "most recent scheduled run"
        if metadata.get('timestamp'):
            try:
                ts = datetime.fromisoformat(metadata['timestamp'].replace('Z', '+00:00'))
                run_date = f"most recent scheduled run: {ts.strftime('%Y-%m-%d')}"
            except (ValueError, TypeError):
                # If timestamp is missing or malformed, fall back to default run_date string
                logger.warning("Could not parse timestamp from metadata; using default run_date.")
        
        dashboard = f"""*Updated: {self.current_date.strftime('%B %d, %Y at %H:%M UTC')}*

## Overview Statistics
*(Based on {run_date})*

# Success Rate - {compliance_rate:.1f}% 

| Metric | Count |
|--------|-------|
| **Total Applications Tracked** | {total_tracked} |
| **✅ Up to Date** | {up_to_date} |
| **⏳ Need Updates** | {len(packages)} |

## Contribution Opportunities by Platform**

### [GNOME Platform: 49](https://github.com/{self.repo.full_name}/issues?q=is%3Aissue+is%3Aopen+label%3Agnome-49)
### [KDE Platform: 6.9](https://github.com/{self.repo.full_name}/issues?q=is%3Aissue+is%3Aopen+label%3Akde-6.9)
### [Freedesktop Platform: 25.08](https://github.com/{self.repo.full_name}/issues?q=is%3Aissue+is%3Aopen+label%3Afreedesktop-25.08)

---

# Purpose

This website is designed to help new contributors find applications in Flathub that need runtime updates. Check the [open issues](https://github.com/{self.repo.full_name}/issues) and find your favorite app!

This only tracks apps shipping in Aurora, Bazzite, and Bluefin. It also tracks the applications shipping in the [Bazaar](https://github.com/kolunmi/bazaar) curated sections. Our hope is by focusing on a core set of apps shipping to our users that we can help target the most popular applications. Thanks for helping!

# Changelog

Below is a record of all scheduled workflow runs that have checked for runtime updates.

"""
        return dashboard
    
    def generate_changelog_section(self, packages: List[OutdatedPackage],
                                   metadata: dict) -> str:
        """Generate the weekly changelog section with table format."""
        
        # Get week range
        start_of_week = self.current_date - timedelta(days=self.current_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        week_range = f"{start_of_week.strftime('%B %d')} - {end_of_week.strftime('%B %d, %Y')}"
        
        # Try to get run date and ID from workflow or use current date
        run_date = self.current_date.strftime('%Y-%m-%d')
        run_id_link = "[Run ID unavailable]"
        
        # Get latest workflow run to extract run ID
        try:
            workflows = self.repo.get_workflows()
            for workflow in workflows:
                if "Check Flatpak Runtime Updates" in workflow.name:
                    runs = workflow.get_runs(status='completed', event='schedule')
                    latest_run = next(iter(runs), None)
                    if latest_run:
                        run_id_link = f"[{latest_run.id}](https://github.com/{self.repo.full_name}/actions/runs/{latest_run.id})"
                        run_date = latest_run.created_at.strftime('%Y-%m-%d')
                    break
        except Exception as e:
            logger.debug(f"Could not fetch workflow run info: {e}")
        
        total_tracked = metadata.get('total_checked', len(packages))
        outdated_count = metadata.get('outdated_count', len(packages))
        up_to_date = total_tracked - outdated_count
        success_rate = ((up_to_date / total_tracked * 100) if total_tracked > 0 else 0)
        
        changelog = f"""## Week of {week_range}

**Run Date:** {run_date}  
**Run ID:** {run_id_link}

{self.generate_application_table(packages)}
### Stats
- **Total**: {total_tracked}
- **Up to Date:** {up_to_date}
- **Need Updates:** {outdated_count}
- **Success Rate:** {success_rate:.1f}%

### Summary
This scheduled workflow run checked {total_tracked} flatpak applications across all ublue-os sources. {outdated_count} applications were found with outdated runtimes and issues were created or updated for each.

---

"""
        return changelog
    
    def generate_historical_changelog_sections(self, snapshots: List[HistoricalSnapshot]) -> str:
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
            updated, added, removed = self.detect_changes_between_snapshots(old_snapshot, new_snapshot)
            
            # Only create a section if there were changes
            if not (updated or added or removed):
                continue
            
            # Calculate week range for this snapshot
            run_date = new_snapshot.run_date
            start_of_week = run_date - timedelta(days=run_date.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            week_range = f"{start_of_week.strftime('%B %d')} - {end_of_week.strftime('%B %d, %Y')}"
            
            section = f"""## Week of {week_range}

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
            
            section += "---\n\n"
            historical_sections.append(section)
        
        # Reverse to show newest first (after current week)
        historical_sections.reverse()
        
        if historical_sections:
            return "# Historical Updates\n\n" + "".join(historical_sections)
        
        return ""
    
    def generate_changelog(self, outdated_file: str):
        """Generate the complete changelog by prepending current week's update."""
        logger.info(f"Generating changelog from {outdated_file}")
        
        # Load data
        packages, all_tracked, metadata = self.load_outdated_packages(outdated_file)
        
        if not packages and not all_tracked:
            logger.warning("No data available to generate changelog")
            return
        
        logger.info(f"Found {len(packages)} outdated packages, {len(all_tracked)} total tracked")
        
        # Generate dashboard section
        dashboard = self.generate_dashboard_section(packages, all_tracked, metadata)
        
        # Generate changelog section for current week
        current_week_changelog = self.generate_changelog_section(packages, metadata)
        
        # Check if output file already exists
        existing_content = ""
        if os.path.exists(self.output_file):
            logger.info("Existing file found - will keep existing historical sections")
            with open(self.output_file, 'r') as f:
                content = f.read()
                # Skip Jekyll front matter if present (between --- markers at start of file)
                if content.startswith('---'):
                    # Find the closing front matter marker (must be on its own line)
                    lines = content.split('\n')
                    front_matter_end = -1
                    for i, line in enumerate(lines[1:], start=1):  # Start from line 1 (skip opening ---)
                        if line.strip() == '---':
                            front_matter_end = i
                            break
                    if front_matter_end != -1:
                        # Join lines after the front matter, skipping the closing ---
                        content = '\n'.join(lines[front_matter_end + 1:]).lstrip()
                # Extract everything after the first "## Week of" to preserve historical data
                if "## Week of" in content:
                    parts = content.split("## Week of", 1)
                    if len(parts) > 1:
                        # Keep everything from the second week onwards
                        existing_content = "## Week of " + parts[1]
                        # If there's another week, extract it and all subsequent weeks
                        if "## Week of" in existing_content:
                            # Keep old weeks as historical sections
                            pass
        
        # Combine: Jekyll front matter (if writing to index.md) + Dashboard + Current Week + Existing Historical
        full_changelog = ""
        # Check if output file is index.md (either relative or absolute path)
        output_basename = os.path.basename(self.output_file)
        if output_basename == 'index.md':
            full_changelog = self.jekyll_front_matter
        full_changelog += dashboard + current_week_changelog
        
        if existing_content:
            # Insert existing historical content
            full_changelog = full_changelog + "\n" + existing_content
        
        # Add footer
        full_changelog += """
---

*This changelog is automatically maintained and updated with each scheduled workflow run.*
"""
        
        try:
            with open(self.output_file, 'w') as f:
                f.write(full_changelog)
            logger.info(f"Successfully generated changelog: {self.output_file}")
        except Exception as e:
            logger.error(f"Failed to write changelog: {e}")
            sys.exit(1)


def main():
    """Main entry point for changelog generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate changelog from flatpak runtime update data')
    parser.add_argument('outdated_file', help='Path to outdated_packages.json file')
    args = parser.parse_args()
    
    outdated_file = args.outdated_file
    
    github_token = os.environ.get('GITHUB_TOKEN')
    repo_name = os.environ.get('GITHUB_REPOSITORY')
    
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is required")
        sys.exit(1)
        
    if not repo_name:
        logger.error("GITHUB_REPOSITORY environment variable is required")
        sys.exit(1)
    
    if not os.path.exists(outdated_file):
        logger.error(f"Outdated packages file not found: {outdated_file}")
        sys.exit(1)
    
    # Generate changelog
    generator = ChangelogGenerator(github_token, repo_name)
    generator.generate_changelog(outdated_file)
    
    logger.info("Changelog generation complete")


if __name__ == '__main__':
    main()
