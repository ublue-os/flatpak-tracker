# Changelog Generation

## Overview

The flatpak-tracker repository automatically generates a changelog that tracks runtime updates for all monitored applications. The changelog combines:

- **Dashboard Statistics** - Overview of compliance rates and migration progress
- **Weekly Updates** - Recently updated applications and pending updates
- **Historical Archive** - Complete history of all changes

## Automatic Updates

The changelog updates automatically every Monday at 11:00 UTC (2 hours after the runtime check runs) via the [Generate Changelog workflow](.github/workflows/generate-changelog.yml).

Each week, the workflow:
1. Downloads the latest `outdated_packages.json` from the runtime check
2. Generates the current week's update section
3. Prepends it to the existing changelog
4. Commits the updated `CHANGELOG.md` back to the repository

## One-Time Historical Backfill

To initialize the changelog with historical data from previous workflow runs, use the backfill script **once**:

```bash
# Set environment variables
export GITHUB_TOKEN="your_github_token"
export GITHUB_REPOSITORY="ublue-os/flatpak-tracker"

# Run the one-time backfill
python backfill_changelog.py
```

This will:
- Fetch all previous **scheduled** workflow runs (ignores manual triggers)
- Download artifacts from each run
- Detect changes between snapshots (updated, added, removed apps)
- Generate a complete historical changelog
- Create `CHANGELOG.md` with the full history

**Note**: This should only be run once during initial setup. After backfilling, the weekly workflow will automatically maintain the changelog.

## How It Works

### Regular Weekly Updates (`generate_changelog.py`)

The main script:
1. Loads the current `outdated_packages.json`
2. Queries GitHub API for recently closed issues (last 7 days)
3. Generates dashboard statistics
4. Creates current week's changelog section
5. Prepends to existing changelog (moves previous week to historical section)
6. Writes updated `CHANGELOG.md`

### One-Time Backfill (`backfill_changelog.py`)

The backfill script:
1. Fetches all completed scheduled workflow runs for "Check Flatpak Runtime Updates"
2. Downloads `outdated-packages-data` artifact from each run
3. Builds snapshots of state at each point in time
4. Compares consecutive snapshots to detect:
   - Applications that were updated (removed from outdated list)
   - Applications that were added to tracking
   - Applications that were removed from tracking
5. Generates historical sections for each week
6. Creates initial `CHANGELOG.md` with complete history

## File Structure

```
.github/workflows/
  generate-changelog.yml    # Weekly scheduled workflow
generate_changelog.py       # Main weekly update generator
backfill_changelog.py      # One-time historical backfill
CHANGELOG.md              # Generated changelog (auto-updated)
index.md                  # Site landing page
_config.yml              # Jekyll configuration
```

## Changelog Format

The generated changelog follows this structure:

```markdown
# 📊 Flatpak Runtime Tracker
(Dashboard with current statistics)

# Weekly Update
Week of [date range]

## 🎉 Recently Updated
(Apps that were updated in the last week)

## 🔄 Pending Updates
### 🔥 High Priority (Popular Apps)
(Top 10 most downloaded apps needing updates)

### Standard Priority
(All other apps needing updates)

# Historical Updates
(Previous weeks in reverse chronological order)
```

## Troubleshooting

### Backfill finds no historical data
- Ensure the "Check Flatpak Runtime Updates" workflow has run at least twice
- Verify artifacts are being uploaded (check workflow runs)
- Check that runs were scheduled (event='schedule'), not manual

### Weekly update not generating
- Check the workflow logs in GitHub Actions
- Verify `outdated_packages.json` artifact exists from runtime check
- Ensure GITHUB_TOKEN has proper permissions

### Changelog format looks wrong
- Review the latest workflow run logs
- Check for any Python errors in the generation step
- Verify the `outdated_packages.json` structure is correct

## Manual Testing

Test the weekly generator locally:

```bash
# Set environment variables
export GITHUB_TOKEN="your_token"
export GITHUB_REPOSITORY="ublue-os/flatpak-tracker"

# Test with sample data
python generate_changelog.py temp_outdated.json

# Check the output
cat CHANGELOG.md
```

Test the backfill locally:

```bash
# Set environment variables (same as above)

# Run backfill
python backfill_changelog.py

# Review the historical sections
cat CHANGELOG.md
```
