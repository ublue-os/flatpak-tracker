#!/usr/bin/env python3
"""
Issue generator for flatpak runtime updates.
This module handles the creation of GitHub issues for outdated flatpak packages.
"""

import json
import logging
import os
import sys
import re
import requests
import time
from typing import Dict, List, Optional, Tuple
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
    installs: int = 0
    monthly_downloads: int = 0


class IssueGenerator:
    """Handles GitHub issue creation for outdated flatpak packages."""
    
    def __init__(self, github_token: str, repo_name: str):
        """Initialize the issue generator with GitHub credentials."""
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repo_name)
    
    def extract_flatpak_id_from_issue_title(self, issue_title: str) -> Optional[str]:
        """Extract flatpak ID from issue title."""
        match = re.search(r'Update runtime for (app/[^\s]+)', issue_title)
        if match:
            return match.group(1)
        return None
    
    def _get_runtime_label(self, runtime: str) -> Optional[str]:
        """Extract runtime label from runtime string.
        
        Examples:
            org.gnome.Platform/x86_64/49 -> gnome-49
            org.freedesktop.Platform/x86_64/25.08 -> freedesktop-25.08
            org.kde.Platform/x86_64/6.10 -> kde-6.10
        """
        if not runtime or '/' not in runtime:
            return None
        
        parts = runtime.split('/')
        if len(parts) < 3:
            return None
        
        runtime_name = parts[0].lower()
        version = parts[2]
        
        if 'gnome' in runtime_name:
            return f"gnome-{version}"
        elif 'kde' in runtime_name:
            return f"kde-{version}"
        elif 'freedesktop' in runtime_name:
            return f"freedesktop-{version}"
        
        return None
    
    def create_issue_body(self, package: OutdatedPackage) -> str:
        """Generate the issue body content."""
        sources_info = ', '.join(package.sources)
        
        return f"""
## Flatpak Runtime Update Needed

**Package:** `{package.flatpak_id}`
**Current Runtime:** `{package.current_runtime}`
**Latest Available Runtime:** `{package.latest_runtime}`
**Monthly Downloads:** `{package.monthly_downloads}`
**Found in sources:** {sources_info}

### Look for an existing pull request!

Look for the repositoy of this application in [github.com/flathub](https://github.com/flathub) - in many cases a pull request might already exist. If this is the case then you can help out by testing the updated flatpak and adding more information to an existing issue! Usually just getting more testers on a new version is enough to help the maintainers! 

The bot will autoclose issues here, you can just work directly upstream, this issue is only a sign post!

### How to Update the Runtime on Flathub

The runtime for this flatpak appears to be outdated. **For app maintainers**, please follow the official Flathub process:

#### Step 1: Update Your Manifest
1. Edit your app's manifest file (e.g., `{package.flatpak_id.replace('app/', '')}.json` or `.yml`)
2. Update the `runtime` field from `{package.current_runtime}` to `{package.latest_runtime}`
3. Update the `runtime-version` field if using separate version specification

#### Step 2: Update SDK (if needed)
- If your app uses an SDK, update it to match the new runtime version
- For GNOME apps: change `org.gnome.Sdk` to the same version as the Platform
- For Freedesktop apps: change `org.freedesktop.Sdk` to match the Platform version

#### Step 3: Test and Submit
1. Test your app locally with the new runtime:
   ```bash
   flatpak-builder build-dir {package.flatpak_id.replace('app/', '')}.json --force-clean
   flatpak-builder --run build-dir {package.flatpak_id.replace('app/', '')}.json your-app-command
   ```
2. Create a pull request to your app's repository on the [flathub GitHub organization](https://github.com/flathub)
3. The Flathub build system will automatically test and build your update

### Documentation References

- [Flathub Runtime Updates Guide](https://docs.flathub.org/docs/for-app-authors/maintenance#runtime-updates)
- [Flatpak Manifest Reference](https://docs.flatpak.org/en/latest/manifests.html)
- [Flathub Submission Guidelines](https://docs.flathub.org/docs/for-app-authors/submission)

### For Users

This runtime update will be handled by the app maintainers. Once updated on Flathub, you can get the latest version with:
```bash
flatpak update {package.flatpak_id.replace('app/', '')}
```

### Additional Information

This issue was automatically created by the flatpak-updater bot that monitors multiple ublue-os flatpak lists:
- [ublue-os/bluefin system-flatpaks.list](https://github.com/ublue-os/bluefin/blob/main/flatpaks/system-flatpaks.list)
- [ublue-os/aurora system-flatpaks.list](https://github.com/ublue-os/aurora/blob/main/flatpaks/system-flatpaks.list)  
- [ublue-os/bazzite gnome flatpaks](https://github.com/ublue-os/bazzite/blob/main/installer/gnome_flatpaks/flatpaks)
- [ublue-os/bazzite kde flatpaks](https://github.com/ublue-os/bazzite/blob/main/installer/kde_flatpaks/flatpaks)
- [ublue-os/bluefin bazaar config](https://github.com/ublue-os/bluefin/blob/main/system_files/shared/etc/bazaar/config.yaml)
- [ublue-os/aurora bazaar config](https://github.com/ublue-os/aurora/blob/main/system_files/shared/etc/bazaar/config.yaml)
- [ublue-os/bazzite bazaar config](https://github.com/ublue-os/bazzite/blob/main/system_files/desktop/shared/usr/share/ublue-os/bazaar/config.yaml)

If this is a false positive or the runtime is intentionally pinned to an older version for compatibility reasons, please close this issue with a comment explaining why.
""".strip()
    
    def find_existing_issue(self, flatpak_id: str) -> Optional[any]:
        """Find an existing issue for the given flatpak ID using exact matching."""
        try:
            existing_issues = self.repo.get_issues(state='open')
            for issue in existing_issues:
                extracted_id = self.extract_flatpak_id_from_issue_title(issue.title)
                if extracted_id == flatpak_id:
                    logger.info(f"Found existing issue for {flatpak_id}: #{issue.number}")
                    return issue
            return None
        except Exception as e:
            logger.error(f"Error checking existing issues: {e}")
            return None
    
    def create_or_update_issue(self, package: OutdatedPackage, is_popular: bool = False) -> bool:
        """Create a GitHub issue for an outdated package or update existing one."""
        issue_title = f"Update runtime for {package.flatpak_id}"
        
        # Check if issue already exists
        existing_issue = self.find_existing_issue(package.flatpak_id)
        
        # Generate body content
        body = self.create_issue_body(package)
        
        labels = []
        if is_popular:
            labels.append("popular")
        
        # Add runtime version label
        runtime_label = self._get_runtime_label(package.latest_runtime)
        if runtime_label:
            labels.append(runtime_label)

        if existing_issue:
            # Update existing issue
            try:
                # Check if the issue content needs updating
                current_body = existing_issue.body or ""
                
                # Extract current runtime info from existing issue to check if update is needed
                current_runtime_match = re.search(r'\*\*Current Runtime:\*\* `([^`]+)`', current_body)
                current_runtime_in_issue = current_runtime_match.group(1) if current_runtime_match else None
                
                latest_runtime_match = re.search(r'\*\*Latest Available Runtime:\*\* `([^`]+)`', current_body)
                latest_runtime_in_issue = latest_runtime_match.group(1) if latest_runtime_match else None
                
                # Update if runtime information has changed
                needs_update = (
                    current_runtime_in_issue != package.current_runtime or
                    latest_runtime_in_issue != package.latest_runtime
                )
                
                if needs_update:
                    existing_issue.edit(title=issue_title, body=body)
                    logger.info(f"Updated existing issue #{existing_issue.number} for {package.flatpak_id}")
                    
                    # Add a comment indicating the issue was updated
                    update_comment = f"""
🔄 **Issue Updated**

This issue has been automatically updated with the latest runtime information:
- **Current Runtime**: `{package.current_runtime}`  
- **Latest Available Runtime**: `{package.latest_runtime}`

The runtime update instructions remain the same.

---
*This issue was automatically updated by the flatpak-updater bot.*
""".strip()
                    existing_issue.create_comment(update_comment)
                    
                    # Update labels
                    if is_popular:
                        existing_issue.add_to_labels("popular")
                    runtime_label = self._get_runtime_label(package.latest_runtime)
                    if runtime_label:
                        existing_issue.add_to_labels(runtime_label)
                    
                    return True
                else:
                    logger.info(f"Issue #{existing_issue.number} for {package.flatpak_id} is already up to date")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to update existing issue #{existing_issue.number} for {package.flatpak_id}: {e}")
                return False
        else:
            # Create new issue
            try:
                issue = self.repo.create_issue(
                    title=issue_title,
                    body=body,
                    labels=labels
                )
                logger.info(f"Created new issue #{issue.number} for {package.flatpak_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to create issue for {package.flatpak_id}: {e}")
                return False
    
    def close_resolved_issues(self, current_outdated_packages: List[str], all_tracked_packages: List[str]):
        """Close issues for flatpaks that are no longer outdated or no longer tracked."""
        logger.info("Checking for resolved runtime issues to close")
        
        try:
            open_issues = self.repo.get_issues(state='open')
            closed_count = 0
            
            for issue in open_issues:
                flatpak_id = self.extract_flatpak_id_from_issue_title(issue.title)
                if not flatpak_id:
                    logger.debug(f"Could not extract flatpak ID from issue #{issue.number}: {issue.title}")
                    continue
                
                # Check if this flatpak is no longer tracked at all
                if flatpak_id not in all_tracked_packages:
                    # This package is no longer being tracked in any source
                    close_comment = f"""
🔄 **Package No Longer Tracked**

This issue is being automatically closed because:
- The package `{flatpak_id}` is no longer included in any of the monitored flatpak lists
- We only track packages that are currently shipped in ublue-os distributions

**What this means:**
- This package was removed from the system flatpak lists in the source repositories
- Historical applications that are no longer shipped are automatically cleaned up

If this package should still be tracked, please verify it exists in one of these current lists:
- [ublue-os/bluefin system-flatpaks.list](https://github.com/ublue-os/bluefin/blob/main/flatpaks/system-flatpaks.list)
- [ublue-os/aurora system-flatpaks.list](https://github.com/ublue-os/aurora/blob/main/flatpaks/system-flatpaks.list)  
- [ublue-os/bazzite gnome flatpaks](https://github.com/ublue-os/bazzite/blob/main/installer/gnome_flatpaks/flatpaks)
- [ublue-os/bazzite kde flatpaks](https://github.com/ublue-os/bazzite/blob/main/installer/kde_flatpaks/flatpaks)
- [ublue-os/bluefin bazaar config](https://github.com/ublue-os/bluefin/blob/main/system_files/shared/usr/share/ublue-os/bazaar/config.yaml)
- [ublue-os/aurora bazaar config](https://github.com/ublue-os/aurora/blob/main/system_files/shared/usr/share/ublue-os/bazaar/config.yaml)
- [ublue-os/bazzite bazaar config](https://github.com/ublue-os/bazzite/blob/main/system_files/desktop/shared/usr/share/ublue-os/bazaar/config.yaml)

---
*This issue was automatically closed by the flatpak-updater bot.*
""".strip()
                    
                    try:
                        issue.create_comment(close_comment)
                        issue.edit(state='closed')
                        logger.info(f"Closed issue #{issue.number} for no longer tracked package {flatpak_id}")
                        closed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to close issue #{issue.number} for {flatpak_id}: {e}")
                
                # Check if this flatpak is still tracked but no longer outdated
                elif flatpak_id not in current_outdated_packages:
                    # This package is still tracked but runtime is now up to date
                    close_comment = f"""
🎉 **Runtime Issue Resolved!**

This issue is being automatically closed because:
- The runtime for `{flatpak_id}` is now up to date
- The package is still being tracked and monitored

If this was closed in error, please reopen the issue.

---
*This issue was automatically closed by the flatpak-updater bot.*
""".strip()
                    
                    try:
                        issue.create_comment(close_comment)
                        issue.edit(state='closed')
                        logger.info(f"Closed resolved issue #{issue.number} for {flatpak_id}")
                        closed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to close issue #{issue.number} for {flatpak_id}: {e}")
            
            logger.info(f"Closed {closed_count} resolved or obsolete runtime issues")
            
        except Exception as e:
            logger.error(f"Failed to check for resolved issues: {e}")


def load_outdated_packages(file_path: str) -> Tuple[List[OutdatedPackage], List[str]]:
    """Load outdated packages from JSON file and return both outdated and all tracked packages."""
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
            
            # Fetch install count from Flathub
            try:
                # Remove 'app/' prefix for API call - Flathub API expects just the app ID
                app_id = package.flatpak_id[4:] if package.flatpak_id.startswith('app/') else package.flatpak_id
                response = requests.get(f"https://flathub.org/api/v2/stats/{app_id}")
                if response.status_code == 200:
                    stats = response.json()
                    package.monthly_downloads = stats.get('installs_last_month', 0)
                time.sleep(1) # Add a delay to avoid overwhelming Flathub
            except Exception as e:
                logger.warning(f"Could not fetch monthly download count for {package.flatpak_id}: {e}")

            packages.append(package)
        
        # Get all tracked packages for cleanup logic
        all_tracked_packages = data.get('all_tracked_packages', [])
        
        return packages, all_tracked_packages
        
    except Exception as e:
        logger.error(f"Failed to load outdated packages from {file_path}: {e}")
        return [], []


def group_packages_by_runtime(packages: List[OutdatedPackage]) -> Tuple[List[OutdatedPackage], List[OutdatedPackage], List[OutdatedPackage], List[OutdatedPackage]]:
    """Group packages by runtime type (GNOME, KDE, Freedesktop, Other).
    
    Args:
        packages: List of outdated packages to group
        
    Returns:
        Tuple of (gnome_packages, kde_packages, freedesktop_packages, other_packages)
    """
    gnome_packages = []
    kde_packages = []
    freedesktop_packages = []
    other_packages = []
    
    for package in packages:
        runtime_name = package.current_runtime.split('/')[0] if '/' in package.current_runtime else package.current_runtime
        if 'gnome' in runtime_name.lower():
            gnome_packages.append(package)
        elif 'kde' in runtime_name.lower():
            kde_packages.append(package)
        elif 'freedesktop' in runtime_name.lower():
            freedesktop_packages.append(package)
        else:
            other_packages.append(package)
    
    return gnome_packages, kde_packages, freedesktop_packages, other_packages


def identify_popular_packages(packages_by_runtime: Dict[str, List[OutdatedPackage]], top_n: int = 10) -> set:
    """Identify top N most downloaded packages for each runtime group.
    
    Args:
        packages_by_runtime: Dictionary mapping runtime names to package lists
        top_n: Number of top packages to mark as popular (default: 10)
        
    Returns:
        Set of flatpak IDs that should be marked as popular
    """
    popular_package_ids = set()
    
    for runtime_name, packages in packages_by_runtime.items():
        # Sort by monthly downloads (descending)
        sorted_packages = sorted(packages, key=lambda p: p.monthly_downloads, reverse=True)
        
        # Take top N packages (or all if fewer than N)
        for i, package in enumerate(sorted_packages[:top_n]):
            popular_package_ids.add(package.flatpak_id)
            logger.info(f"Popular {runtime_name} app #{i+1}: {package.flatpak_id} ({package.monthly_downloads} downloads/month)")
    
    return popular_package_ids


def main():
    """Main entry point for issue generation."""
    if len(sys.argv) != 2:
        logger.error("Usage: python issue_generator.py <outdated_packages.json>")
        sys.exit(1)
    
    outdated_file = sys.argv[1]
    
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
    
    # Load outdated packages and all tracked packages
    packages, all_tracked_packages = load_outdated_packages(outdated_file)
    if not packages and not all_tracked_packages:
        logger.info("No data found or failed to load file")
        sys.exit(0)
    
    logger.info(f"Found {len(packages)} outdated packages")
    logger.info(f"Tracking {len(all_tracked_packages)} total packages")
    
    # Group packages by runtime type
    gnome_packages, kde_packages, freedesktop_packages, other_packages = group_packages_by_runtime(packages)
    
    logger.info(f"Grouped packages: {len(gnome_packages)} GNOME, {len(kde_packages)} KDE, {len(freedesktop_packages)} Freedesktop, {len(other_packages)} other")
    
    # Identify popular packages (top 10 in each runtime group)
    # Note: other_packages (with unknown runtimes) are excluded from popular labeling
    # since they don't fit into the standard GNOME/KDE/Freedesktop categories
    packages_by_runtime = {
        'GNOME': gnome_packages,
        'KDE': kde_packages,
        'Freedesktop': freedesktop_packages
    }
    popular_package_ids = identify_popular_packages(packages_by_runtime, top_n=10)
    
    logger.info(f"Total popular packages: {len(popular_package_ids)}")
    
    # Initialize issue generator
    generator = IssueGenerator(github_token, repo_name)
    
    # Close resolved issues first - pass both lists
    current_outdated_flatpak_ids = [pkg.flatpak_id for pkg in packages]
    generator.close_resolved_issues(current_outdated_flatpak_ids, all_tracked_packages)
    
    # Create or update issues for outdated packages
    created_or_updated_count = 0
    for package in packages:
        is_popular = package.flatpak_id in popular_package_ids
        if generator.create_or_update_issue(package, is_popular):
            created_or_updated_count += 1
    
    logger.info(f"Created or updated {created_or_updated_count} issues for outdated packages")


if __name__ == '__main__':
    main()
