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
    
    def generate_issue_labels(self, package: OutdatedPackage) -> List[str]:
        """Generate comprehensive labels for GitHub issues."""
        labels = ['runtime']
        
        # Check if package is from default sources (system flatpak lists)
        # vs bazaar sources (user-configurable)
        default_sources = {'bluefin', 'aurora', 'bazzite-gnome', 'bazzite-kde'}
        has_default_source = any(source in default_sources for source in package.sources)
        
        if has_default_source:
            labels.append('default')
        
        # Extract runtime information for labels
        if package.current_runtime and '/' in package.current_runtime:
            runtime_parts = package.current_runtime.split('/')
            runtime_name = runtime_parts[0]  # e.g., org.gnome.Platform
            
            # Generate combined runtime-version labels following Flathub convention
            runtime_label = None
            if 'gnome' in runtime_name.lower():
                runtime_label = 'gnome'
            elif 'freedesktop' in runtime_name.lower():
                runtime_label = 'freedesktop'
            elif 'kde' in runtime_name.lower():
                runtime_label = 'kde'
            
            # Combine runtime with version if we have both
            if runtime_label and package.latest_version:
                # Replace dots with dashes for GitHub label compatibility
                safe_version = package.latest_version.replace('.', '-')
                combined_label = f'{runtime_label}-{safe_version}'
                labels.append(combined_label)
            elif runtime_label:
                # Fallback to just runtime if no version available
                labels.append(runtime_label)
        
        return labels
    
    def create_issue_body(self, package: OutdatedPackage) -> str:
        """Generate the issue body content."""
        sources_info = ', '.join(package.sources)
        
        return f"""
## Flatpak Runtime Update Needed

**Package:** `{package.flatpak_id}`
**Current Runtime:** `{package.current_runtime}`
**Latest Available Runtime:** `{package.latest_runtime}`
**Found in sources:** {sources_info}

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
- [ublue-os/bluefin bazaar config](https://github.com/ublue-os/bluefin/blob/main/system_files/shared/usr/share/ublue-os/bazaar/config.yaml)
- [ublue-os/aurora bazaar config](https://github.com/ublue-os/aurora/blob/main/system_files/shared/usr/share/ublue-os/bazaar/config.yaml)
- [ublue-os/bazzite bazaar config](https://github.com/ublue-os/bazzite/blob/main/system_files/desktop/shared/usr/share/ublue-os/bazaar/config.yaml)

If this is a false positive or the runtime is intentionally pinned to an older version for compatibility reasons, please close this issue with a comment explaining why.
""".strip()
    
    def issue_exists(self, flatpak_id: str) -> bool:
        """Check if an issue already exists for the given flatpak ID."""
        try:
            existing_issues = self.repo.get_issues(state='open', labels=['runtime'])
            for issue in existing_issues:
                if flatpak_id in issue.title:
                    logger.info(f"Issue already exists for {flatpak_id}: #{issue.number}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking existing issues: {e}")
            return True  # Assume it exists to avoid duplicates on error
    
    def create_issue(self, package: OutdatedPackage) -> bool:
        """Create a GitHub issue for an outdated package."""
        issue_title = f"Update runtime for {package.flatpak_id}"
        
        # Check if issue already exists
        if self.issue_exists(package.flatpak_id):
            return False
        
        # Generate labels and body
        labels = self.generate_issue_labels(package)
        body = self.create_issue_body(package)
        
        try:
            issue = self.repo.create_issue(
                title=issue_title,
                body=body,
                labels=labels
            )
            logger.info(f"Created issue #{issue.number} for {package.flatpak_id} with labels: {', '.join(labels)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create issue for {package.flatpak_id}: {e}")
            return False
    
    def close_resolved_issues(self, current_outdated_packages: List[str], all_tracked_packages: List[str]):
        """Close issues for flatpaks that are no longer outdated or no longer tracked."""
        logger.info("Checking for resolved runtime issues to close")
        
        try:
            open_issues = self.repo.get_issues(state='open', labels=['runtime'])
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
            packages.append(package)
        
        # Get all tracked packages for cleanup logic
        all_tracked_packages = data.get('all_tracked_packages', [])
        
        return packages, all_tracked_packages
        
    except Exception as e:
        logger.error(f"Failed to load outdated packages from {file_path}: {e}")
        return [], []


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
    
    # Initialize issue generator
    generator = IssueGenerator(github_token, repo_name)
    
    # Close resolved issues first - pass both lists
    current_outdated_flatpak_ids = [pkg.flatpak_id for pkg in packages]
    generator.close_resolved_issues(current_outdated_flatpak_ids, all_tracked_packages)
    
    # Create issues for outdated packages
    created_count = 0
    for package in packages:
        if generator.create_issue(package):
            created_count += 1
    
    logger.info(f"Created {created_count} new issues for outdated packages")


if __name__ == '__main__':
    main()