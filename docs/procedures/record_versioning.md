# Record Versioning

## Metadata

- **ID**: WF-005
- **Version**: 1.0.0
- **Owner**: Storage Module (py/storage.py, main.py)
- **Trigger**: User edits transcript/AI results (auto) or clicks save version (manual)
- **Last Updated**: 2026-04-29

---

## Overview

Track changes to record content over time with automatic and manual versioning. Versions are stored in the `versions` table with snapshots of transcript, segments, and AI results. Maximum 20 versions per record, oldest pruned first.

---

## Pre-conditions

- [ ] Record exists in database
- [ ] Record has content to version (transcript or AI results)

---

## Flow

### Step 1: Content Change (auto-version)

**Actor**: User
**Action**: User edits transcript text or AI result in EditorView
**Validation**: Content actually differs from current saved version
**On Failure**: No version created if content unchanged

### Step 2: Mark Dirty

**Actor**: System
**Action**: `mark_dirty(record_id)` sets dirty flag, UI shows unsaved indicator
**Validation**: Record exists
**On Failure**: Silent fail

### Step 3: Save Changes

**Actor**: User
**Action**: User clicks save, `save_record()` persists changes
**Validation**: Content is valid, record exists
**On Failure**: Show "Save failed" error

### Step 4: Auto-version (on save)

**Actor**: System
**Action**: Before saving, `save_version()` creates snapshot of current transcript, segments, and AI results. Then updates record with new content.
**Validation**: Compare with latest version - skip if identical
**On Failure**: Save record without versioning, log warning

### Step 5: Prune Old Versions

**Actor**: System
**Action**: If version count exceeds 20, `_prune_versions()` deletes oldest versions
**Validation**: Always keep latest 20 versions
**On Failure**: Allow excess, prune on next save

### Step 6: Restore Version (manual)

**Actor**: User
**Action**: In version history panel, click restore on a specific version, `restore_version(record_id, version)`
**Validation**: Version exists for this record
**On Failure**: "Version not found" error

---

## Post-conditions

- [ ] Version snapshot stored in `versions` table
- [ ] Record content updated to new values
- [ ] Dirty flag cleared
- [ ] (After restore) Record content matches selected version

---

## Error Handling

| Error Scenario | Detection | Recovery | User Feedback |
|---------------|-----------|----------|---------------|
| Version not found | DB lookup | Show version list | "Version not found" |
| Prune failure | DB error | Allow excess | Silent warning |
| Restore corrupt data | JSON parse error | Skip restore | "Version data corrupted" |
| Concurrent edit | Content mismatch | Alert user | "Content was modified elsewhere" |

---

## Related

- **Business Rules**: BR-VER-001 (max versions), BR-VER-002 (auto-versioning)
- **API Endpoints**: save_version, restore_version, delete_version, get_version_history
- **State Machine**: Version State Machine
- **Data Models**: records.csv, versions.csv
