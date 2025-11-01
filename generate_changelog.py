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
    
    def __init__(self, github_token: str, repo_name: str, output_file: str = "CHANGELOG.md"):
        """Initialize the changelog generator."""
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repo_name)
        self.output_file = output_file
        self.current_date = datetime.now()
        self.github_token = github_token
        
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
                                   recently_closed: List[dict],
                                   packages_by_runtime: Dict[str, List[OutdatedPackage]]) -> str:
        """Generate the dashboard statistics section."""
        total_tracked = len(all_tracked)
        up_to_date = total_tracked - len(packages)
        compliance_rate = (up_to_date / total_tracked * 100) if total_tracked > 0 else 0
        
        dashboard = f"""# 📊 Flatpak Runtime Tracker
*Updated: {self.current_date.strftime('%B %d, %Y at %H:%M UTC')}*

## Overview Statistics

| Metric | Count |
|--------|-------|
| **Total Applications Tracked** | {total_tracked} |
| **✅ Up to Date** | {up_to_date} |
| **⏳ Need Updates** | {len(packages)} |
| **Compliance Rate** | {compliance_rate:.1f}% |

---

## 🎯 Runtime Migration Progress
"""
        
        # Add progress for each runtime
        for runtime_name in ['GNOME', 'KDE', 'Freedesktop']:
            runtime_packages = packages_by_runtime.get(runtime_name, [])
            if runtime_packages:
                # Determine the target version from the most common latest_version
                target_version = runtime_packages[0].latest_version if runtime_packages else "N/A"
                
                dashboard += f"\n### {runtime_name} Platform {target_version}\n"
                dashboard += f"**{len(runtime_packages)} applications** need updates\n\n"
        
        dashboard += "---\n\n"
        return dashboard
    
    def generate_changelog_section(self, packages: List[OutdatedPackage],
                                   recently_closed: List[dict],
                                   popular_package_ids: set) -> str:
        """Generate the timeline/changelog section."""
        
        # Get week range
        start_of_week = self.current_date - timedelta(days=self.current_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        week_range = f"{start_of_week.strftime('%B %d')} - {end_of_week.strftime('%B %d, %Y')}"
        
        changelog = f"""# Weekly Update
**Week of {week_range}**

---

"""
        
        # Recently Updated section
        if recently_closed:
            changelog += f"## 🎉 Recently Updated ({len(recently_closed)} applications)\n"
            changelog += "*These applications have successfully updated to the latest runtime!*\n\n"
            
            for item in recently_closed[:15]:  # Show top 15
                flatpak_id = item['flatpak_id']
                issue_num = item['issue_number']
                app_name = flatpak_id.replace('app/', '').split('.')[-1]
                changelog += f"- ✅ **{app_name}** (`{flatpak_id}`) - [#{issue_num}](https://github.com/{self.repo.full_name}/issues/{issue_num})\n"
            
            if len(recently_closed) > 15:
                changelog += f"\n<details>\n<summary>View {len(recently_closed) - 15} more recently updated apps...</summary>\n\n"
                for item in recently_closed[15:]:
                    flatpak_id = item['flatpak_id']
                    issue_num = item['issue_number']
                    app_name = flatpak_id.replace('app/', '').split('.')[-1]
                    changelog += f"- ✅ **{app_name}** - [#{issue_num}](https://github.com/{self.repo.full_name}/issues/{issue_num})\n"
                changelog += "\n</details>\n"
            
            changelog += "\n---\n\n"
        
        # Pending Updates section
        if packages:
            changelog += f"## 🔄 Pending Updates ({len(packages)} applications)\n"
            changelog += "*These applications still need runtime updates. Click to help!*\n\n"
            
            # Separate popular from standard
            popular_packages = [p for p in packages if p.flatpak_id in popular_package_ids]
            standard_packages = [p for p in packages if p.flatpak_id not in popular_package_ids]
            
            if popular_packages:
                changelog += f"### 🔥 High Priority (Popular Apps - Top {len(popular_packages)})\n\n"
                for package in popular_packages[:10]:  # Show top 10 popular
                    app_name = package.flatpak_id.replace('app/', '').split('.')[-1]
                    issue_num = self.get_issue_number_for_package(package.flatpak_id)
                    version_change = f"{package.current_version} → {package.latest_version}"
                    
                    if issue_num:
                        changelog += f"- 🔥 **{app_name}** (`{package.flatpak_id}`) - {version_change} - [#{issue_num}](https://github.com/{self.repo.full_name}/issues/{issue_num})\n"
                    else:
                        changelog += f"- 🔥 **{app_name}** (`{package.flatpak_id}`) - {version_change}\n"
                
                if len(popular_packages) > 10:
                    changelog += f"\n<details>\n<summary>View {len(popular_packages) - 10} more high priority apps...</summary>\n\n"
                    for package in popular_packages[10:]:
                        app_name = package.flatpak_id.replace('app/', '').split('.')[-1]
                        issue_num = self.get_issue_number_for_package(package.flatpak_id)
                        version_change = f"{package.current_version} → {package.latest_version}"
                        
                        if issue_num:
                            changelog += f"- 🔥 **{app_name}** - {version_change} - [#{issue_num}](https://github.com/{self.repo.full_name}/issues/{issue_num})\n"
                        else:
                            changelog += f"- 🔥 **{app_name}** - {version_change}\n"
                    changelog += "\n</details>\n"
                
                changelog += "\n"
            
            if standard_packages:
                changelog += f"### Standard Priority ({len(standard_packages)} applications)\n\n"
                changelog += "<details>\n<summary>View all standard priority apps...</summary>\n\n"
                
                for package in standard_packages:
                    app_name = package.flatpak_id.replace('app/', '').split('.')[-1]
                    issue_num = self.get_issue_number_for_package(package.flatpak_id)
                    version_change = f"{package.current_version} → {package.latest_version}"
                    
                    if issue_num:
                        changelog += f"- **{app_name}** (`{package.flatpak_id}`) - {version_change} - [#{issue_num}](https://github.com/{self.repo.full_name}/issues/{issue_num})\n"
                    else:
                        changelog += f"- **{app_name}** (`{package.flatpak_id}`) - {version_change}\n"
                
                changelog += "\n</details>\n"
            
            changelog += "\n---\n\n"
        
        # How to help section
        changelog += """## 💡 How You Can Help

1. **Test existing PRs**: Many apps already have updates pending on Flathub - test them!
2. **Submit updates**: Follow the instructions in each issue to update manifests
3. **Report issues**: If you find problems with updated apps, report them upstream

[View all open issues →](https://github.com/{}/issues?q=is%3Aissue+is%3Aopen)

---

*This changelog updates automatically every Monday at 11:00 UTC, 2 hours after the runtime check runs.*
""".format(self.repo.full_name)
        
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
    
    def generate_changelog(self, outdated_file: str, backfill: bool = False):
        """Generate the complete changelog."""
        logger.info(f"Generating changelog from {outdated_file}")
        
        # Load data
        packages, all_tracked, metadata = self.load_outdated_packages(outdated_file)
        recently_closed = self.get_recently_closed_issues(days=7)
        
        if not packages and not all_tracked:
            logger.warning("No data available to generate changelog")
            return
        
        logger.info(f"Found {len(packages)} outdated packages, {len(all_tracked)} total tracked")
        logger.info(f"Found {len(recently_closed)} recently closed issues")
        
        # Group packages by runtime
        packages_by_runtime = self.group_packages_by_runtime(packages)
        
        # Identify popular packages (excluding 'Other' category)
        popular_package_ids = self.identify_popular_packages(packages_by_runtime, top_n=10)
        logger.info(f"Identified {len(popular_package_ids)} popular packages")
        
        # Generate dashboard section
        dashboard = self.generate_dashboard_section(packages, all_tracked, recently_closed, packages_by_runtime)
        
        # Generate changelog section for current week
        changelog = self.generate_changelog_section(packages, recently_closed, popular_package_ids)
        
        # Generate historical sections if backfill is enabled
        historical_changelog = ""
        if backfill:
            logger.info("Backfilling historical data from previous workflow runs...")
            snapshots = self.build_historical_snapshots()
            historical_changelog = self.generate_historical_changelog_sections(snapshots)
        
        # Combine all sections
        full_changelog = dashboard + changelog + historical_changelog
        
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
    parser.add_argument('--backfill', action='store_true', 
                       help='Backfill historical data from previous scheduled workflow runs')
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
    generator.generate_changelog(outdated_file, backfill=args.backfill)
    
    logger.info("Changelog generation complete")


if __name__ == '__main__':
    main()
