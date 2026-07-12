# Job Automation Platform

This project currently implements Milestone 2: the first end-to-end job collection workflow.

## Current milestone

Milestone 2 includes:
- RemoteOK API communication
- RemoteOK response parsing
- Generic Job model creation
- SQLite database initialization and job insertion
- Workflow execution logging

## Create a virtual environment

```bash
python -m venv .venv
```

## Install dependencies

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Activate the virtual environment

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Run the application

```bash
python app/main.py
```
## Run tests
```bash
python -m unittest discover -s tests -p "test_*.py"
```

## What currently works

- Application startup and configuration loading
- Centralized logging
- Filesystem validation
- Automatic SQLite database creation
- RemoteOK download and parsing
- Job storage in SQLite
- Workflow summary logging
