# Flatpak Tracker

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

Flatpak Tracker is a Python-based GitHub Actions tool that monitors flatpak packages from multiple ublue-os sources (bluefin, aurora, bazzite) for:
1. **Outdated runtimes** - Automatically creates GitHub issues when runtime updates are available
2. **Missing donation metadata** - Identifies packages without donation links or with unreachable donation URLs
3. **Historical tracking** - Generates and maintains a changelog of runtime updates over time

The tool fetches download statistics from Flathub and labels the most popular applications. It also publishes a Jekyll-based website (GitHub Pages) that displays the current state and historical updates.

## Working Effectively

### Bootstrap and Dependencies
- Install Python dependencies: `pip install -r requirements.txt` -- installs requests>=2.31.0, PyGithub>=1.59.0, and PyYAML>=6.0.2
- Install system dependencies: `sudo apt-get update && sudo apt-get install -y flatpak`
- Add flathub remote: `sudo flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo` -- may fail in restricted network environments due to firewall limitations
- Validate Python syntax: `python -m py_compile check_flatpak_runtimes.py issue_generator.py`

### Running the Application
- **CRITICAL**: Set required environment variables before running:
  - `export GITHUB_TOKEN=<your_github_token>`
  - `export GITHUB_REPOSITORY=<owner/repo>`

#### Runtime Updates Workflow
- Run the main script: `python check_flatpak_runtimes.py --output outdated_packages.json` -- generates JSON output with outdated packages
- Run issue generator: `python issue_generator.py outdated_packages.json` -- creates/updates GitHub issues with popular labels
- **Manual workflow trigger**: Use GitHub Actions UI to trigger "Check Flatpak Runtime Updates" workflow
- **Automated schedule**: Runs weekly on Mondays at 9 AM UTC via GitHub Actions

#### Donation Metadata Workflow
- Generate flatpak list first: `python check_flatpak_runtimes.py --output flatpak_list.json`
- Dry run (no issues created): `python check_donation_metadata.py --input flatpak_list.json`
- Create issues: `python check_donation_metadata.py --input flatpak_list.json --create-issues`
- **Manual workflow trigger**: Use GitHub Actions UI to trigger "Check Donation Metadata" workflow
- **Automated schedule**: Runs weekly on Mondays at 10 AM UTC via GitHub Actions

#### Changelog Generation Workflow
- Generate changelog: `python generate_changelog.py outdated_packages.json`
- **Manual workflow trigger**: Use GitHub Actions UI to trigger "Generate Changelog" workflow
- **Automated schedule**: Runs weekly on Mondays at 11 AM UTC (2 hours after runtime check)
- **Output**: Updates CHANGELOG.md and commits it back to the repository

### Build and Test
- **No traditional build process** - this is a Python script that runs directly
- **No unit tests** - validation is done by running the script itself and end-to-end tests
- Syntax validation: `python -m py_compile check_flatpak_runtimes.py issue_generator.py check_donation_metadata.py generate_changelog.py`
- **No linting configuration** - no flake8, pylint, or other linting tools configured
- Test external API access: `curl -s "https://raw.githubusercontent.com/ublue-os/bluefin/main/flatpaks/system-flatpaks.list" | head -5`
- End-to-end test: Create and run a test script to validate the complete workflow (see "End-to-End Testing" section below)

### Jekyll Website
- **Purpose**: GitHub Pages site displaying current runtime status and historical changelog
- **Source files**: `index.md`, `about.md`, `_config.yml`, `_layouts/`, `_includes/`
- **Deployment**: Automatic via GitHub Actions on push to main branch
- **URL**: https://ublue-os.github.io/flatpak-tracker
- **Content**: Uses `index.md` which includes content from `CHANGELOG.md`
- **Theme**: Jekyll with custom layouts
- **Testing locally**: `bundle exec jekyll serve` (requires Ruby and bundler)

## Validation Scenarios

### Always Test These After Making Changes
1. **Dependency installation**: Run `pip install -r requirements.txt` and verify no errors
2. **Script compilation**: Run `python -m py_compile check_flatpak_runtimes.py issue_generator.py check_donation_metadata.py generate_changelog.py` and verify no syntax errors
3. **Flatpak installation**: Run `flatpak --version` to verify flatpak is installed and working (optional - fallback mechanisms exist)
4. **External API connectivity**: Test `curl -s "https://flathub.org/api/v2/appstream/org.gnome.Calculator"` -- may fail in restricted networks with name resolution errors
5. **Flatpak list retrieval**: Test `curl -s "https://raw.githubusercontent.com/ublue-os/bluefin/main/flatpaks/system-flatpaks.list"` -- should return package names
6. **Flathub stats API**: Test `curl -s "https://flathub.org/api/v2/stats/app/org.mozilla.firefox"` -- fetches download statistics (may fail in restricted networks)
7. **Workflow configuration**: Verify all workflow files have correct permissions and triggers

### Network Restriction Handling
- **Flathub remote setup may fail** due to firewall limitations - document this as expected in restricted environments
- **External API calls may timeout** - the script includes proper error handling for this
- **Do not attempt to bypass network restrictions** - document limitations instead

### Manual Testing Limitations
- **Cannot fully test issue creation** without valid GitHub token and appropriate repository permissions
- **Cannot test flatpak runtime queries** without flathub remote setup (network dependent)
- **Focus validation on syntax, dependencies, and accessible external APIs**

## Common Tasks

### Repository Structure
```
.
├── .github/
│   ├── copilot-instructions.md              # This file - instructions for Copilot
│   └── workflows/
│       ├── check-flatpak-runtimes.yml       # Runtime update checker workflow (Mon 9 AM UTC)
│       ├── check-donation-metadata.yml      # Donation metadata checker workflow (Mon 10 AM UTC)
│       ├── generate-changelog.yml           # Changelog generator workflow (Mon 11 AM UTC)
│       └── jekyll-gh-pages.yml              # Jekyll site deployment (on push to main)
├── _config.yml                               # Jekyll configuration for GitHub Pages
├── _includes/                                # Jekyll include files
├── _layouts/                                 # Jekyll layout files
│   └── default.html                          # Main layout template
├── public/                                   # Public assets (CSS, etc.)
├── .gitignore                                # Python/IDE/OS ignores
├── LICENSE                                   # Apache 2.0 license
├── README.md                                 # Project documentation (for developers)
├── CHANGELOG.md                              # Auto-generated changelog (also used by website)
├── index.md                                  # Jekyll website home page
├── about.md                                  # Jekyll website about page
├── check_flatpak_runtimes.py                # Runtime checker - generates JSON output
├── issue_generator.py                        # Issue creation with popular labeling
├── check_donation_metadata.py               # Donation metadata checker
├── generate_changelog.py                     # Changelog generator from workflow artifacts
├── requirements.txt                          # Python dependencies
├── temp_outdated.json                        # Sample data for testing (77 packages)
├── test_outdated.json                        # Minimal test data (1 package)
└── renovate.json                             # Renovate bot configuration
```

### Key Script Functions

#### check_flatpak_runtimes.py
- `fetch_flatpak_list()` - Retrieves and merges package lists from multiple ublue-os sources
- `get_flatpak_info()` - Queries Flathub API for package metadata
- `get_runtime_from_flatpak_info()` - Extracts runtime information
- `compare_versions()` - Determines if runtime updates are available
- `save_outdated_packages()` - Outputs JSON file with outdated packages

#### issue_generator.py
- `load_outdated_packages()` - Loads JSON and fetches download stats from Flathub
- `group_packages_by_runtime()` - Groups packages by runtime type (GNOME, KDE, Freedesktop)
- `identify_popular_packages()` - Identifies top 10 most downloaded per runtime
- `create_or_update_issue()` - Creates/updates GitHub issues with popular labels
- `close_resolved_issues()` - Closes issues for packages that are no longer outdated

#### check_donation_metadata.py
- `get_flatpak_info()` - Queries Flathub API for package metadata
- `get_donation_url()` - Extracts donation URL from metadata
- `check_url_reachable()` - Verifies donation URL is accessible
- `is_gnome_or_kde_app()` - Filters out GNOME/KDE apps (they have their own donation infrastructure)
- `is_commercial_or_closed_license()` - Filters out commercial/closed-source apps
- `check_donation_metadata()` - Main function that checks all packages
- `create_issue_for_missing_donation()` - Creates GitHub issues for missing/unreachable donation links
- `close_filtered_issues()` - Closes issues for apps now filtered (GNOME/KDE/commercial)

#### generate_changelog.py
- `fetch_historical_workflow_runs()` - Fetches scheduled workflow runs for backfilling
- `download_artifact_data()` - Downloads outdated_packages.json from workflow artifacts
- `build_historical_snapshots()` - Builds historical data from previous runs
- `detect_changes_between_snapshots()` - Identifies updated/added/removed packages
- `generate_dashboard_section()` - Creates overview statistics section
- `generate_changelog_section()` - Creates weekly changelog entry
- `generate_changelog()` - Main function that updates CHANGELOG.md

### GitHub Actions Workflows

#### 1. Check Flatpak Runtime Updates (check-flatpak-runtimes.yml)
- **Trigger**: Weekly on Mondays at 9 AM UTC (`0 9 * * 1`) or manual dispatch
- **Runtime**: ubuntu-latest with Python 3.14
- **Permissions**: issues:write, contents:read
- **Dependencies**: Installs flatpak system package and Python requirements
- **Duration**: Typically completes in 5-10 minutes depending on API response times and number of packages
- **Steps**:
  1. Checkout repository
  2. Install Python and dependencies
  3. Install flatpak system tools
  4. Run check_flatpak_runtimes.py to generate outdated_packages.json
  5. Display outdated packages summary
  6. Run issue_generator.py to create/update issues with popular labels
  7. Upload JSON data as artifact (retention: 30 days)

#### 2. Check Donation Metadata (check-donation-metadata.yml)
- **Trigger**: Weekly on Mondays at 10 AM UTC (`0 10 * * 1`) or manual dispatch
- **Runtime**: ubuntu-latest with Python 3.14
- **Permissions**: issues:write, contents:read
- **Duration**: Varies based on number of packages to check
- **Steps**:
  1. Checkout repository
  2. Install Python and dependencies
  3. Generate flatpak list using check_flatpak_runtimes.py
  4. Check donation metadata (dry run first)
  5. Create issues for missing/unreachable donation links
  6. Upload flatpak list data as artifact (retention: 30 days)
- **Filtering**: Automatically skips GNOME/KDE apps and commercial/closed-source applications

#### 3. Generate Changelog (generate-changelog.yml)
- **Trigger**: Weekly on Mondays at 11 AM UTC (`0 11 * * 1`) or manual dispatch (2 hours after runtime check)
- **Runtime**: ubuntu-latest with Python 3.14
- **Permissions**: contents:write, issues:read
- **Duration**: 1-2 minutes
- **Steps**:
  1. Checkout repository
  2. Install Python and dependencies
  3. Download latest outdated-packages-data artifact
  4. Generate updated changelog
  5. Display changelog preview
  6. Commit and push CHANGELOG.md if changes exist
- **Behavior**: Prepends current week's update to existing changelog, maintaining historical data

#### 4. Deploy Jekyll Site (jekyll-gh-pages.yml)
- **Trigger**: On push to main branch or manual dispatch
- **Runtime**: ubuntu-latest
- **Permissions**: contents:read, pages:write, id-token:write
- **Duration**: 1-2 minutes
- **Steps**:
  1. Checkout repository
  2. Setup GitHub Pages
  3. Build with Jekyll
  4. Upload artifact
  5. Deploy to GitHub Pages
- **Output**: Published site at https://ublue-os.github.io/flatpak-tracker

### Environment Variables Required
- `GITHUB_TOKEN` - GitHub API token with issues:write permission
- `GITHUB_REPOSITORY` - Repository in format "owner/repo"

### External Dependencies
- **ublue-os/bluefin** - Primary source of flatpak package lists (system-flatpaks.list and bazaar config)
- **ublue-os/aurora** - Additional source of flatpak package lists
- **ublue-os/bazzite** - Gaming-focused flatpak package lists (GNOME and KDE variants)
- **Flathub API** - Package metadata, runtime information, and download statistics
  - `/api/v2/appstream/{package_id}` - Package metadata
  - `/api/v2/stats/{package_id}` - Download statistics (installs_last_month)
- **GitHub API** - Issue creation, updates, and management
- **Flatpak command line** - Runtime version queries (fallback)

### Troubleshooting Common Issues
- **"GITHUB_TOKEN environment variable is required"** - Set the environment variable before running
- **"Failed to fetch flatpak list"** - Network connectivity issue to GitHub (check internet connection)
- **"Could not list runtime versions"** - Flatpak not installed or flathub remote not configured (fallback to known versions exists)
- **"Can't load uri flathub.flatpakrepo"** - Network firewall blocking flathub access (expected in restricted environments)
- **"Name resolution error for flathub.org"** - DNS resolution failing (expected in restricted network environments - scripts have fallback mechanisms)
- **"Artifact not found" in changelog generation** - Runtime check workflow hasn't run yet or failed - fallback to empty changelog
- **Jekyll build failure** - Check _config.yml syntax and ensure all referenced files exist
- **Issues not being created** - Verify GITHUB_TOKEN has issues:write permission
- **Changelog not updating** - Ensure generate-changelog workflow has contents:write permission

### Adding New Features
- Always maintain backward compatibility with existing issue format
- Test API rate limiting considerations for large package lists
- Ensure proper error handling for network failures
- Update requirements.txt if adding new Python dependencies
- Update all relevant workflow files if changing script interfaces
- Test Jekyll site locally before pushing changes that affect website content

## End-to-End Testing

### Creating a Test Script
Create a test script in `/tmp` to validate the complete workflow without creating real issues:

```python
#!/usr/bin/env python3
"""End-to-end test for flatpak-tracker"""
import os
import sys
import json
import tempfile

# Test 1: Check flatpak list retrieval
print("Test 1: Fetching flatpak lists...")
os.system('python check_flatpak_runtimes.py --output /tmp/test_output.json')

# Verify output exists and has correct structure
with open('/tmp/test_output.json', 'r') as f:
    data = json.load(f)
    assert 'timestamp' in data
    assert 'total_checked' in data
    assert 'outdated_count' in data
    assert 'outdated_packages' in data
    assert 'all_tracked_packages' in data
    print(f"✅ Test 1 passed: Found {data['total_checked']} tracked packages")

# Test 2: Validate donation metadata checker (dry run only)
print("\nTest 2: Checking donation metadata (dry run)...")
result = os.system('python check_donation_metadata.py --input /tmp/test_output.json')
assert result == 0
print("✅ Test 2 passed: Donation metadata check completed")

# Test 3: Validate changelog generation (without GitHub token)
print("\nTest 3: Testing changelog generation (will fail without token)...")
# This is expected to fail without proper GitHub credentials
# but we can validate the script syntax and basic structure
print("⚠️ Test 3 skipped: Requires GITHUB_TOKEN and GITHUB_REPOSITORY")

print("\n✅ All automated tests completed successfully!")
```

Run with: `python /tmp/test_end_to_end.py`

### Manual Integration Testing
When making changes that affect the entire workflow:

1. **Test Runtime Check**:
   ```bash
   python check_flatpak_runtimes.py --output /tmp/test_outdated.json
   # Verify JSON structure and package counts
   jq '.' /tmp/test_outdated.json | head -20
   ```

2. **Test Issue Generation (with test repo)**:
   ```bash
   export GITHUB_TOKEN="your_test_token"
   export GITHUB_REPOSITORY="your_test_org/test_repo"
   python issue_generator.py /tmp/test_outdated.json
   # Check that issues were created in test repository
   ```

3. **Test Donation Checker**:
   ```bash
   python check_donation_metadata.py --input /tmp/test_outdated.json
   # Review output for missing/unreachable donation URLs
   ```

4. **Test Changelog Generator**:
   ```bash
   python generate_changelog.py /tmp/test_outdated.json
   # Verify CHANGELOG.md was updated with current week's entry
   ```

5. **Test Jekyll Site Locally**:
   ```bash
   # Requires Ruby and bundler
   bundle install
   bundle exec jekyll serve
   # Visit http://localhost:4000/flatpak-tracker
   ```

### Workflow Orchestration Testing
The workflows run in this order on Mondays:
1. **9:00 AM UTC**: Runtime check runs, creates issues, uploads artifact
2. **10:00 AM UTC**: Donation check runs (uses runtime check data)
3. **11:00 AM UTC**: Changelog generation runs (downloads artifact from step 1)
4. **On push to main**: Jekyll site deploys (triggered by changelog commit)

To test the full orchestration:
- Manually trigger "Check Flatpak Runtime Updates" workflow
- Wait for completion and verify artifact was uploaded
- Manually trigger "Check Donation Metadata" workflow  
- Manually trigger "Generate Changelog" workflow
- Verify CHANGELOG.md was committed to main
- Verify Jekyll site deployed with updated content

### Known Testing Limitations in Restricted Environments
- **Flathub API access**: May fail with "Name resolution error" - this is expected and handled
- **Flatpak remote setup**: May fail in sandboxed environments - fallback to known versions exists
- **GitHub issue creation**: Cannot test without valid credentials - focus on JSON output validation
- **Download statistics**: API calls may timeout - scripts handle gracefully with 0 downloads fallback

# Issue Labeling

## Runtime Version Labels
- Issues for applications that need to upgrade to org.gnome.Platform/x86_64/49 should be labeled as `gnome-49`
- Issues for applications that need their freedesktop runtime updated to org.freedesktop.Platform/x86_64/25.08 should be labeled `freedesktop-25.08`
- Issues for applications that need their KDE runtime updated to org.kde.Platform/x86_64/6.9 should be labeled `kde-6.9`

## Popular Application Labels
- The `popular` label is automatically applied to the **top 10 most downloaded applications** within each runtime group
- Grouping is by runtime family: GNOME, KDE, and Freedesktop
- Download counts are fetched from Flathub API (`installs_last_month` metric)
- If a runtime group has fewer than 10 outdated packages, all of them receive the `popular` label
- Example: If there are 25 GNOME packages, 15 KDE packages, and 37 Freedesktop packages:
  - Top 10 GNOME packages get `popular` (15 others don't)
  - Top 10 KDE packages get `popular` (5 others don't)
  - Top 10 Freedesktop packages get `popular` (27 others don't)
  - Total: 30 packages with `popular` label

## Donation Metadata Labels
- Issues for missing or unreachable donation links are labeled with `donation-metadata`
- These issues are created by check_donation_metadata.py
- **Filtered applications** (not tracked for donation metadata):
  - GNOME apps (org.gnome.*) - have their own donation infrastructure
  - KDE apps (org.kde.*) - have their own donation infrastructure
  - Commercial/closed-source applications - not expected to have donation links
- Existing issues for filtered apps are automatically closed when filtering rules are applied

## Label Purpose
- Runtime version labels help filter issues by target runtime
- `popular` label helps prioritize high-impact applications that affect more users
- `donation-metadata` label separates donation-related issues from runtime updates

# Donation Metadata Tracking

## Purpose
The donation metadata checker helps ensure that open-source flatpak applications have donation links in their metadata, making it easier for users to support developers. This feature:
- Identifies packages missing donation URLs in their AppStream metadata
- Detects unreachable or broken donation links
- Filters out GNOME/KDE apps (they have established donation infrastructure)
- Filters out commercial/closed-source applications
- Creates GitHub issues to notify about missing or broken donation links

## How It Works
1. **Fetches package list**: Uses the output from check_flatpak_runtimes.py
2. **Queries Flathub API**: Gets metadata for each package including `urls.donation` field
3. **Validates URLs**: Tests if donation URLs are reachable (HTTP HEAD request)
4. **Applies filters**: Skips GNOME/KDE apps and commercial applications
5. **Creates issues**: Opens labeled issues for packages with problems
6. **Closes obsolete issues**: Automatically closes issues for packages now filtered

## Filtering Logic
- **GNOME apps**: Detected by `org.gnome.*` prefix or `project_group: GNOME` in metadata
- **KDE apps**: Detected by `org.kde.*` prefix or `project_group: KDE` in metadata
- **Commercial apps**: Detected by license keywords: `proprietary`, `commercial`, `closed`, `LicenseRef-proprietary`

## Issue Limits
To avoid overwhelming the tracker, donation metadata checker limits to **25 new issues per run**. If more issues are needed, they'll be created in subsequent weekly runs.

## Verification
Check a package's metadata at: `https://flathub.org/api/v2/appstream/{package_id}?locale=en`

Look for the `urls.donation` field in the JSON response.

# Changelog and Website

## CHANGELOG.md Structure
The changelog is automatically generated and updated weekly by generate_changelog.py. It contains:

1. **Overview Statistics** (updated weekly):
   - Total applications tracked
   - Number up to date
   - Number needing updates
   - Compliance rate percentage
   - Target runtime versions (GNOME, KDE, Freedesktop)

2. **Historical Updates** section:
   - Weekly entries showing all outdated packages in table format
   - Each entry includes: run date, run ID link, application table, stats, and summary
   - Application table columns: Application Name, Flatpak ID (linked to GitHub), Current Runtime, Target Runtime
   - Runtime versions displayed as labels (e.g., `gnome-48`, `freedesktop-24.08`)

3. **How This Works** section (static):
   - Explains the workflow process
   - Links to contributing guide

## Jekyll Website (GitHub Pages)
- **URL**: https://ublue-os.github.io/flatpak-tracker
- **Purpose**: Public-facing dashboard showing current state and historical updates
- **Source**: `index.md` (which includes CHANGELOG.md content)
- **Theme**: Custom Jekyll theme with layouts in `_layouts/` and includes in `_includes/`
- **Styling**: CSS in `public/` directory
- **Configuration**: `_config.yml` sets site title, baseurl, and excluded files
- **Deployment**: Automatic on every push to main branch (triggered by changelog commit)

### Jekyll Configuration Details
- Title: "Flatpak Runtime Tracker"
- Tagline: "Tracking runtime updates for Universal Blue"
- Base URL: `/flatpak-tracker`
- Excluded from site: Python scripts, JSON test files, requirements.txt, compiled Python files

## Workflow Artifact System
The workflows use GitHub Actions artifacts to pass data between runs:

1. **outdated-packages-data** (from check-flatpak-runtimes.yml):
   - Contains: `outdated_packages.json`
   - Retention: 30 days
   - Used by: generate-changelog.yml

2. **flatpak-list-data** (from check-donation-metadata.yml):
   - Contains: `flatpak_list.json`
   - Retention: 30 days
   - Used for: Debugging and manual analysis

The changelog generator can also backfill historical data by downloading artifacts from previous workflow runs.

# Architecture and Data Flow

## High-Level Architecture
```
┌─────────────────────────────────────────────────────────────┐
│ External Data Sources                                       │
├─────────────────────────────────────────────────────────────┤
│ • ublue-os/bluefin (flatpaks + bazaar config)              │
│ • ublue-os/aurora (flatpaks + bazaar config)               │
│ • ublue-os/bazzite (flatpaks + bazaar config)              │
│ • Flathub API (metadata + statistics)                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Weekly Workflow: Check Flatpak Runtime Updates (Mon 9 AM)  │
├─────────────────────────────────────────────────────────────┤
│ check_flatpak_runtimes.py → outdated_packages.json         │
│ issue_generator.py → Creates/Updates GitHub Issues         │
│ Uploads artifact: outdated-packages-data                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Weekly Workflow: Check Donation Metadata (Mon 10 AM)       │
├─────────────────────────────────────────────────────────────┤
│ Uses flatpak list from check_flatpak_runtimes.py           │
│ check_donation_metadata.py → Creates/Closes Issues         │
│ Uploads artifact: flatpak-list-data                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Weekly Workflow: Generate Changelog (Mon 11 AM)            │
├─────────────────────────────────────────────────────────────┤
│ Downloads artifact: outdated-packages-data                  │
│ generate_changelog.py → Updates CHANGELOG.md               │
│ Commits and pushes to main branch                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ On Push to Main: Deploy Jekyll Site                        │
├─────────────────────────────────────────────────────────────┤
│ Builds Jekyll site from index.md + CHANGELOG.md            │
│ Deploys to GitHub Pages                                     │
│ Published at: ublue-os.github.io/flatpak-tracker           │
└─────────────────────────────────────────────────────────────┘
```

## Data Format: outdated_packages.json
```json
{
  "timestamp": "2025-10-31T15:55:18.125865",
  "total_checked": 260,
  "outdated_count": 77,
  "outdated_packages": [
    {
      "flatpak_id": "app/org.mozilla.firefox",
      "sources": ["bluefin", "aurora", "bazzite-gnome"],
      "current_runtime": "org.freedesktop.Platform/x86_64/24.08",
      "latest_runtime": "org.freedesktop.Platform/x86_64/25.08",
      "current_version": "24.08",
      "latest_version": "25.08"
    }
  ],
  "all_tracked_packages": [
    "app/org.mozilla.firefox",
    "app/org.gnome.Calculator",
    ...
  ]
}
```

## Runtime Version Detection Strategy
The tool uses a **three-tier fallback approach** to determine the latest runtime versions:

1. **Known Current Versions (Primary)**: Hardcoded in check_flatpak_runtimes.py
   - org.gnome.Platform: 49
   - org.freedesktop.Platform: 25.08
   - org.kde.Platform: 6.10
   - Updated manually when new stable releases are announced

2. **Flathub API (Secondary)**: Queries runtime metadata from Flathub
   - Used when runtime is not in known_latest_versions
   - Extracts version from bundle.runtime field

3. **Flatpak Command (Tertiary)**: Uses `flatpak remote-ls` command
   - Only works when flatpak is installed and flathub remote configured
   - Often unavailable in CI/sandboxed environments

This approach ensures the tool works even in restricted network environments where Flathub API access may be blocked.

## Issue Management Strategy
The tool maintains issue hygiene through automatic lifecycle management:

### Creating Issues
- Checks for existing issues before creating duplicates
- Uses exact title matching: "Update runtime for {flatpak_id}"
- Applies appropriate labels (runtime version, popular, donation-metadata)
- Includes detailed instructions and links to documentation

### Updating Issues
- Detects when runtime information changes
- Updates issue body with new information
- Adds comment explaining the update
- Preserves original issue number and labels

### Closing Issues
- **Runtime resolved**: Package runtime is now up to date
- **No longer tracked**: Package removed from all source lists
- **Filtered out**: Package now meets filtering criteria (GNOME/KDE/commercial for donation issues)
- Adds explanatory comment before closing
- Closed issues remain available for reference

## Error Handling Philosophy
The tool is designed to be **resilient and graceful**:

- **Network failures**: Logs warning, continues with next package (doesn't fail entire run)
- **Missing data**: Uses fallback values or skips package
- **API rate limits**: Includes delays between requests (1 second for Flathub stats)
- **Invalid responses**: Validates JSON structure, handles missing fields
- **Partial failures**: Completes successfully even if some packages can't be checked
- **Artifact missing**: Changelog generator creates minimal fallback entry

This ensures workflows don't fail catastrophically and provide useful partial results.
