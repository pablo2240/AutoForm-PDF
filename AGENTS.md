# AGENTS.md

Guidelines and conventions for AI coding agents working on **AutoForm PDF** (SmartFormAI).

## Project Overview
- **AutoForm PDF**: Automated PDF filling system supporting both interactive AcroForms and flat visual overlay (WYSIWYG) forms.
- **Backend**: FastAPI (Python 3.10+) with PyMuPDF, OpenCV, and Azure OpenAI (`gpt-4.1-mini`).
- **Frontend**: React 19 + TypeScript + Vite.

## Architecture & Code Style
- Follow ponytail / clean, minimal, stdlib-first style.
- Preserve explicit path resolution when loading `.env` (`dotenv_path=ENV_PATH, override=True`).
- Read `company_data.json` using `encoding='utf-8-sig'` to prevent Windows BOM issues.
- Never write credentials or hardcoded keys into code.

## Agent Skills (Matt Pocock Suite)

### Issue Tracker
GitHub issues via `gh` CLI in `pablo2240/AutoForm-PDF`. See [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md).

### Triage Labels
Canonical roles mapped in [`docs/agents/triage-labels.md`](docs/agents/triage-labels.md).

### Domain Docs
Single-context setup. See [`docs/agents/domain.md`](docs/agents/domain.md) and [`CONTEXT.md`](CONTEXT.md).
