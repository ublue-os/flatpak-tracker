#!/usr/bin/env python3
"""
Check donation metadata for flatpak packages and create issues for missing or unreachable donation links.
"""

import json
import logging
import os
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import requests
from github import Github

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class DonationInfo:
    """Information about a flatpak package's donation metadata."""
    flatpak_id: str
    sources: List[str]
    donation_url: Optional[str] = None
    url_reachable: Optional[bool] = None
    error_message: Optional[str] = None


class DonationMetadataChecker:
    """Check donation metadata for flatpak packages."""
    
    def __init__(self, github_token: str = None, repo_name: str = None):
        """Initialize the donation checker."""
        self.flathub_base_url = "https://flathub.org/api/v2/appstream"
        self.github_token = github_token
        self.repo_name = repo_name
        if github_token and repo_name:
            self.github = Github(github_token)
            self.repo = self.github.get_repo(repo_name)
        else:
            self.github = None
            self.repo = None
    
    def get_flatpak_info(self, flatpak_id: str) -> Optional[Dict]:
        """Get flatpak information from Flathub API."""
        app_id = flatpak_id.replace('app/', '')
        
        try:
            response = requests.get(f"{self.flathub_base_url}/{app_id}?locale=en", timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Could not fetch info for {app_id}: HTTP {response.status_code}")
                return None
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch info for {app_id}: {e}")
            return None
    
    def get_donation_url(self, flatpak_info: Dict) -> Optional[str]:
        """Extract donation URL from flatpak metadata."""
        try:
            if 'urls' in flatpak_info and 'donation' in flatpak_info['urls']:
                return flatpak_info['urls']['donation']
            return None
        except (KeyError, TypeError) as e:
            logger.debug(f"Could not extract donation URL: {e}")
            return None
    
    def is_gnome_or_kde_app(self, flatpak_id: str, flatpak_info: Dict) -> bool:
        """Check if the app is a GNOME or KDE application.
        
        GNOME and KDE have their own donation infrastructure, so we skip them.
        """
        app_id = flatpak_id.replace('app/', '')
        
        # Check by app ID prefix
        if app_id.startswith('org.gnome.') or app_id.startswith('org.kde.'):
            return True
        
        # Check by project group in metadata
        try:
            if 'project_group' in flatpak_info:
                project_group = flatpak_info['project_group'].lower()
                if project_group in ['gnome', 'kde']:
                    return True
        except (KeyError, TypeError, AttributeError):
            pass
        
        return False
    
    def is_commercial_or_closed_license(self, flatpak_info: Dict) -> bool:
        """Check if the app is commercial or has a closed/proprietary license.
        
        Commercial apps with closed licenses should not be tracked for donation links.
        """
        try:
            if 'project_license' in flatpak_info:
                license_str = flatpak_info['project_license'].lower()
                
                # Check for proprietary or closed license keywords
                proprietary_keywords = [
                    'proprietary',
                    'commercial',
                    'closed',
                    'all rights reserved',
                    'copyright only',
                    'licenseref-proprietary'
                ]
                
                for keyword in proprietary_keywords:
                    if keyword in license_str:
                        return True
        except (KeyError, TypeError, AttributeError):
            pass
        
        return False
    
    def should_skip_app(self, flatpak_id: str, flatpak_info: Dict) -> Tuple[bool, Optional[str]]:
        """Determine if an app should be skipped for donation checking.
        
        Returns:
            Tuple of (should_skip, reason)
        """
        # Check if it's a GNOME or KDE app
        if self.is_gnome_or_kde_app(flatpak_id, flatpak_info):
            return True, "GNOME/KDE app with own donation infrastructure"
        
        # Check if it's a commercial/closed license app
        if self.is_commercial_or_closed_license(flatpak_info):
            return True, "Commercial/closed-license application"
        
        return False, None
    
    def check_url_reachable(self, url: str) -> Tuple[bool, Optional[str]]:
        """Check if a URL is reachable."""
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code < 400:
                return True, None
            else:
                return False, f"HTTP {response.status_code}"
        except requests.RequestException as e:
            return False, str(e)
    
    def check_donation_metadata(self, flatpaks: Dict[str, any]) -> List[DonationInfo]:
        """Check donation metadata for all flatpaks."""
        missing_or_unreachable = []
        
        logger.info(f"Checking donation metadata for {len(flatpaks)} flatpaks...")
        
        for flatpak_id, flatpak_info_obj in flatpaks.items():
            logger.info(f"Checking {flatpak_id}...")
            
            # Get flatpak metadata from Flathub API
            flatpak_info = self.get_flatpak_info(flatpak_id)
            if not flatpak_info:
                logger.warning(f"Could not fetch metadata for {flatpak_id}, skipping")
                continue
            
            # Check if this app should be skipped (GNOME/KDE or commercial)
            should_skip, skip_reason = self.should_skip_app(flatpak_id, flatpak_info)
            if should_skip:
                logger.info(f"  ⏭️  Skipping {flatpak_id}: {skip_reason}")
                continue
            
            # Check for donation URL
            donation_url = self.get_donation_url(flatpak_info)
            
            if not donation_url:
                # No donation URL found
                donation_info = DonationInfo(
                    flatpak_id=flatpak_id,
                    sources=flatpak_info_obj.sources,
                    donation_url=None,
                    url_reachable=None,
                    error_message="No donation URL found in metadata"
                )
                missing_or_unreachable.append(donation_info)
                logger.info(f"  ❌ No donation URL for {flatpak_id}")
            else:
                # Check if donation URL is reachable
                is_reachable, error_msg = self.check_url_reachable(donation_url)
                
                if not is_reachable:
                    # Donation URL exists but is unreachable
                    donation_info = DonationInfo(
                        flatpak_id=flatpak_id,
                        sources=flatpak_info_obj.sources,
                        donation_url=donation_url,
                        url_reachable=False,
                        error_message=error_msg
                    )
                    missing_or_unreachable.append(donation_info)
                    logger.info(f"  ⚠️  Unreachable donation URL for {flatpak_id}: {donation_url} ({error_msg})")
                else:
                    logger.info(f"  ✅ Donation URL OK for {flatpak_id}: {donation_url}")
        
        logger.info(f"Found {len(missing_or_unreachable)} packages with missing or unreachable donation URLs")
        return missing_or_unreachable
    
    def create_issue_for_missing_donation(self, donation_info: DonationInfo):
        """Create a GitHub issue for a package with missing or unreachable donation link."""
        if not self.repo:
            logger.error("GitHub repository not initialized, cannot create issues")
            return False
        
        # Check if issue already exists
        if self.find_existing_donation_issue(donation_info.flatpak_id):
            logger.info(f"Issue already exists for {donation_info.flatpak_id}")
            return False
        
        app_id = donation_info.flatpak_id.replace('app/', '')
        
        if donation_info.donation_url is None:
            # Missing donation URL
            title = f"Donation Link missing for {app_id}"
            body = f"""## Missing Donation Link

**Package:** `{donation_info.flatpak_id}`
**Found in sources:** {', '.join(donation_info.sources)}

This flatpak package does not have a donation link in its metadata.

### Why This Matters

Donation links help users support the developers of the applications they use. Adding a donation link makes it easier for users to contribute to the project's development.

### How to Add a Donation Link

For app maintainers on Flathub:

1. Add a `<url type="donation">` entry to your AppStream metadata file (usually `*.appdata.xml` or `*.metainfo.xml`)
2. Example:
   ```xml
   <url type="donation">https://github.com/sponsors/your-username</url>
   ```
3. Submit a pull request to your app's Flathub repository

### Verification

You can verify the metadata at: https://flathub.org/api/v2/appstream/{app_id}?locale=en

Look for the `urls.donation` field in the JSON response.

---
*This issue was automatically created by the flatpak-tracker donation metadata checker.*
"""
        else:
            # Unreachable donation URL
            title = f"Donation Link unreachable for {app_id}"
            body = f"""## Unreachable Donation Link

**Package:** `{donation_info.flatpak_id}`
**Donation URL:** {donation_info.donation_url}
**Error:** {donation_info.error_message}
**Found in sources:** {', '.join(donation_info.sources)}

This flatpak package has a donation link in its metadata, but the URL appears to be unreachable.

### What This Means

The donation URL in the AppStream metadata returned an error when accessed. This could be due to:
- The URL being incorrect or outdated
- The server being temporarily down
- Network restrictions or redirects

### How to Fix

For app maintainers on Flathub:

1. Verify the donation URL is correct
2. Update the `<url type="donation">` entry in your AppStream metadata file
3. Submit a pull request to your app's Flathub repository

### Verification

You can verify the metadata at: https://flathub.org/api/v2/appstream/{app_id}?locale=en

Look for the `urls.donation` field in the JSON response.

---
*This issue was automatically created by the flatpak-tracker donation metadata checker.*
"""
        
        try:
            issue = self.repo.create_issue(title=title, body=body.strip(), labels=['donation-metadata'])
            logger.info(f"Created issue #{issue.number}: {title}")
            return True
        except Exception as e:
            logger.error(f"Failed to create issue for {donation_info.flatpak_id}: {e}")
            return False
    
    def find_existing_donation_issue(self, flatpak_id: str) -> Optional[any]:
        """Find an existing donation issue for the given flatpak ID."""
        if not self.repo:
            return None
        
        app_id = flatpak_id.replace('app/', '')
        
        try:
            open_issues = self.repo.get_issues(state='open', labels=['donation-metadata'])
            for issue in open_issues:
                if f"for {app_id}" in issue.title:
                    logger.info(f"Found existing donation issue for {flatpak_id}: #{issue.number}")
                    return issue
            return None
        except Exception as e:
            logger.error(f"Error checking existing issues: {e}")
            return None
    
    def close_filtered_issues(self, flatpaks: Dict[str, any]):
        """Close issues for apps that should now be filtered (GNOME/KDE or commercial).
        
        This ensures that existing issues for GNOME/KDE apps or commercial apps
        are automatically closed to focus on individual app maintainers.
        """
        if not self.repo:
            logger.warning("GitHub repository not initialized, cannot close issues")
            return
        
        logger.info("Checking for donation issues to close (filtered apps)...")
        
        try:
            open_issues = self.repo.get_issues(state='open', labels=['donation-metadata'])
            closed_count = 0
            
            for issue in open_issues:
                # Extract flatpak ID from issue title
                # Title format: "Donation Link missing for app.id" or "Donation Link unreachable for app.id"
                app_id = None
                if " for " in issue.title:
                    app_id = issue.title.split(" for ")[-1].strip()
                
                if not app_id:
                    logger.debug(f"Could not extract app ID from issue #{issue.number}: {issue.title}")
                    continue
                
                flatpak_id = f"app/{app_id}"
                
                # Check if this app is in our tracked list
                if flatpak_id not in flatpaks:
                    logger.debug(f"App {flatpak_id} from issue #{issue.number} not in tracked list")
                    continue
                
                # Get flatpak metadata to check if it should be filtered
                flatpak_info = self.get_flatpak_info(flatpak_id)
                if not flatpak_info:
                    logger.warning(f"Could not fetch metadata for {flatpak_id} to check filtering")
                    continue
                
                # Check if this app should be skipped
                should_skip, skip_reason = self.should_skip_app(flatpak_id, flatpak_info)
                
                if should_skip:
                    # This app should be filtered, close the issue
                    close_comment = f"""🔄 **Issue Automatically Closed**

This issue is being automatically closed because:
- {skip_reason}

**What this means:**
- This application type is now excluded from donation metadata tracking
- For GNOME/KDE apps: These projects have their own established donation infrastructure
- For commercial apps: Closed-source commercial applications are not expected to have open donation links

**Focusing on Individual Maintainers:**
The flatpak-tracker now focuses on checking donation metadata for individual open-source application maintainers who can benefit from having donation links.

If this was closed in error, please reopen the issue or contact the maintainers.

---
*This issue was automatically closed by the flatpak-tracker donation metadata checker.*
""".strip()
                    
                    try:
                        issue.create_comment(close_comment)
                        issue.edit(state='closed')
                        logger.info(f"Closed filtered issue #{issue.number} for {flatpak_id}: {skip_reason}")
                        closed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to close issue #{issue.number} for {flatpak_id}: {e}")
            
            if closed_count > 0:
                logger.info(f"Closed {closed_count} issue(s) for filtered apps")
            else:
                logger.info("No issues to close for filtered apps")
                
        except Exception as e:
            logger.error(f"Error while closing filtered issues: {e}")


def load_flatpaks_from_json(file_path: str) -> Dict[str, any]:
    """Load flatpak list from the JSON file created by check_flatpak_runtimes.py."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Convert to a simple dict structure
        flatpaks = {}
        for flatpak_id in data.get('all_tracked_packages', []):
            # Create a simple object with sources
            class SimpleInfo:
                def __init__(self):
                    self.sources = ['tracked']
            
            flatpaks[flatpak_id] = SimpleInfo()
        
        logger.info(f"Loaded {len(flatpaks)} flatpaks from {file_path}")
        return flatpaks
    except Exception as e:
        logger.error(f"Failed to load flatpaks from {file_path}: {e}")
        return {}


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check donation metadata for flatpak packages')
    parser.add_argument('--input', '-i', default='outdated_packages.json',
                       help='Input JSON file with flatpak list (default: outdated_packages.json)')
    parser.add_argument('--create-issues', action='store_true',
                       help='Create GitHub issues for missing/unreachable donation links')
    args = parser.parse_args()
    
    # Load flatpaks from the input file
    flatpaks = load_flatpaks_from_json(args.input)
    if not flatpaks:
        logger.error("No flatpaks found to check")
        return 1
    
    # Initialize checker
    github_token = os.environ.get('GITHUB_TOKEN')
    repo_name = os.environ.get('GITHUB_REPOSITORY')
    
    if args.create_issues:
        if not github_token or not repo_name:
            logger.error("GITHUB_TOKEN and GITHUB_REPOSITORY environment variables are required for creating issues")
            return 1
        checker = DonationMetadataChecker(github_token, repo_name)
    else:
        checker = DonationMetadataChecker()
    
    # Check donation metadata
    missing_or_unreachable = checker.check_donation_metadata(flatpaks)
    
    # Print summary
    print("\n" + "="*60)
    print(f"SUMMARY: {len(missing_or_unreachable)} packages with issues")
    print("="*60)
    
    missing_count = sum(1 for d in missing_or_unreachable if d.donation_url is None)
    unreachable_count = len(missing_or_unreachable) - missing_count
    
    print(f"Missing donation URL: {missing_count}")
    print(f"Unreachable donation URL: {unreachable_count}")
    
    if missing_or_unreachable:
        print("\nPackages with issues:")
        for donation_info in missing_or_unreachable:
            app_id = donation_info.flatpak_id.replace('app/', '')
            if donation_info.donation_url is None:
                print(f"  - {app_id}: No donation URL")
            else:
                print(f"  - {app_id}: Unreachable ({donation_info.error_message})")
    
    # Create issues if requested
    if args.create_issues and missing_or_unreachable:
        print("\n" + "="*60)
        print("Creating GitHub issues...")
        print("="*60)
        created_count = 0
        for donation_info in missing_or_unreachable:
            if checker.create_issue_for_missing_donation(donation_info):
                created_count += 1
        print(f"\nCreated {created_count} new issues")
    
    # Close issues for filtered apps (GNOME/KDE or commercial)
    if args.create_issues:
        print("\n" + "="*60)
        print("Checking for issues to close (filtered apps)...")
        print("="*60)
        checker.close_filtered_issues(flatpaks)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
