# Model Installation

## Metadata

- **ID**: WF-003
- **Version**: 1.0.0
- **Owner**: Model Manager (py/model_manager.py, py/model_registry.py, main.py)
- **Trigger**: User clicks install on model management settings page
- **Last Updated**: 2026-04-29

---

## Overview

Download and install ASR models from multiple sources (HuggingFace, GitHub Proxy, ModelScope). Models are organized by type (streaming/offline), language, and size. Installation includes download, validation, and registration.

---

## Pre-conditions

- [ ] Internet connection available
- [ ] `models/` directory is writable
- [ ] Disk space sufficient for model (50MB - 3GB depending on model)
- [ ] User has selected a download source (config)

---

## Flow

### Step 1: Browse Available Models

**Actor**: User
**Action**: `list_available_models(model_type)` shows all models with metadata (size, language, type, source)
**Validation**: API call succeeds
**On Failure**: Show "Failed to load model list"

### Step 2: Select Model

**Actor**: User
**Action**: Click install button on desired model card
**Validation**: Model not already installed
**On Failure**: "Model already installed" - offer update instead

### Step 3: Download

**Actor**: System
**Action**: `install_model(model_id)` downloads from configured source, emits progress events
**Validation**: Download URL reachable, disk space available
**On Failure**: Retry with alternative source, show error after 3 attempts

### Step 4: Progress Display

**Actor**: System
**Action**: Emit progress events with download percentage and speed
**Validation**: Progress updates received
**On Failure**: Show "Downloading..." with no progress if callbacks fail

### Step 5: Validate

**Actor**: System
**Action**: After download, validate model files exist and are valid
**Validation**: All expected files present, checksum if available
**On Failure**: Delete partial download, show "Validation failed"

### Step 6: Register

**Actor**: System
**Action**: Model appears in `list_installed_models()` and is selectable in UI
**Validation**: Model shows in installed list
**On Failure**: Manual rescan or restart app

---

## Post-conditions

- [ ] Model files in `models/` directory
- [ ] Model appears in installed models list
- [ ] Model selectable in ASR settings

---

## Error Handling

| Error Scenario | Detection | Recovery | User Feedback |
|---------------|-----------|----------|---------------|
| Network error | Download timeout/failure | Retry with alternative source | "Download failed, try another source" |
| Disk full | OS error | Prompt user to free space | "Insufficient disk space" |
| Corrupt download | Validation failure | Re-download | "Download corrupted, retrying" |
| Source unavailable | API unreachable | Switch source | "Source unavailable, try another" |
| Permission denied | OS write error | Check directory permissions | "Cannot write to models directory" |

---

## Related

- **Business Rules**: BR-MODEL-001 (download sources), BR-MODEL-002 (model types)
- **API Endpoints**: list_available_models, install_model, validate_model, delete_model
- **Data Models**: N/A (filesystem-based)
