# flatpak-updater

A GitHub Actions-based tool that monitors flatpak packages from [ublue-os/bluefin](https://github.com/ublue-os/bluefin) for outdated runtimes and automatically creates tracking issues for packages that need updates.

## Purpose

This repository tracks flatpak packages from the [ublue-os/bluefin system-flatpaks.list](https://github.com/ublue-os/bluefin/blob/main/flatpaks/system-flatpaks.list) and identifies which ones are using outdated flatpak runtimes. When outdated runtimes are detected, GitHub issues are automatically created with instructions on how to update them.

## How It Works

1. **Automated Monitoring**: A GitHub Action runs daily to check for runtime updates
2. **Runtime Analysis**: The script fetches the flatpak list and queries Flathub for runtime information
3. **Issue Creation**: For each package with an outdated runtime, a GitHub issue is created with:
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
    'org.kde.Platform': '6.8',      # Check: https://community.kde.org/Schedules
}
```

## Manual Execution

You can manually trigger the runtime check by:

1. Going to the [Actions tab](../../actions)
2. Selecting the "Check Flatpak Runtime Updates" workflow
3. Clicking "Run workflow"

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

## Contributing

If you notice false positives or have suggestions for improving the runtime detection, please open an issue or submit a pull request.

### Updating Runtime Versions

When new stable runtime versions are released:

1. Update the `known_latest_versions` dictionary in `check_flatpak_runtimes.py`
2. Test the changes locally
3. Submit a pull request