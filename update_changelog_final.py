#!/usr/bin/env python3
"""
Final CHANGELOG.md updater script.
Updates the CHANGELOG with proper tables for all workflow runs.
"""

import json
from datetime import datetime, timedelta

def generate_application_table(outdated_packages: list) -> str:
    """Generate a markdown table of outdated applications."""
    if not outdated_packages:
        return "*All applications were up to date in this run!*\n\n"
    
    table = "| Application Name | Flatpak ID | Current Runtime | Target Runtime |\n"
    table += "|------------------|------------|-----------------|----------------|\n"
    
    # Sort by flatpak_id for consistency
    sorted_packages = sorted(outdated_packages, key=lambda x: x['flatpak_id'])
    
    for pkg in sorted_packages:
        flatpak_id = pkg['flatpak_id']
        # Remove 'app/' prefix if present
        clean_id = flatpak_id.replace('app/', '')
        # Extract application name (last part after the last dot)
        app_name = clean_id.split('.')[-1]
        
        # Create Flathub GitHub link
        flathub_link = f"https://github.com/flathub/{clean_id}"
        linked_id = f"[{clean_id}]({flathub_link})"
        
        # Get runtime information
        current_runtime = pkg.get('current_runtime', 'Unknown')
        latest_runtime = pkg.get('latest_runtime', 'Unknown')
        current_version = pkg.get('current_version', '')
        latest_version = pkg.get('latest_version', '')
        
        # Format runtime display - show platform name and version
        if '/' in current_runtime:
            platform_name = current_runtime.split('/')[0]
            current_display = f"{platform_name} {current_version}"
        else:
            current_display = current_runtime
            
        if '/' in latest_runtime:
            platform_name = latest_runtime.split('/')[0]
            latest_display = f"{platform_name} {latest_version}"
        else:
            latest_display = latest_runtime
        
        table += f"| {app_name} | {linked_id} | {current_display} | {latest_display} |\n"
    
    table += "\n"
    return table


# Load the most recent data from temp_outdated.json
with open('temp_outdated.json', 'r') as f:
    recent_data = json.load(f)

# Generate the changelog
changelog = f"""# 📊 Flatpak Runtime Tracker
*Updated: November 01, 2025 at 19:03 UTC*

## Overview Statistics
*(Based on most recent scheduled run: 2025-10-27)*

| Metric | Count |
|--------|-------|
| **Total Applications Tracked** | {recent_data['total_checked']} |
| **✅ Up to Date** | {recent_data['total_checked'] - recent_data['outdated_count']} |
| **⏳ Need Updates** | {recent_data['outdated_count']} |
| **Compliance Rate** | {((recent_data['total_checked'] - recent_data['outdated_count']) / recent_data['total_checked'] * 100):.1f}% |

**Target Runtimes:**
- GNOME Platform: 49
- KDE Platform: 6.9
- Freedesktop Platform: 25.08

---

# Historical Updates

Below is a record of all scheduled workflow runs that have checked for runtime updates.

## Week of October 27 - November 02, 2025

**Run Date:** 2025-10-27  
**Run ID:** [18835461852](https://github.com/ublue-os/flatpak-tracker/actions/runs/18835461852)

{generate_application_table(recent_data['outdated_packages'])}
### Stats
- **Total**: {recent_data['total_checked']}
- **Up to Date:** {recent_data['total_checked'] - recent_data['outdated_count']}
- **Need Updates:** {recent_data['outdated_count']}
- **Success Rate:** {((recent_data['total_checked'] - recent_data['outdated_count']) / recent_data['total_checked'] * 100):.1f}%

### Summary
This scheduled workflow run checked {recent_data['total_checked']} flatpak applications across all ublue-os sources. {recent_data['outdated_count']} applications were found with outdated runtimes and issues were created or updated for each.

---

## Week of October 20 - October 26, 2025

**Run Date:** 2025-10-20  
**Run ID:** [18647358799](https://github.com/ublue-os/flatpak-tracker/actions/runs/18647358799)

*Artifact data not available for historical runs. To view complete application lists for past runs, check the workflow run logs linked above.*

### Summary
Scheduled workflow run completed successfully. Runtime checks were performed and issues were created/updated for applications with outdated runtimes.

View detailed logs and statistics in the [workflow run](https://github.com/ublue-os/flatpak-tracker/actions/runs/18647358799).

---

## Week of October 13 - October 19, 2025

**Run Date:** 2025-10-13  
**Run ID:** [18460651533](https://github.com/ublue-os/flatpak-tracker/actions/runs/18460651533)

*Artifact data not available for historical runs. To view complete application lists for past runs, check the workflow run logs linked above.*

### Summary
Scheduled workflow run completed successfully. Runtime checks were performed and issues were created/updated for applications with outdated runtimes.

View detailed logs and statistics in the [workflow run](https://github.com/ublue-os/flatpak-tracker/actions/runs/18460651533).

---

## Week of October 06 - October 12, 2025

**Run Date:** 2025-10-06  
**Run ID:** [18275667071](https://github.com/ublue-os/flatpak-tracker/actions/runs/18275667071)

*Artifact data not available for historical runs. To view complete application lists for past runs, check the workflow run logs linked above.*

### Summary
Scheduled workflow run completed successfully. Runtime checks were performed and issues were created/updated for applications with outdated runtimes.

View detailed logs and statistics in the [workflow run](https://github.com/ublue-os/flatpak-tracker/actions/runs/18275667071).

---

## Week of September 29 - October 05, 2025

**Run Date:** 2025-09-29  
**Run ID:** [18091671815](https://github.com/ublue-os/flatpak-tracker/actions/runs/18091671815)

*Artifact data not available for historical runs. To view complete application lists for past runs, check the workflow run logs linked above.*

### Summary
Scheduled workflow run completed successfully. Runtime checks were performed and issues were created/updated for applications with outdated runtimes.

View detailed logs and statistics in the [workflow run](https://github.com/ublue-os/flatpak-tracker/actions/runs/18091671815).

---

## Week of September 22 - September 28, 2025

**Run Date:** 2025-09-22  
**Run ID:** [17910235305](https://github.com/ublue-os/flatpak-tracker/actions/runs/17910235305)

*Artifact data not available for historical runs. To view complete application lists for past runs, check the workflow run logs linked above.*

### Summary
Scheduled workflow run completed successfully. Runtime checks were performed and issues were created/updated for applications with outdated runtimes.

View detailed logs and statistics in the [workflow run](https://github.com/ublue-os/flatpak-tracker/actions/runs/17910235305).

---

## Week of September 15 - September 21, 2025

**Run Date:** 2025-09-15  
**Run ID:** [17727778387](https://github.com/ublue-os/flatpak-tracker/actions/runs/17727778387)

*Artifact data not available for historical runs. To view complete application lists for past runs, check the workflow run logs linked above.*

### Summary
Scheduled workflow run completed successfully. Runtime checks were performed and issues were created/updated for applications with outdated runtimes.

View detailed logs and statistics in the [workflow run](https://github.com/ublue-os/flatpak-tracker/actions/runs/17727778387).

---

## Week of September 08 - September 14, 2025

**Run Date:** 2025-09-11  
**Run ID:** [17639534930](https://github.com/ublue-os/flatpak-tracker/actions/runs/17639534930)

*Artifact data not available for historical runs. To view complete application lists for past runs, check the workflow run logs linked above.*

### Summary
Scheduled workflow run completed successfully. Runtime checks were performed and issues were created/updated for applications with outdated runtimes.

View detailed logs and statistics in the [workflow run](https://github.com/ublue-os/flatpak-tracker/actions/runs/17639534930).

---



## How This Works

The Flatpak Runtime Tracker:
1. **Runs Weekly**: Executes every Monday at 9:00 AM UTC via GitHub Actions
2. **Monitors Sources**: Checks applications from ublue-os/bluefin, ublue-os/aurora, and ublue-os/bazzite
3. **Detects Outdated Runtimes**: Compares current runtime versions against latest available
4. **Creates Issues**: Automatically opens GitHub issues for applications needing updates
5. **Labels Priority**: Marks top 10 most downloaded apps per runtime as "popular"
6. **Closes Resolved**: Automatically closes issues when runtimes are updated

## Contributing

Help keep applications up to date! Check the [open issues](https://github.com/ublue-os/flatpak-tracker/issues?q=is%3Aissue+is%3Aopen) for applications that need runtime updates.

---

*This changelog is automatically maintained and updated with each scheduled workflow run.*
"""

# Write the changelog
with open('CHANGELOG.md', 'w') as f:
    f.write(changelog)

print("✅ Successfully updated CHANGELOG.md")
print(f"   - {recent_data['outdated_count']} applications listed in the most recent run")
print(f"   - All Flatpak IDs link to https://github.com/flathub/[app.id]")
print(f"   - Runtime upgrade information included for each application")
