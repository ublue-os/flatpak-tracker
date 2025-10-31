# Flatpak Runtime Updater

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

Flatpak Runtime Updater is a Python-based GitHub Actions tool that monitors flatpak packages from ublue-os/bluefin for outdated runtimes and automatically creates GitHub issues when updates are available.

## Working Effectively

### Bootstrap and Dependencies
- Install Python dependencies: `pip install -r requirements.txt` -- installs requests>=2.31.0 and PyGithub>=1.59.0
- Install system dependencies: `sudo apt-get update && sudo apt-get install -y flatpak`
- Add flathub remote: `sudo flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo` -- may fail in restricted network environments due to firewall limitations
- Validate Python syntax: `python -m py_compile check_flatpak_runtimes.py`

### Running the Application
- **CRITICAL**: Set required environment variables before running:
  - `export GITHUB_TOKEN=<your_github_token>`
  - `export GITHUB_REPOSITORY=<owner/repo>`
- Run the main script: `python check_flatpak_runtimes.py` -- completes in under 1 minute for script execution, but may take 2-5 minutes total depending on API response times and number of packages (33 packages as of current list)
- **Manual workflow trigger**: Use GitHub Actions UI to trigger "Check Flatpak Runtime Updates" workflow
- **Automated schedule**: Runs daily at 9 AM UTC via GitHub Actions

### Build and Test
- **No traditional build process** - this is a Python script that runs directly
- **No unit tests** - validation is done by running the script itself
- Syntax validation: `python -m py_compile check_flatpak_runtimes.py`
- **No linting configuration** - no flake8, pylint, or other linting tools configured
- Test external API access: `curl -s "https://raw.githubusercontent.com/ublue-os/bluefin/main/flatpaks/system-flatpaks.list" | head -5`

## Validation Scenarios

### Always Test These After Making Changes
1. **Dependency installation**: Run `pip install -r requirements.txt` and verify no errors
2. **Script compilation**: Run `python -m py_compile check_flatpak_runtimes.py` and verify no syntax errors
3. **Flatpak installation**: Run `flatpak --version` to verify flatpak is installed and working
4. **External API connectivity**: Test `curl -s "https://flathub.org/api/v2/appstream/org.gnome.Calculator"` -- may fail in restricted networks with name resolution errors
5. **Flatpak list retrieval**: Test `curl -s "https://raw.githubusercontent.com/ublue-os/bluefin/main/flatpaks/system-flatpaks.list"` -- should return 33+ flatpak package names

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
│   └── workflows/
│       └── check-flatpak-runtimes.yml    # GitHub Actions workflow
├── .gitignore                            # Python/IDE/OS ignores
├── LICENSE                               # Apache 2.0 license
├── README.md                             # Project documentation
├── check_flatpak_runtimes.py            # Main executable script
└── requirements.txt                      # Python dependencies
```

### Key Script Functions
- `fetch_flatpak_list()` - Retrieves package list from ublue-os/bluefin
- `get_flatpak_info()` - Queries Flathub API for package metadata
- `get_runtime_from_flatpak_info()` - Extracts runtime information
- `compare_versions()` - Determines if runtime updates are available
- `create_or_update_issue()` - Creates GitHub issues for outdated packages

### GitHub Actions Workflow
- **Trigger**: Daily at 9 AM UTC (`0 9 * * *`) or manual dispatch
- **Runtime**: ubuntu-latest with Python 3.11
- **Permissions**: issues:write, contents:read
- **Dependencies**: Installs flatpak system package and Python requirements
- **Duration**: Typically completes in 2-5 minutes depending on API response times

### Environment Variables Required
- `GITHUB_TOKEN` - GitHub API token with issues:write permission
- `GITHUB_REPOSITORY` - Repository in format "owner/repo"

### External Dependencies
- **ublue-os/bluefin** - Source of flatpak package list
- **Flathub API** - Package metadata and runtime information
- **GitHub API** - Issue creation and management
- **Flatpak command line** - Runtime version queries

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

# Issue Labelling

- Issues for applications that need to upgrade to org.gnome.Platform/x86_64/49 should be labelled as `gnome-49`
- Issues for applications that need their freedesktop runtime updated to org.freedesktop.Platform/x86_64/25.08 should be labelled `freedesktop-25.08`
- Issues for applications that need their KDE runtime updated to org.kde.Platform/x86_64/6.9 should be labelled `kde-6.9`
