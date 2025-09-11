#!/usr/bin/env python3
"""
Check flatpak runtime updates for packages from ublue-os/bluefin system-flatpaks.list
and create GitHub issues for outdated packages.
"""

import os
import re
import subprocess
import sys
import json
import logging
from typing import Dict, List, Set, Optional, Tuple, NamedTuple
from dataclasses import dataclass
import requests
import yaml


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
    def __init__(self, output_file: str = None):
        self.flathub_base_url = "https://flathub.org/api/v2/appstream"
        self.output_file = output_file or "outdated_packages.json"
        
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
            },
            # Bazaar config sources
            'bluefin-bazaar': {
                'url': 'https://raw.githubusercontent.com/ublue-os/bluefin/main/system_files/shared/usr/share/ublue-os/bazaar/config.yaml',
                'format': 'bazaar_yaml'  # YAML format with appids in sections
            },
            'aurora-bazaar': {
                'url': 'https://raw.githubusercontent.com/ublue-os/aurora/main/system_files/shared/usr/share/ublue-os/bazaar/config.yaml',
                'format': 'bazaar_yaml'  # YAML format with appids in sections
            },
            'bazzite-bazaar': {
                'url': 'https://raw.githubusercontent.com/ublue-os/bazzite/main/system_files/desktop/shared/usr/share/ublue-os/bazaar/config.yaml',
                'format': 'bazaar_yaml'  # YAML format with appids in sections
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
                
                if source_config['format'] == 'bazaar_yaml':
                    # Parse YAML and extract appids from all sections
                    source_flatpaks = self._parse_bazaar_yaml(response.text)
                else:
                    # Handle existing list formats
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
            except Exception as e:
                logger.error(f"Error processing {source_name}: {e}")
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
    
    def _parse_bazaar_yaml(self, yaml_content: str) -> List[str]:
        """Parse bazaar config YAML and extract all appids from all sections."""
        try:
            # Parse the YAML content
            config = yaml.safe_load(yaml_content)
            
            flatpaks = []
            
            # The bazaar config has a 'sections' key containing a list of sections
            if isinstance(config, dict) and 'sections' in config:
                sections = config['sections']
                if isinstance(sections, list):
                    for section in sections:
                        if isinstance(section, dict) and 'appids' in section:
                            appids = section['appids']
                            if isinstance(appids, list):
                                for app_id in appids:
                                    if isinstance(app_id, str) and app_id.strip():
                                        # Convert to app/package.id format
                                        app_id = app_id.strip()
                                        if not app_id.startswith('app/'):
                                            app_id = f"app/{app_id}"
                                        flatpaks.append(app_id)
            
            logger.debug(f"Parsed {len(flatpaks)} flatpaks from bazaar YAML")
            return flatpaks
            
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing bazaar YAML: {e}")
            return []
    
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
            'org.kde.Platform': '6.9',  # KDE 6.9 is current
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
    
    def save_outdated_packages(self, outdated_packages: List[Dict], all_tracked_flatpaks: Dict[str, any]):
        """Save outdated packages to JSON file for issue generation."""
        # Convert all tracked flatpaks to a list for easier processing
        all_tracked_list = list(all_tracked_flatpaks.keys())
        
        output_data = {
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "total_checked": getattr(self, '_total_checked', 0),
            "outdated_count": len(outdated_packages),
            "outdated_packages": outdated_packages,
            "all_tracked_packages": all_tracked_list
        }
        
        try:
            with open(self.output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            logger.info(f"Saved {len(outdated_packages)} outdated packages to {self.output_file}")
            logger.info(f"Total tracked packages: {len(all_tracked_list)}")
        except Exception as e:
            logger.error(f"Failed to save outdated packages: {e}")
            sys.exit(1)
    
    def check_runtime_updates(self):
        """Main method to check for runtime updates and save outdated packages to JSON."""
        logger.info("Starting flatpak runtime update check")
        
        # Fetch flatpak dictionary from multiple sources
        flatpak_dict = self.fetch_flatpak_list()
        app_flatpaks = self.get_app_flatpaks(flatpak_dict)
        
        logger.info(f"Checking {len(app_flatpaks)} unique app flatpaks for runtime updates")
        self._total_checked = len(app_flatpaks)
        
        outdated_packages = []
        
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
                
                # Add to outdated packages list
                outdated_package = {
                    "flatpak_id": flatpak_id,
                    "sources": flatpak_info.sources,
                    "current_runtime": current_runtime,
                    "latest_runtime": latest_runtime,
                    "current_version": current_version,
                    "latest_version": latest_version
                }
                outdated_packages.append(outdated_package)
            else:
                logger.info(f"{flatpak_id} runtime is up to date")
        
        logger.info(f"Runtime check complete. Found {len(outdated_packages)} outdated runtimes")
        
        # Save outdated packages to JSON file
        self.save_outdated_packages(outdated_packages, app_flatpaks)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check for flatpak runtime updates')
    parser.add_argument('--output', '-o', default='outdated_packages.json',
                       help='Output JSON file for outdated packages (default: outdated_packages.json)')
    args = parser.parse_args()
    
    checker = FlatpakRuntimeChecker(output_file=args.output)
    checker.check_runtime_updates()


if __name__ == '__main__':
    main()
