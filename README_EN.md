# neo-bpsys.PluginMarket

[中文 README](./README.md)

## Plugin Submission Flow

If you want to add a new plugin or update an existing one, follow this process.

1. Fork this repository.
2. In your fork, add or edit `PluginManifests/<PluginId>.yml`.
3. Make sure the manifest `id` is unique, and do not change the existing `id` when updating a plugin.
4. Fill in or update plugin metadata such as `name`, `description`, `version`, `apiVersion`, `author`, `url`, and `downloadURL`.
5. Run:

```powershell
python scripts/build-plugin-index.py
```

6. Confirm that the root `PluginIndex.json` has been generated or updated.
7. Commit both your manifest file and the updated `PluginIndex.json`.
8. Open a Pull Request against the `main` branch.

## Manifest Requirements

- Manifest files must be placed under `PluginManifests/`
- Recommended file name: `<PluginId>.yml`
- Only flat `key: value` structure is supported
- Nested objects and arrays are not supported
- Every manifest must contain a non-empty and unique `id`

Example:

```yml
id: "3DViewerIDV"
name: "3DViewerIDV"
description: "3D characters and scene support"
version: "0.04"
apiVersion: "2.0.0.0"
author: "jefcrb"
url: "https://github.com/jefcrb/3DViewerIDV"
downloadURL: "https://github.com/jefcrb/3DViewerIDV/releases/download/v0.04/repo-v0.04.zip"
```

## Common Cases

### Add a New Plugin

- Create your own `PluginManifests/<PluginId>.yml`
- Fill in the initial metadata
- Generate and commit `PluginIndex.json`

### Update an Existing Plugin

- Edit your existing manifest file
- Update fields such as version, download URL, or description
- Keep the original `id`
- Regenerate and commit `PluginIndex.json`

## Repository Automation

When `main` receives a push containing changes under `PluginManifests/**/*.yml`, GitHub Actions will:

1. Scan all manifests.
2. Rebuild the root `PluginIndex.json`.
3. Commit and push it only if the generated content changed.

The generated `PluginIndex.json` uses plugin `id` as the top-level key.

## Validation Rules

- Each line must be a valid flat `key: value` pair
- Lines starting with `#` are treated as comments
- If parsing fails, `id` is missing, or duplicate `id` values are found, the GitHub Action fails
