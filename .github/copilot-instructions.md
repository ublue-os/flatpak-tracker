# Flatpak Runtime Updater

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

Flatpak Runtime Updater is a Python-based GitHub Actions tool that monitors flatpak packages from multiple ublue-os sources (bluefin, aurora, bazzite) for outdated runtimes and automatically creates GitHub issues when updates are available. The tool fetches download statistics from Flathub and labels the most popular applications.

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
- Run the main script: `python check_flatpak_runtimes.py --output outdated_packages.json` -- generates JSON output with outdated packages
- Run issue generator: `python issue_generator.py outdated_packages.json` -- creates/updates GitHub issues with popular labels
- **Manual workflow trigger**: Use GitHub Actions UI to trigger "Check Flatpak Runtime Updates" workflow
- **Automated schedule**: Runs weekly on Mondays at 9 AM UTC via GitHub Actions

### Build and Test
- **No traditional build process** - this is a Python script that runs directly
- **No unit tests** - validation is done by running the script itself and end-to-end tests
- Syntax validation: `python -m py_compile check_flatpak_runtimes.py issue_generator.py`
- **No linting configuration** - no flake8, pylint, or other linting tools configured
- Test external API access: `curl -s "https://raw.githubusercontent.com/ublue-os/bluefin/main/flatpaks/system-flatpaks.list" | head -5`
- End-to-end test: Run the test script in `/tmp/test_end_to_end.py` to validate the complete workflow

## Validation Scenarios

### Always Test These After Making Changes
1. **Dependency installation**: Run `pip install -r requirements.txt` and verify no errors
2. **Script compilation**: Run `python -m py_compile check_flatpak_runtimes.py issue_generator.py` and verify no syntax errors
3. **Flatpak installation**: Run `flatpak --version` to verify flatpak is installed and working
4. **External API connectivity**: Test `curl -s "https://flathub.org/api/v2/appstream/org.gnome.Calculator"` -- may fail in restricted networks with name resolution errors
5. **Flatpak list retrieval**: Test `curl -s "https://raw.githubusercontent.com/ublue-os/bluefin/main/flatpaks/system-flatpaks.list"` -- should return package names
6. **Flathub stats API**: Test `curl -s "https://flathub.org/api/v2/stats/app/org.mozilla.firefox"` -- fetches download statistics

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
│   ├── copilot-instructions.md          # This file - instructions for Copilot
│   └── workflows/
│       └── check-flatpak-runtimes.yml    # GitHub Actions workflow
├── .gitignore                            # Python/IDE/OS ignores
├── LICENSE                               # Apache 2.0 license
├── README.md                             # Project documentation
├── check_flatpak_runtimes.py            # Runtime checker - generates JSON output
├── issue_generator.py                    # Issue creation with popular labeling
├── requirements.txt                      # Python dependencies
├── temp_outdated.json                    # Sample data for testing (77 packages)
└── test_outdated.json                    # Minimal test data (1 package)
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

### GitHub Actions Workflow
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
  5. Run issue_generator.py to create/update issues with popular labels
  6. Upload JSON data as artifact

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
- **"Failed to fetch flatpak list"** - Network connectivity issue to GitHub
- **"Could not list runtime versions"** - Flatpak not installed or flathub remote not configured
- **"Can't load uri flathub.flatpakrepo"** - Network firewall blocking flathub access (expected in restricted environments)

### Adding New Features
- Always maintain backward compatibility with existing issue format
- Test API rate limiting considerations for large package lists
- Ensure proper error handling for network failures
- Update requirements.txt if adding new Python dependencies

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

## Label Purpose
- Runtime version labels help filter issues by target runtime
- `popular` label helps prioritize high-impact applications that affect more users
