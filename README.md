# StakeMap — 3D Stakeholder Mapping

Visualize and analyze stakeholder relationships in 3D, 2D matrix, and spherical views.

## Features

- **3D Stakeholder Mapping** — Interactive 3D, 2D matrix, and spherical visualization
- **Node Management** — Add, edit, delete stakeholders with name, category, influence, and interest
- **Connections** — Draw weighted connections between stakeholders with configurable priority
- **Multi-language** — English, Deutsch, Français, Italiano
- **Export** — PNG, JPG, PDF, GLB (requires trimesh), MP4 (requires FFmpeg)

## Requirements

- Python 3.10+
- matplotlib, numpy, pillow

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

## Build Executable

```powershell
.\build.ps1
```

## Language

Switch language via **Settings → Language**. Current languages:

- English (en)
- Deutsch (de)
- Français (fr)
- Italiano (it)

Translation files are in `i18n/*.json`. Add a new language by creating `i18n/<code>.json` with the same keys.
