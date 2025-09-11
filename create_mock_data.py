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
        "total_checked": 5,
        "outdated_count": 3,
        "outdated_packages": [
            {
                "flatpak_id": "app/org.gnome.Calculator",
                "sources": ["bluefin", "aurora"],
                "current_runtime": "org.gnome.Platform/x86_64/46",
                "latest_runtime": "org.gnome.Platform/x86_64/48",
                "current_version": "46",
                "latest_version": "48"
            },
            {
                "flatpak_id": "app/org.mozilla.firefox",
                "sources": ["bluefin"],
                "current_runtime": "org.freedesktop.Platform/x86_64/22.08",
                "latest_runtime": "org.freedesktop.Platform/x86_64/24.08",
                "current_version": "22.08",
                "latest_version": "24.08"
            },
            {
                "flatpak_id": "app/org.kde.krita",
                "sources": ["bazzite-gnome", "bazzite-kde"],
                "current_runtime": "org.kde.Platform/x86_64/6.6",
                "latest_runtime": "org.kde.Platform/x86_64/6.8",
                "current_version": "6.6",
                "latest_version": "6.8"
            }
        ]
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