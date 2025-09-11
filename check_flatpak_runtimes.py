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
from typing import Dict, List, Set, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from github import Github
import requests


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class FlatpakInfo:
    """Information about a flatpak package from multiple sources."""
    flatpak_id: str
    sources: List[str]  # ['bluefin', 'bazzite-gnome', 'aurora', etc.]
    runtime_info: Optional[Dict] = None
    current_runtime: Optional[str] = None


class FlatpakRuntimeChecker:
    def __init__(self, github_token: str, repo_name: str):
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repo_name)
        self.flathub_base_url = "https://flathub.org/api/v2/appstream"
        
    def fetch_flatpak_list(self) -> Dict[str, FlatpakInfo]:
        """Fetch and merge flatpak lists from multiple ublue-os sources with deduplication."""
        
        # Define all sources with their URLs and formats
        sources = {
            'bluefin': {
                'url': 'https://raw.githubusercontent.com/ublue-os/bluefin/main/flatpaks/system-flatpaks.list',
                'format': 'app_prefix'  # already has app/ prefix
            },
            'aurora': {
                'url': 'https://raw.githubusercontent.com/ublue-os/aurora/main/flatpaks/system-flatpaks.list', 
                'format': 'no_prefix'  # needs app/ prefix added
            },
            'bazzite-gnome': {
                'url': 'https://raw.githubusercontent.com/ublue-os/bazzite/main/installer/gnome_flatpaks/flatpaks',
                'format': 'full_ref'  # app/package/arch/branch format
            },
            'bazzite-kde': {
                'url': 'https://raw.githubusercontent.com/ublue-os/bazzite/main/installer/kde_flatpaks/flatpaks',
                'format': 'full_ref'  # app/package/arch/branch format
            }
        }
        
        # Dictionary to store deduplicated flatpaks with source tracking
        flatpak_dict = {}
        
        for source_name, source_config in sources.items():
            logger.info(f"Fetching flatpaks from {source_name}")
            
            try:
                response = requests.get(source_config['url'], timeout=30)
                response.raise_for_status()
                
                source_flatpaks = []
                for line in response.text.strip().split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Normalize to app/package.id format
                        if source_config['format'] == 'app_prefix':
                            # Already correct format: app/package.id
                            flatpak_id = line
                        elif source_config['format'] == 'no_prefix':
                            # Add app/ prefix: package.id -> app/package.id
                            flatpak_id = f"app/{line}"
                        elif source_config['format'] == 'full_ref':
                            # Extract package ID: app/package.id/arch/branch -> app/package.id
                            parts = line.split('/')
                            if len(parts) >= 2:
                                flatpak_id = f"{parts[0]}/{parts[1]}"
                            else:
                                flatpak_id = line
                        else:
                            flatpak_id = line
                        
                        # Only include app flatpaks (not runtimes)
                        if flatpak_id.startswith('app/'):
                            source_flatpaks.append(flatpak_id)
                
                logger.info(f"Found {len(source_flatpaks)} flatpaks from {source_name}")
                
                # Add to deduplicated dictionary
                for flatpak_id in source_flatpaks:
                    if flatpak_id in flatpak_dict:
                        # Flatpak already exists, add this source
                        flatpak_dict[flatpak_id].sources.append(source_name)
                    else:
                        # New flatpak
                        flatpak_dict[flatpak_id] = FlatpakInfo(
                            flatpak_id=flatpak_id,
                            sources=[source_name]
                        )
                        
            except requests.RequestException as e:
                logger.error(f"Failed to fetch flatpak list from {source_name}: {e}")
                # Continue with other sources instead of failing completely
                continue
        
        total_unique = len(flatpak_dict)
        total_sources = sum(len(info.sources) for info in flatpak_dict.values())
        logger.info(f"Combined total: {total_unique} unique flatpaks from {total_sources} source entries")
        
        # Log some statistics
        source_counts = {}
        for info in flatpak_dict.values():
            for source in info.sources:
                source_counts[source] = source_counts.get(source, 0) + 1
        
        for source, count in source_counts.items():
            logger.info(f"  {source}: {count} flatpaks")
        
        return flatpak_dict
    
    def get_app_flatpaks(self, flatpak_dict: Dict[str, FlatpakInfo]) -> Dict[str, FlatpakInfo]:
        """Filter to get only app flatpaks (not runtimes) - all should already be apps."""
        return {fid: info for fid, info in flatpak_dict.items() if fid.startswith('app/')}
    
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
        """Get available versions of a runtime from flathub using API and known current versions."""
        
        # Known current runtime versions as of 2024/2025
        # These are updated periodically and represent the latest stable versions
        # TODO: Update these versions when new stable releases are available
        # - Check GNOME release schedule: https://wiki.gnome.org/ReleasePlanning
        # - Check Freedesktop SDK releases: https://gitlab.com/freedesktop-sdk/freedesktop-sdk
        # - Check KDE release schedule: https://community.kde.org/Schedules
        known_latest_versions = {
            'org.gnome.Platform': '48',  # GNOME 48 is current stable as of 2024
            'org.freedesktop.Platform': '24.08',  # Freedesktop 24.08 is current
            'org.kde.Platform': '6.8',  # KDE 6.8 is current
        }
        
        # First, try to use the known latest version for common runtimes
        if runtime_name in known_latest_versions:
            latest_version = known_latest_versions[runtime_name]
            logger.info(f"Using known latest version {latest_version} for runtime {runtime_name}")
            return [latest_version]
        
        # Fallback: try to get runtime information from Flathub API
        try:
            api_url = f"https://flathub.org/api/v2/appstream/{runtime_name}"
            response = requests.get(api_url, timeout=30)
            if response.status_code == 200:
                runtime_info = response.json()
                # Try to extract version information from the API response
                if 'bundle' in runtime_info and 'runtime' in runtime_info['bundle']:
                    runtime_ref = runtime_info['bundle']['runtime']
                    # Extract version from runtime reference (e.g., "org.gnome.Platform/x86_64/47" -> "47")
                    if '/' in runtime_ref:
                        version = runtime_ref.split('/')[-1]
                        return [version]
        except requests.RequestException as e:
            logger.debug(f"Could not fetch runtime info from API for {runtime_name}: {e}")
        
        # Final fallback: try flatpak command (kept for environments where it might work)
        try:
            cmd = ['flatpak', 'remote-ls', '--runtime', 'flathub', '--columns=name,version', runtime_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                versions = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 2 and parts[0].strip() == runtime_name:
                            versions.append(parts[1].strip())
                if versions:
                    return versions
                    
        except Exception as e:
            logger.debug(f"Flatpak command failed for {runtime_name}: {e}")
            
        logger.warning(f"Could not determine latest version for runtime {runtime_name}")
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
    
    def extract_flatpak_id_from_issue_title(self, issue_title: str) -> Optional[str]:
        """Extract flatpak ID from issue title."""
        # Issue titles are in format: "Update runtime for app/org.example.App"
        match = re.search(r'Update runtime for (app/[^\s]+)', issue_title)
        if match:
            return match.group(1)
        return None
    
    def generate_issue_labels(self, flatpak_info: FlatpakInfo, current_runtime: str) -> List[str]:
        """Generate comprehensive labels for GitHub issues."""
        labels = ['runtime-update', 'automated']
        
        # Add source labels
        for source in flatpak_info.sources:
            labels.append(f'source-{source}')
        
        # Extract runtime information for labels
        if current_runtime and '/' in current_runtime:
            runtime_parts = current_runtime.split('/')
            runtime_name = runtime_parts[0]  # e.g., org.gnome.Platform
            runtime_version = runtime_parts[-1]  # e.g., 48 or 24.08
            
            # Add runtime-specific labels
            if 'gnome' in runtime_name.lower():
                labels.append('runtime-gnome')
            elif 'freedesktop' in runtime_name.lower():
                labels.append('runtime-freedesktop')
            elif 'kde' in runtime_name.lower():
                labels.append('runtime-kde')
            
            # Add version labels (sanitized for GitHub)
            if runtime_version:
                # Replace dots with dashes for GitHub label compatibility
                safe_version = runtime_version.replace('.', '-')
                labels.append(f'version-{safe_version}')
        
        return labels
    
    def close_resolved_issues(self, flatpak_dict: Dict[str, FlatpakInfo]):
        """Close issues for flatpaks that are now up to date."""
        logger.info("Checking for resolved runtime issues to close")
        
        # Get all open issues with runtime-update label
        try:
            open_issues = self.repo.get_issues(state='open', labels=['runtime-update'])
            
            closed_count = 0
            for issue in open_issues:
                flatpak_id = self.extract_flatpak_id_from_issue_title(issue.title)
                if not flatpak_id:
                    logger.debug(f"Could not extract flatpak ID from issue #{issue.number}: {issue.title}")
                    continue
                
                # Check if this flatpak still exists in our current list
                if flatpak_id not in flatpak_dict:
                    logger.warning(f"Flatpak {flatpak_id} from issue #{issue.number} no longer in source lists")
                    continue
                
                logger.info(f"Checking if issue #{issue.number} for {flatpak_id} should be closed")
                
                # Get current flatpak information
                flatpak_info = self.get_flatpak_info(flatpak_id)
                if not flatpak_info:
                    logger.warning(f"Could not get info for {flatpak_id} when checking issue #{issue.number}")
                    continue
                
                # Extract runtime information
                current_runtime = self.get_runtime_from_flatpak_info(flatpak_info)
                if not current_runtime:
                    logger.warning(f"Could not determine runtime for {flatpak_id} when checking issue #{issue.number}")
                    continue
                
                # Get available runtime versions
                runtime_name = current_runtime.split('/')[0] if '/' in current_runtime else current_runtime
                available_versions = self.get_available_runtime_versions(runtime_name)
                
                if not available_versions:
                    logger.warning(f"Could not get available versions for runtime {runtime_name} when checking issue #{issue.number}")
                    continue
                
                # Find the latest version
                latest_version = max(available_versions) if available_versions else None
                if not latest_version:
                    continue
                    
                # Extract current version for comparison
                current_version = current_runtime.split('/')[-1] if '/' in current_runtime else current_runtime
                
                # Check if runtime is now up to date
                if not self.compare_versions(current_version, latest_version):
                    # Runtime is now up to date, close the issue
                    close_comment = f"""
🎉 **Runtime Updated Successfully!**

The runtime for `{flatpak_id}` has been updated and is now up to date:
- **Current Runtime:** `{current_runtime}`
- **Latest Available:** `{latest_version}`

This issue is being automatically closed as the runtime update has been completed.

Thank you to the maintainers for keeping the flatpak up to date! 

---
*This issue was automatically closed by the flatpak-updater bot.*
"""
                    
                    try:
                        issue.create_comment(close_comment.strip())
                        issue.edit(state='closed')
                        logger.info(f"Closed resolved issue #{issue.number} for {flatpak_id}")
                        closed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to close issue #{issue.number} for {flatpak_id}: {e}")
                else:
                    logger.info(f"Issue #{issue.number} for {flatpak_id} is still valid (runtime outdated)")
            
            logger.info(f"Closed {closed_count} resolved runtime issues")
            
        except Exception as e:
            logger.error(f"Failed to check for resolved issues: {e}")
    
    def create_or_update_issue(self, flatpak_info: FlatpakInfo, current_runtime: str, latest_runtime: str):
        """Create or update a GitHub issue for an outdated flatpak with comprehensive labeling."""
        flatpak_id = flatpak_info.flatpak_id
        issue_title = f"Update runtime for {flatpak_id}"
        
        # Check if issue already exists
        existing_issues = self.repo.get_issues(state='open', labels=['runtime-update'])
        for issue in existing_issues:
            if flatpak_id in issue.title:
                logger.info(f"Issue already exists for {flatpak_id}: #{issue.number}")
                return
        
        # Generate comprehensive labels
        labels = self.generate_issue_labels(flatpak_info, current_runtime)
        
        # Create sources information for issue body
        sources_info = ', '.join(flatpak_info.sources)
        
        issue_body = f"""
## Flatpak Runtime Update Needed

**Package:** `{flatpak_id}`
**Current Runtime:** `{current_runtime}`
**Latest Available Runtime:** `{latest_runtime}`
**Found in sources:** {sources_info}

### How to Update the Runtime on Flathub

The runtime for this flatpak appears to be outdated. **For app maintainers**, please follow the official Flathub process:

#### Step 1: Update Your Manifest
1. Edit your app's manifest file (e.g., `{flatpak_id.replace('app/', '')}.json` or `.yml`)
2. Update the `runtime` field from `{current_runtime}` to `{latest_runtime}`
3. Update the `runtime-version` field if using separate version specification

#### Step 2: Update SDK (if needed)
- If your app uses an SDK, update it to match the new runtime version
- For GNOME apps: change `org.gnome.Sdk` to the same version as the Platform
- For Freedesktop apps: change `org.freedesktop.Sdk` to match the Platform version

#### Step 3: Test and Submit
1. Test your app locally with the new runtime:
   ```bash
   flatpak-builder build-dir {flatpak_id.replace('app/', '')}.json --force-clean
   flatpak-builder --run build-dir {flatpak_id.replace('app/', '')}.json your-app-command
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
flatpak update {flatpak_id.replace('app/', '')}
```

### Additional Information

This issue was automatically created by the flatpak-updater bot that monitors multiple ublue-os flatpak lists:
- [ublue-os/bluefin system-flatpaks.list](https://github.com/ublue-os/bluefin/blob/main/flatpaks/system-flatpaks.list)
- [ublue-os/aurora system-flatpaks.list](https://github.com/ublue-os/aurora/blob/main/flatpaks/system-flatpaks.list)  
- [ublue-os/bazzite gnome flatpaks](https://github.com/ublue-os/bazzite/blob/main/installer/gnome_flatpaks/flatpaks)
- [ublue-os/bazzite kde flatpaks](https://github.com/ublue-os/bazzite/blob/main/installer/kde_flatpaks/flatpaks)

If this is a false positive or the runtime is intentionally pinned to an older version for compatibility reasons, please close this issue with a comment explaining why.
"""

        try:
            issue = self.repo.create_issue(
                title=issue_title,
                body=issue_body.strip(),
                labels=labels
            )
            logger.info(f"Created issue #{issue.number} for {flatpak_id} with labels: {', '.join(labels)}")
            
        except Exception as e:
            logger.error(f"Failed to create issue for {flatpak_id}: {e}")
    
    def check_runtime_updates(self):
        """Main method to check for runtime updates and create issues."""
        logger.info("Starting flatpak runtime update check")
        
        # Fetch flatpak dictionary from multiple sources
        flatpak_dict = self.fetch_flatpak_list()
        app_flatpaks = self.get_app_flatpaks(flatpak_dict)
        
        logger.info(f"Checking {len(app_flatpaks)} unique app flatpaks for runtime updates")
        
        # First, close any issues for flatpaks that are now up to date
        self.close_resolved_issues(flatpak_dict)
        
        outdated_count = 0
        
        for flatpak_id, flatpak_info in app_flatpaks.items():
            logger.info(f"Checking {flatpak_id} (from: {', '.join(flatpak_info.sources)})")
            
            # Get flatpak information
            runtime_info = self.get_flatpak_info(flatpak_id)
            if not runtime_info:
                logger.warning(f"Could not get info for {flatpak_id}, skipping")
                continue
            
            # Store runtime info in our data structure for potential future use
            flatpak_info.runtime_info = runtime_info
            
            # Extract runtime information
            current_runtime = self.get_runtime_from_flatpak_info(runtime_info)
            if not current_runtime:
                logger.warning(f"Could not determine runtime for {flatpak_id}, skipping")
                continue
            
            # Store current runtime info
            flatpak_info.current_runtime = current_runtime
            
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
                self.create_or_update_issue(flatpak_info, current_runtime, latest_runtime)
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