# ialhabbal ComfyUI Node Suite

This package combines the following ComfyUI custom nodes into a single suite:

- `Prompt Verify`
- `Compare`
- `Meta Prompt Extractor`
- `Occlusion Mask`
- `Loader for Batch Image Processing`
- `PhotoLab`
- `Save_It`

## Installation

1. Copy the `ialhabbal` folder into your ComfyUI `custom_nodes` directory.
2. Restart ComfyUI.

## Notes

- The suite exposes all nodes separately in the ComfyUI node menu.
- Each node keeps its existing functionality and frontend assets.
- Frontend files are served from the package `web` folder.

If a node fails to import, the suite will still attempt to load the remaining nodes.
