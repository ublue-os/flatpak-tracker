# CHANGELOG Helper Scripts

This directory contains several helper scripts for maintaining and updating the CHANGELOG.md file.

## Scripts

### `update_changelog_final.py`
**Purpose**: Main script used to update CHANGELOG.md with complete application tables.

**Usage**:
```bash
python update_changelog_final.py
```

**What it does**:
- Reads data from `temp_outdated.json` (the most recent run data)
- Generates a comprehensive table listing all 77 outdated applications
- Each Flatpak ID is linked to its GitHub Flathub repository
- Shows current and target runtimes for each application
- Updates CHANGELOG.md with the formatted content

**Output**: Updated CHANGELOG.md with complete application tables

### `backfill_changelog_with_tables.py`
**Purpose**: Comprehensive backfill script that downloads artifacts from all workflow runs and generates complete historical data.

**Requirements**:
- `GITHUB_TOKEN` environment variable
- `GITHUB_REPOSITORY` environment variable (defaults to ublue-os/flatpak-tracker)

**Usage**:
```bash
export GITHUB_TOKEN="your_github_token"
export GITHUB_REPOSITORY="ublue-os/flatpak-tracker"
python backfill_changelog_with_tables.py
```

**What it does**:
- Fetches all scheduled workflow runs from GitHub Actions
- Downloads artifacts (outdated_packages.json) from each run
- Generates a detailed table for each workflow run
- Creates a complete historical changelog with all applications listed

### `update_changelog_tables.py`
**Purpose**: Format guide and example generator showing the expected table format.

**Usage**:
```bash
python update_changelog_tables.py
```

**What it does**:
- Demonstrates the expected format for CHANGELOG tables
- Shows examples using data from `temp_outdated.json`
- Provides a template for manual updates
- Useful for understanding the table structure

### `prepare_backfill_data.py`
**Purpose**: Prepares workflow run information for the backfill process.

**Usage**:
```bash
python prepare_backfill_data.py
```

**What it does**:
- Lists all workflow runs that need to be processed
- Saves workflow run information to `workflow_runs.json`
- Provides guidance for downloading artifacts

## Table Format

Each weekly section in CHANGELOG.md follows this format:

```markdown
## Week of [Month Day] - [Month Day, Year]

**Run Date:** YYYY-MM-DD  
**Run ID:** [run_id](https://github.com/ublue-os/flatpak-tracker/actions/runs/run_id)

| Application Name | Flatpak ID | Current Runtime | Target Runtime |
|------------------|------------|-----------------|----------------|
| AppName | [org.example.AppName](https://github.com/flathub/org.example.AppName) | org.gnome.Platform 48 | org.gnome.Platform 49 |

### Stats
- **Total**: XXX
- **Up to Date:** XXX
- **Need Updates:** XXX
- **Success Rate:** XX.X%

### Summary
This scheduled workflow run checked XXX flatpak applications across all ublue-os sources...
```

## Key Features

### Proper Flathub Links
All Flatpak IDs link to their respective GitHub Flathub repositories:
- Format: `https://github.com/flathub/[flatpak.id]`
- Example: `https://github.com/flathub/org.mozilla.firefox`

### Runtime Information
Each entry shows:
- **Current Runtime**: The runtime version currently in use
- **Target Runtime**: The latest available runtime version
- Example: `org.freedesktop.Platform 24.08` → `org.freedesktop.Platform 25.08`

### Application Names
- Extracted from the last part of the Flatpak ID
- Example: `org.mozilla.firefox` → `firefox`

## Data Sources

### Primary Data
- `temp_outdated.json`: Contains the most recent run data with 77 outdated packages
- Workflow artifacts: Each scheduled run uploads an artifact with outdated package data

### Workflow Runs
The scripts process data from these scheduled workflow runs:
- Run 18835461852 (2025-10-27)
- Run 18647358799 (2025-10-20)
- Run 18460651533 (2025-10-13)
- Run 18275667071 (2025-10-06)
- Run 18091671815 (2025-09-29)
- Run 17910235305 (2025-09-22)
- Run 17727778387 (2025-09-15)
- Run 17639534930 (2025-09-11)

## Maintenance

### Adding New Weeks
When a new scheduled workflow run completes:
1. The workflow uploads an artifact with `outdated_packages.json`
2. Run `backfill_changelog_with_tables.py` with `GITHUB_TOKEN` to fetch and process new data
3. Alternatively, manually update using the format template from `update_changelog_tables.py`

### Validating Changes
To validate the CHANGELOG format:
```python
# Check link count
grep -c "https://github.com/flathub/" CHANGELOG.md

# Check table headers
grep "Application Name | Flatpak ID | Current Runtime | Target Runtime" CHANGELOG.md

# Verify specific applications
grep "org.mozilla.firefox" CHANGELOG.md
```

## Requirements

### Python Dependencies
```
requests>=2.31.0
PyGithub>=1.59.0
PyYAML>=6.0.2
```

Install with:
```bash
pip install -r requirements.txt
```

### System Requirements
- Python 3.8 or higher
- Git (for viewing diffs and managing changes)
- Internet access (for downloading artifacts)

## Troubleshooting

### "GITHUB_TOKEN environment variable is required"
Set the token before running:
```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

### "No artifact found for run"
Some workflow runs may not have artifacts available:
- Artifacts expire after 30 days by default
- Check if the artifact exists in the workflow run page
- Use the placeholder text for historical runs without artifacts

### "Module not found"
Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Contributing

When updating these scripts:
1. Maintain the existing table format
2. Ensure all Flatpak IDs link to `github.com/flathub`
3. Test with `temp_outdated.json` before running on live data
4. Validate the output using the validation script examples above

## License

These scripts are part of the flatpak-tracker project and follow the same license as the main repository (Apache 2.0).
