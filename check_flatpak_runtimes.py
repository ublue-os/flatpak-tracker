#!/usr/bin/env python3
"""
Check flatpak runtime updates for packages from ublue-os/bluefin system-flatpaks.list
and create GitHub issues for outdated packages.
"""

import os
import re
import subprocess
import sys
import logging
from typing import Dict, List, Set, Optional, Tuple
from github import Github
import requests


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FlatpakRuntimeChecker:
    def __init__(self, github_token: str, repo_name: str):
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repo_name)
        self.flathub_base_url = "https://flathub.org/api/v2/appstream"
        
    def fetch_flatpak_list(self) -> List[str]:
        """Fetch the list of flatpaks from ublue-os/bluefin repository."""
        url = "https://raw.githubusercontent.com/ublue-os/bluefin/main/flatpaks/system-flatpaks.list"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            flatpaks = []
            for line in response.text.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    flatpaks.append(line)
            
            logger.info(f"Fetched {len(flatpaks)} flatpaks from bluefin list")
            return flatpaks
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch flatpak list: {e}")
            sys.exit(1)
    
    def get_app_flatpaks(self, flatpaks: List[str]) -> List[str]:
        """Filter to get only app flatpaks (not runtimes)."""
        return [fp for fp in flatpaks if fp.startswith('app/')]
    
    def get_flatpak_info(self, flatpak_id: str) -> Optional[Dict]:
        """Get flatpak information from Flathub API."""
        # Remove 'app/' prefix for API call
        app_id = flatpak_id.replace('app/', '')
        
        try:
            response = requests.get(f"{self.flathub_base_url}/{app_id}", timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Could not fetch info for {app_id}: HTTP {response.status_code}")
                return None
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch info for {app_id}: {e}")
            return None
    
    def get_runtime_from_flatpak_info(self, flatpak_info: Dict) -> Optional[str]:
        """Extract runtime information from flatpak metadata."""
        try:
            # Look for runtime in bundle information
            if 'bundle' in flatpak_info:
                bundle = flatpak_info['bundle']
                if 'runtime' in bundle:
                    return bundle['runtime']
            
            # Alternative: check in metadata
            if 'metadata' in flatpak_info:
                metadata = flatpak_info['metadata']
                if 'runtime' in metadata:
                    return metadata['runtime']
                    
            return None
        except (KeyError, TypeError) as e:
            logger.debug(f"Could not extract runtime info: {e}")
            return None
    
    def get_available_runtime_versions(self, runtime_name: str) -> List[str]:
        """Get available versions of a runtime from flathub."""
        try:
            # Use flatpak command to search for runtime versions
            cmd = ['flatpak', 'remote-ls', '--runtime', 'flathub', '--columns=name,version', runtime_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                versions = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 2 and parts[0].strip() == runtime_name:
                            versions.append(parts[1].strip())
                return versions
            else:
                logger.debug(f"Could not list runtime versions for {runtime_name}")
                return []
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout while checking runtime versions for {runtime_name}")
            return []
        except Exception as e:
            logger.debug(f"Error checking runtime versions for {runtime_name}: {e}")
            return []
    
    def compare_versions(self, current: str, latest: str) -> bool:
        """Compare version strings to determine if current is outdated."""
        try:
            # Simple version comparison for common patterns
            # This is a basic implementation - real version comparison is complex
            current_parts = [int(x) for x in current.split('.') if x.isdigit()]
            latest_parts = [int(x) for x in latest.split('.') if x.isdigit()]
            
            # Pad shorter version with zeros
            max_len = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            latest_parts.extend([0] * (max_len - len(latest_parts)))
            
            return current_parts < latest_parts
        except (ValueError, TypeError):
            # If we can't parse versions, assume string comparison
            return current != latest
    
    def create_or_update_issue(self, flatpak_id: str, current_runtime: str, latest_runtime: str):
        """Create or update a GitHub issue for an outdated flatpak."""
        issue_title = f"Update runtime for {flatpak_id}"
        
        # Check if issue already exists
        existing_issues = self.repo.get_issues(state='open')
        for issue in existing_issues:
            if flatpak_id in issue.title:
                logger.info(f"Issue already exists for {flatpak_id}: #{issue.number}")
                return
        
        issue_body = f"""
## Flatpak Runtime Update Needed

**Package:** `{flatpak_id}`
**Current Runtime:** `{current_runtime}`
**Latest Available Runtime:** `{latest_runtime}`

### How to Update

The runtime for this flatpak appears to be outdated. To update it:

1. **For maintainers of the flatpak:**
   - Update the `runtime` field in your flatpak manifest
   - Change from `{current_runtime}` to `{latest_runtime}`
   - Test the application with the new runtime
   - Submit an update to Flathub

2. **For users experiencing issues:**
   - This is typically handled by the app maintainers
   - You can try updating with: `flatpak update {flatpak_id.replace('app/', '')}`

### Additional Information

This issue was automatically created by the flatpak-updater bot that monitors the [ublue-os/bluefin system-flatpaks.list](https://github.com/ublue-os/bluefin/blob/main/flatpaks/system-flatpaks.list).

If this is a false positive or the runtime is intentionally pinned to an older version, please close this issue with a comment explaining why.
"""

        try:
            issue = self.repo.create_issue(
                title=issue_title,
                body=issue_body.strip(),
                labels=['runtime-update', 'automated']
            )
            logger.info(f"Created issue #{issue.number} for {flatpak_id}")
            
        except Exception as e:
            logger.error(f"Failed to create issue for {flatpak_id}: {e}")
    
    def check_runtime_updates(self):
        """Main method to check for runtime updates and create issues."""
        logger.info("Starting flatpak runtime update check")
        
        # Fetch flatpak list
        flatpaks = self.fetch_flatpak_list()
        app_flatpaks = self.get_app_flatpaks(flatpaks)
        
        logger.info(f"Checking {len(app_flatpaks)} app flatpaks for runtime updates")
        
        outdated_count = 0
        
        for flatpak_id in app_flatpaks:
            logger.info(f"Checking {flatpak_id}")
            
            # Get flatpak information
            flatpak_info = self.get_flatpak_info(flatpak_id)
            if not flatpak_info:
                logger.warning(f"Could not get info for {flatpak_id}, skipping")
                continue
            
            # Extract runtime information
            current_runtime = self.get_runtime_from_flatpak_info(flatpak_info)
            if not current_runtime:
                logger.warning(f"Could not determine runtime for {flatpak_id}, skipping")
                continue
            
            logger.info(f"{flatpak_id} uses runtime: {current_runtime}")
            
            # Get available runtime versions
            runtime_name = current_runtime.split('/')[0] if '/' in current_runtime else current_runtime
            available_versions = self.get_available_runtime_versions(runtime_name)
            
            if not available_versions:
                logger.warning(f"Could not get available versions for runtime {runtime_name}")
                continue
            
            # Find the latest version
            latest_version = max(available_versions) if available_versions else None
            if not latest_version:
                continue
                
            # Extract current version for comparison
            current_version = current_runtime.split('/')[-1] if '/' in current_runtime else current_runtime
            
            # Compare versions
            if self.compare_versions(current_version, latest_version):
                logger.info(f"Runtime update available for {flatpak_id}: {current_version} -> {latest_version}")
                latest_runtime = current_runtime.replace(current_version, latest_version)
                self.create_or_update_issue(flatpak_id, current_runtime, latest_runtime)
                outdated_count += 1
            else:
                logger.info(f"{flatpak_id} runtime is up to date")
        
        logger.info(f"Runtime check complete. Found {outdated_count} outdated runtimes")


def main():
    """Main entry point."""
    github_token = os.environ.get('GITHUB_TOKEN')
    repo_name = os.environ.get('GITHUB_REPOSITORY')
    
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is required")
        sys.exit(1)
        
    if not repo_name:
        logger.error("GITHUB_REPOSITORY environment variable is required")
        sys.exit(1)
    
    checker = FlatpakRuntimeChecker(github_token, repo_name)
    checker.check_runtime_updates()


if __name__ == '__main__':
    main()