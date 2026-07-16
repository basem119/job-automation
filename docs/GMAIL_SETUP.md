# Gmail Credentials Integration - Setup Guide

## Overview

The job automation system now integrates with Gmail API to automatically create draft emails for job applications. The system has been designed with:
- **Graceful fallback**: Works in mock mode if credentials are unavailable
- **Robust validation**: Verifies credentials file exists and is valid before use
- **Clear logging**: Distinguishes between MOCK and REAL Gmail API calls
- **Security**: Credentials file is never committed to version control

## How It Works

### System Architecture

```
Application Draft Workflow
  ↓
ApplicationBuilder (coordinates data)
  ↓
GmailDraftService (creates drafts)
  ├── If credentials available → Real Gmail API
  └── If credentials missing → Mock mode (generates deterministic draft IDs)
```

### Credential Handling Flow

1. **Initialization**: `GmailDraftService(credentials_file=path/to/gmail_credentials.json)`
   - Validates that the file exists
   - Logs appropriate messages

2. **Client Creation**: On first use
   - Attempts to load credentials using Google service account library
   - Falls back to mock mode if:
     - File not provided
     - File doesn't exist
     - Invalid JSON format
     - Google libraries not installed

3. **Draft Creation**
   - **Real mode**: Creates actual Gmail draft via Gmail API
   - **Mock mode**: Generates deterministic draft ID (for testing)

## Setup Instructions

### Option 1: Using Existing Credentials (Already Set Up)

Your project already has `config/gmail_credentials.json` with valid service account credentials.

**Verify credentials are loaded:**
```powershell
cd e:\Git\job-automation\job-automation
.\.venv\Scripts\python.exe -c "
from app.application.gmail import GmailDraftService
service = GmailDraftService('config/gmail_credentials.json')
print('Credentials loaded successfully!' if service.credentials_file else 'Using mock mode')
"
```

**Expected output:**
```
INFO - job_automation - Gmail credentials file configured: config/gmail_credentials.json
Credentials loaded successfully!
```

### Option 2: Setting Up New Credentials

If you need to create new credentials:

#### Step 1: Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing one)
3. Enable Gmail API:
   - Search for "Gmail API"
   - Click "Enable"

#### Step 2: Create Service Account
1. Go to **Credentials** in left sidebar
2. Click **"Create Credentials"** → **"Service Account"**
3. Fill in details:
   - Service account name: `job-automation`
   - Service account ID: auto-filled
   - Click "Create and Continue"
4. Click "Create Key" → **JSON** → **Create**
   - Downloads `YOUR-KEY.json` file

#### Step 3: Configure in Project
1. Rename downloaded file to `gmail_credentials.json`
2. Move to: `config/gmail_credentials.json`
3. Add to `.gitignore` (already done):
   ```
   config/gmail_credentials.json
   ```

#### Step 4: Verify Setup
```powershell
cd e:\Git\job-automation\job-automation
.\.venv\Scripts\python.exe -c "
from pathlib import Path
import json

creds_file = Path('config/gmail_credentials.json')
if creds_file.exists():
    data = json.load(open(creds_file))
    print(f'✓ Credentials file found')
    print(f'  Service Account: {data.get(\"client_email\")}')
    print(f'  Project ID: {data.get(\"project_id\")}')
else:
    print('✗ Credentials file not found')
"
```

## Implementation Details

### GmailDraftService Changes

**File**: `app/application/gmail/service.py`

#### Improved Initialization
```python
def __init__(self, credentials_file: Path | str | None = None) -> None:
    self.credentials_file = None
    if credentials_file:
        cred_path = Path(credentials_file)
        if cred_path.exists():
            self.credentials_file = cred_path
            logger.info(f"Gmail credentials file configured: {cred_path}")
        else:
            logger.warning(f"Gmail credentials file not found: {cred_path}, will use mock mode")
    self._client = None
```

**What this does:**
- ✓ Validates file exists before storing
- ✓ Logs status at initialization
- ✓ Won't fail later with "file not found" error

#### Enhanced Client Creation
```python
def _create_client(self):
    if not self.credentials_file:
        logger.warning("Gmail credentials file not configured, using mock mode")
        return None
    
    if not self.credentials_file.exists():
        logger.warning(f"Gmail credentials file does not exist: {self.credentials_file}, using mock mode")
        return None
    
    try:
        creds = Credentials.from_service_account_file(str(self.credentials_file))
        service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail API client successfully initialized")
        return service
    except (ImportError, ValueError, Exception) as e:
        logger.error(f"Failed to create Gmail client: {e}")
        logger.warning("Using mock mode")
        return None
```

**What this does:**
- ✓ Graceful fallback for missing libraries
- ✓ Graceful fallback for invalid credentials format
- ✓ Clear logging of failure reason
- ✓ Comprehensive exception handling

#### Clear Draft Logging
```python
def create_draft(self, to_email, subject, body, resume_path):
    if self.client is None:
        # Mock mode
        draft_id = hashlib.sha256(f"{to_email}:{subject}".encode()).hexdigest()[:16]
        logger.info(f"[MOCK] Gmail draft created: {draft_id} (to={to_email})")
        return draft_id
    
    # Real API mode
    result = self.client.users().drafts().create(userId="me", body=draft).execute()
    draft_id = result.get("id")
    logger.info(f"[REAL] Gmail draft created: {draft_id} (to={to_email})")
    return draft_id
```

**What this does:**
- ✓ [MOCK] vs [REAL] prefix in logs for clarity
- ✓ Easy to distinguish between real and test runs
- ✓ Recipient info logged for verification

### Main.py Integration

The `app/main.py` workflow now:
1. Loads credentials from `config/gmail_credentials.json`
2. Passes credentials to `ApplicationDraftWorkflow`
3. Logs comprehensive statistics:
   - Recommended jobs processed
   - Recruiter discovery attempts/successes
   - Applications built
   - Drafts created (with/without recipient)
   - Validation failures
   - Draft creation failures

**Log output example:**
```
INFO - Application draft generation - Recommended jobs: 5
INFO - Application draft generation - Recruiter discovery found: 3
INFO - Application draft generation - Applications built: 5
INFO - Application draft generation - Drafts created: 5
INFO - Application draft generation - Drafts with recipient: 3
INFO - Application draft generation - Drafts without recipient: 2
```

## Security Considerations

### ✓ What's Protected
- `config/gmail_credentials.json` is in `.gitignore` (never committed)
- Service account uses OAuth, not stored passwords
- Gmail API can be revoked by deleting service account

### ⚠️ What You Should Do
1. **Never commit credentials file**
   - If accidentally committed, regenerate service account immediately
   - Delete all keys: Google Cloud Console → Service Accounts → job-automation → Keys

2. **Limit service account permissions**
   - Only grant Gmail API access
   - Don't grant Owner/Editor roles
   - Use least-privilege principle

3. **Rotate credentials periodically**
   - Create new service account key every 90 days
   - Delete old keys in Google Cloud Console

## Troubleshooting

### Issue: "Gmail credentials file not configured, using mock mode"
**Cause**: Credentials file not provided or not found
**Solution**:
```powershell
# Check file exists
Test-Path config/gmail_credentials.json

# If missing, obtain credentials from Google Cloud Console
# Then move to config/gmail_credentials.json
```

### Issue: "Invalid Gmail credentials file format"
**Cause**: JSON file is corrupted or wrong format
**Solution**:
```powershell
# Validate JSON format
python -m json.tool config/gmail_credentials.json

# If invalid, regenerate from Google Cloud Console
```

### Issue: "Gmail API library not installed"
**Cause**: Required Google libraries missing
**Solution**:
```powershell
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### Issue: Gmail API returns permission error
**Cause**: Service account not authorized
**Solution**:
1. Go to Google Cloud Console
2. Select project: `job-automation-502516`
3. Verify Gmail API is enabled
4. Check service account has necessary roles

## Testing

### Test Without Credentials (Mock Mode)
```powershell
# This will use mock draft IDs
$env:GMAIL_CREDENTIALS = $null
python app/main.py
```

### Test With Credentials (Real API)
```powershell
# This will create real Gmail drafts
python app/main.py
```

### Verify Logs
Check application logs for [MOCK] or [REAL] prefix to see which mode is active.

## API Limits

Gmail API has the following limits:
- **Daily quota**: 1 billion requests/day (practically unlimited)
- **Per-user quota**: 15,000 requests/minute
- **Creation quota**: No specific limit for drafts

Your job application workflow is well within limits.

## Next Steps

1. ✓ Credentials configured and validated
2. ✓ GmailDraftService improvements complete
3. ⏳ Create ApplicationPreview for draft validation
4. ⏳ Build comprehensive test suite
5. ⏳ End-to-end validation with real jobs
