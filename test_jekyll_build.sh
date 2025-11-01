#!/bin/bash
# Test script to verify Jekyll build works correctly before deployment

set -e

echo "Testing Jekyll build..."

# Ensure we have the C++ compiler in PATH for eventmachine gem
export PATH="$HOME/.local/bin:$PATH"

# Install dependencies
echo "Installing bundle dependencies..."
bundle install --quiet

# Build the site
echo "Building Jekyll site..."
bundle exec jekyll build

# Verify critical assets exist
echo "Verifying assets..."
test -f _site/index.html || { echo "ERROR: index.html not found"; exit 1; }
test -f _site/public/css/poole.css || { echo "ERROR: poole.css not found"; exit 1; }
test -f _site/public/css/lanyon.css || { echo "ERROR: lanyon.css not found"; exit 1; }
test -f _site/public/css/syntax.css || { echo "ERROR: syntax.css not found"; exit 1; }
test -f _site/public/js/script.js || { echo "ERROR: script.js not found"; exit 1; }

# Verify no doubled baseurl in paths
echo "Checking for path issues..."
if grep -q "/flatpak-tracker/flatpak-tracker/" _site/index.html; then
    echo "ERROR: Found doubled baseurl path in index.html"
    exit 1
fi

# Verify correct single baseurl path (should contain /flatpak-tracker/public but not doubled)
if ! grep -q '/flatpak-tracker/public/css/' _site/index.html; then
    echo "ERROR: CSS paths don't contain correct baseurl in index.html"
    exit 1
fi

echo "✅ All tests passed! Jekyll site builds correctly."
