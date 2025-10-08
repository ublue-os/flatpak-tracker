#!/usr/bin/env python3
"""
Create mock data for testing the issue generator locally.
This script generates a test JSON file with sample outdated packages.
"""

import json
from datetime import datetime

def create_mock_data():
    """Create mock outdated packages data for testing."""
    mock_data = {
        "timestamp": datetime.now().isoformat(),
        "total_checked": 8,
        "outdated_count": 4,
        "outdated_packages": [
            {
                "flatpak_id": "app/org.gnome.Calculator",
                "sources": ["bluefin", "aurora"],  # DEFAULT sources
                "current_runtime": "org.gnome.Platform/x86_64/46",
                "latest_runtime": "org.gnome.Platform/x86_64/48",
                "current_version": "46",
                "latest_version": "48"
            },
            {
                "flatpak_id": "app/org.mozilla.firefox",
                "sources": ["bluefin"],  # DEFAULT source
                "current_runtime": "org.freedesktop.Platform/x86_64/22.08",
                "latest_runtime": "org.freedesktop.Platform/x86_64/24.08",
                "current_version": "22.08",
                "latest_version": "24.08"
            },
            {
                "flatpak_id": "app/org.kde.krita",
                "sources": ["bazzite-gnome", "bazzite-kde"],  # DEFAULT sources
                "current_runtime": "org.kde.Platform/x86_64/6.6",
                "latest_runtime": "org.kde.Platform/x86_64/6.8",
                "current_version": "6.6",
                "latest_version": "6.8"
            },
            {
                "flatpak_id": "app/com.example.BazaarApp",
                "sources": ["bluefin-bazaar", "aurora-bazaar"],  # NON-DEFAULT sources (bazaar only)
                "current_runtime": "org.gnome.Platform/x86_64/47",
                "latest_runtime": "org.gnome.Platform/x86_64/48",
                "current_version": "47",
                "latest_version": "48"
            }
        ],
        "all_tracked_packages": [
            "app/org.gnome.Calculator",
            "app/org.mozilla.firefox", 
            "app/org.kde.krita",
            "app/com.example.BazaarApp",
            "app/org.gnome.TextEditor",  # tracked but not outdated
            "app/org.gimp.GIMP",         # tracked but not outdated
            "app/org.libreoffice.LibreOffice",  # tracked but not outdated
            "app/com.spotify.Client"     # tracked but not outdated
        ],
        "all_tracked_packages_with_sources": {
            "app/org.gnome.Calculator": {"sources": ["bluefin", "aurora"]},
            "app/org.mozilla.firefox": {"sources": ["bluefin"]},
            "app/org.kde.krita": {"sources": ["bazzite-gnome", "bazzite-kde"]},
            "app/com.example.BazaarApp": {"sources": ["bluefin-bazaar", "aurora-bazaar"]},
            "app/org.gnome.TextEditor": {"sources": ["bluefin"]},
            "app/org.gimp.GIMP": {"sources": ["aurora"]},
            "app/org.libreoffice.LibreOffice": {"sources": ["bazzite-gnome"]},
            "app/com.spotify.Client": {"sources": ["bluefin", "bazzite-gnome"]}
        }
    }
    
    return mock_data

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Create mock outdated packages data for testing')
    parser.add_argument('--output', '-o', default='mock_outdated.json',
                       help='Output JSON file for mock data (default: mock_outdated.json)')
    args = parser.parse_args()
    
    mock_data = create_mock_data()
    
    with open(args.output, 'w') as f:
        json.dump(mock_data, f, indent=2)
    
    print(f"Created mock data in {args.output}")
    print(f"Total packages: {mock_data['total_checked']}")
    print(f"Outdated packages: {mock_data['outdated_count']}")
    print("\nTo test issue generation (requires valid GitHub credentials):")
    print(f"  export GITHUB_TOKEN='your_token'")
    print(f"  export GITHUB_REPOSITORY='owner/repo'")
    print(f"  python issue_generator.py {args.output}")

if __name__ == '__main__':
    main()