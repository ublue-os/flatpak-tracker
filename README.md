# Flatpak Tracker

Tracks out of date runtimes in Flatpaks shipped by Universal Blue. HELP WANTED! Go help a Flatpak!

## Purpose

This repository tracks flatpak packages from multiple ublue-os sources and identifies which ones are using outdated flatpak runtimes. When outdated runtimes are detected, GitHub issues are automatically created with instructions on how to update them.

This helps keep the ISOs small and can be an effective onramp for people who want to get involved helping FlatHub by updating apps that we ship and recommend to all Aurora, Bazzite, and Bluefin images.

## Architecture

The tool uses a two-step approach for better reliability and debugging:

### Step 1: Runtime Detection (`check_flatpak_runtimes.py`)
- Fetches flatpak lists from multiple ublue-os sources
- Queries Flathub API for runtime information
- Compares current vs latest runtime versions
- Outputs structured JSON data with outdated packages

### Step 2: Issue Generation (`issue_generator.py`)
- Reads the JSON output from step 1
- Creates GitHub issues for outdated packages
- Manages existing issues (prevents duplicates, closes resolved)
- Provides detailed update instructions

## How It Works

1. **Automated Monitoring**: A GitHub Action runs daily to check for runtime updates
2. **Multi-Source Analysis**: The script fetches flatpak lists from:
   - [ublue-os/bluefin system-flatpaks.list](https://github.com/ublue-os/bluefin/blob/main/flatpaks/system-flatpaks.list)
   - [ublue-os/aurora system-flatpaks.list](https://github.com/ublue-os/aurora/blob/main/flatpaks/system-flatpaks.list)  
   - [ublue-os/bazzite gnome flatpaks](https://github.com/ublue-os/bazzite/blob/main/installer/gnome_flatpaks/flatpaks)
   - [ublue-os/bazzite kde flatpaks](https://github.com/ublue-os/bazzite/blob/main/installer/kde_flatpaks/flatpaks)
3. **Runtime Analysis**: Queries Flathub for runtime information and compares with known latest versions
4. **Issue Creation**: For each package with an outdated runtime, a GitHub issue is created with:
   - Current runtime version
   - Latest available runtime version
   - Step-by-step update instructions for Flathub maintainers
   - Links to official documentation

## Runtime Version Detection

The script uses multiple approaches to determine the latest runtime versions:

1. **Known Current Versions**: Hardcoded latest stable versions for common runtimes
2. **Flathub API**: Fallback to API queries when available
3. **Flatpak Command**: Final fallback to `flatpak remote-ls` (when available)

### Maintaining Runtime Versions

The known runtime versions are defined in `check_flatpak_runtimes.py` and should be updated when new stable releases are available:

```python
known_latest_versions = {
    'org.gnome.Platform': '48',      # Check: https://wiki.gnome.org/ReleasePlanning
    'org.freedesktop.Platform': '24.08',  # Check: https://gitlab.com/freedesktop-sdk/freedesktop-sdk
    'org.kde.Platform': '6.9',      # Check: https://community.kde.org/Schedules
}
```

## Manual Execution

You can manually trigger the runtime check by:

1. Going to the [Actions tab](../../actions)
2. Selecting the "Check Flatpak Runtime Updates" workflow
3. Clicking "Run workflow"

### Local Testing

To test the detection script locally:
```bash
# Install dependencies
pip install -r requirements.txt

# Run detection (creates outdated_packages.json)
python check_flatpak_runtimes.py --output outdated_packages.json

# Create mock data for testing issue generation
python create_mock_data.py --output mock_outdated.json

# Test issue generation (requires GitHub credentials)
export GITHUB_TOKEN="your_token"
export GITHUB_REPOSITORY="owner/repo"
python issue_generator.py mock_outdated.json
```

## Workflow Steps

The GitHub Action performs these steps:

1. **Setup Environment**: Install Python, dependencies, and Flatpak
2. **Runtime Detection**: Run `check_flatpak_runtimes.py` to analyze packages
3. **Summary Display**: Show overview of findings in workflow logs
4. **Issue Creation**: Run `issue_generator.py` to create GitHub issues
5. **Artifact Upload**: Save detection results for debugging

## Error Handling

The tool includes robust error handling for:

- **Network Connectivity Issues**: Gracefully handles Flathub API failures
- **Authentication Problems**: Clear error messages for GitHub token issues
- **Malformed Data**: Validates JSON structure and required fields
- **Rate Limiting**: Respects GitHub API rate limits

If the detection step fails due to network issues, the workflow will still complete successfully, but no issues will be created.

## Issues

Each issue created by this bot will be tagged with:
- `runtime-update`: Indicates this is a runtime update issue
- `automated`: Shows this was created automatically

## Issue Template

The bot creates detailed issues with:
- **Current vs Latest Runtime**: Clear version comparison
- **Step-by-Step Instructions**: How to update manifest files
- **Testing Guide**: How to test locally before submission
- **Documentation Links**: Official Flathub and Flatpak resources

## Development Environment

This repository includes a `.copilot-agent-environment` file that automatically sets up the development environment for GitHub Copilot coding agents. This file preinstalls:

- Python 3.11 and pip
- Required Python dependencies (requests, PyGithub, etc.)
- Flatpak and related system packages
- Flathub remote configuration

This speeds up development by avoiding the need to install dependencies each time.

## File Structure

```
.
├── .github/
│   └── workflows/
│       └── check-flatpak-runtimes.yml    # GitHub Actions workflow
├── check_flatpak_runtimes.py            # Main detection script
├── issue_generator.py                   # GitHub issue creation module
├── create_mock_data.py                  # Test data generator for development
├── requirements.txt                     # Python dependencies
├── README.md                           # This documentation
├── LICENSE                             # Apache 2.0 license
└── .gitignore                          # Python/IDE/OS ignores
```

## Contributing

If you notice false positives or have suggestions for improving the runtime detection, please open an issue or submit a pull request.

### Updating Runtime Versions

When new stable runtime versions are released:

1. Update the `known_latest_versions` dictionary in `check_flatpak_runtimes.py`
2. Test the changes locally using the commands shown above
3. Submit a pull request

### Debugging Issues

If issues aren't being created:

1. Check the workflow logs for the "Display outdated packages summary" step
2. Download the `outdated-packages-data` artifact to inspect the JSON output
3. Verify GitHub token permissions include `issues: write`
4. Test issue generation locally with valid credentials
