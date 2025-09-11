# flatpak-updater

A GitHub Actions-based tool that monitors flatpak packages from [ublue-os/bluefin](https://github.com/ublue-os/bluefin) for outdated runtimes and automatically creates tracking issues for packages that need updates.

## Purpose

This repository tracks flatpak packages from the [ublue-os/bluefin system-flatpaks.list](https://github.com/ublue-os/bluefin/blob/main/flatpaks/system-flatpaks.list) and identifies which ones are using outdated flatpak runtimes. When outdated runtimes are detected, GitHub issues are automatically created with instructions on how to update them.

This helps keep the ISOs small and can be an effective onramp for people who want to get involved helping FlatHub by updating apps that we ship and recommend to all Aurora, Bazzite, and Bluefin images. 

## How It Works

1. **Automated Monitoring**: A GitHub Action runs daily to check for runtime updates
2. **Runtime Analysis**: The script fetches the flatpak list and queries Flathub for runtime information
3. **Issue Creation**: For each package with an outdated runtime, a GitHub issue is created with:
   - Current runtime version
   - Latest available runtime version
   - Update instructions for maintainers
   - Links to relevant resources

## Manual Execution

You can manually trigger the runtime check by:

1. Going to the [Actions tab](../../actions)
2. Selecting the "Check Flatpak Runtime Updates" workflow
3. Clicking "Run workflow"

## Issues

Each issue created by this bot will be tagged with:
- `runtime-update`: Indicates this is a runtime update issue
- `automated`: Shows this was created automatically

## Development Environment

This repository includes a `.copilot-agent-environment` file that automatically sets up the development environment for GitHub Copilot coding agents. This file preinstalls:

- Python 3.11 and pip
- Required Python dependencies (requests, PyGithub, etc.)
- Flatpak and related system packages
- Flathub remote configuration

This speeds up development by avoiding the need to install dependencies each time.

## Contributing

If you notice false positives or have suggestions for improving the runtime detection, please open an issue or submit a pull request.
