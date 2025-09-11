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
from typing import Dict, List, Optional
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
        labels = ['runtime-update', 'automated']
        
        # Add source labels
        for source in package.sources:
            labels.append(source)
        
        # Extract runtime information for labels
        if package.current_runtime and '/' in package.current_runtime:
            runtime_parts = package.current_runtime.split('/')
            runtime_name = runtime_parts[0]  # e.g., org.gnome.Platform
            
            # Add runtime-specific labels
            if 'gnome' in runtime_name.lower():
                labels.append('gnome')
            elif 'freedesktop' in runtime_name.lower():
                labels.append('freedesktop')
            elif 'kde' in runtime_name.lower():
                labels.append('kde')
            
            # Add version labels (sanitized for GitHub)
            if package.latest_version:
                # Replace dots with dashes for GitHub label compatibility
                safe_version = package.latest_version.replace('.', '-')
                labels.append(f'target-{safe_version}')
        
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

If this is a false positive or the runtime is intentionally pinned to an older version for compatibility reasons, please close this issue with a comment explaining why.
""".strip()
    
    def issue_exists(self, flatpak_id: str) -> bool:
        """Check if an issue already exists for the given flatpak ID."""
        try:
            existing_issues = self.repo.get_issues(state='open', labels=['runtime-update'])
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
    
    def close_resolved_issues(self, current_packages: List[str]):
        """Close issues for flatpaks that are no longer outdated or no longer tracked."""
        logger.info("Checking for resolved runtime issues to close")
        
        try:
            open_issues = self.repo.get_issues(state='open', labels=['runtime-update'])
            closed_count = 0
            
            for issue in open_issues:
                flatpak_id = self.extract_flatpak_id_from_issue_title(issue.title)
                if not flatpak_id:
                    logger.debug(f"Could not extract flatpak ID from issue #{issue.number}: {issue.title}")
                    continue
                
                # Check if this flatpak is still in our outdated list
                if flatpak_id not in current_packages:
                    # This package is no longer outdated or no longer tracked
                    close_comment = f"""
🎉 **Runtime Issue Resolved!**

This issue is being automatically closed because:
- The runtime for `{flatpak_id}` is now up to date, OR
- The package is no longer being tracked in the monitored flatpak lists

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
            
            logger.info(f"Closed {closed_count} resolved runtime issues")
            
        except Exception as e:
            logger.error(f"Failed to check for resolved issues: {e}")


def load_outdated_packages(file_path: str) -> List[OutdatedPackage]:
    """Load outdated packages from JSON file."""
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
        
        return packages
        
    except Exception as e:
        logger.error(f"Failed to load outdated packages from {file_path}: {e}")
        return []


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
    
    # Load outdated packages
    packages = load_outdated_packages(outdated_file)
    if not packages:
        logger.info("No outdated packages found or failed to load file")
        sys.exit(0)
    
    logger.info(f"Found {len(packages)} outdated packages")
    
    # Initialize issue generator
    generator = IssueGenerator(github_token, repo_name)
    
    # Close resolved issues first
    current_flatpak_ids = [pkg.flatpak_id for pkg in packages]
    generator.close_resolved_issues(current_flatpak_ids)
    
    # Create issues for outdated packages
    created_count = 0
    for package in packages:
        if generator.create_issue(package):
            created_count += 1
    
    logger.info(f"Created {created_count} new issues for outdated packages")


if __name__ == '__main__':
    main()