# Export & Backup

## Metadata

- **ID**: WF-007
- **Version**: 1.0.0
- **Owner**: Storage Module, Backup Module (py/storage.py, py/backup.py, main.py)
- **Trigger**: User clicks export on record, or backup/restore in settings
- **Last Updated**: 2026-04-29

---

## Overview

Export individual records in multiple formats (Markdown, text, DOCX, SRT) or perform full application backup and restore. Backup includes configuration, presets, records, and optionally audio files.

---

## Pre-conditions

### Export
- [ ] Record exists with content to export
- [ ] Output directory is writable

### Backup
- [ ] Data directory is accessible
- [ ] Sufficient disk space for backup

---

## Flow

### Step 1: Select Export Format

**Actor**: User
**Action**: Choose from: Markdown (.md), Text (.txt), Word (.docx), SRT (.srt)
**Validation**: Record has content for selected format
**On Failure**: "No content to export"

### Step 2: Configure Options

**Actor**: User
**Action**: Toggle "Include AI results" checkbox (default: enabled)
**Validation**: N/A
**On Failure**: N/A

### Step 3: Export

**Actor**: System
**Action**: `export_record(record_id, fmt, include_ai)` generates file in export directory
**Validation**: File written successfully
**On Failure**: Show "Export failed" error

### Step 4: Backup (full data)

**Actor**: User
**Action**: In settings, select data types to backup (config, presets, records, audio)
**Validation**: At least one option selected
**On Failure**: Prompt "Select at least one item"

### Step 5: Generate Backup

**Actor**: System
**Action**: `export_backup(path, options)` creates zip archive with selected data
**Validation**: Archive created, contents verified
**On Failure**: Show "Backup failed" error

### Step 6: Restore

**Actor**: User
**Action**: Select backup file, `import_backup(path)` restores data
**Validation**: Backup file is valid zip, version compatible
**On Failure**: "Invalid backup file" or version mismatch warning

---

## Post-conditions

### Export
- [ ] Export file generated in output directory
- [ ] File opens correctly in target application

### Backup
- [ ] Zip archive created with selected data
- [ ] Restore completes without data loss

---

## Error Handling

| Error Scenario | Detection | Recovery | User Feedback |
|---------------|-----------|----------|---------------|
| No content | Empty transcript + no AI | Block export | "Nothing to export" |
| Write permission | OS error | Choose different directory | "Cannot write to directory" |
| Invalid backup file | Zip parse error | Check file | "Invalid backup file" |
| Version mismatch | Backup format version check | Warn user, attempt partial restore | "Backup from different version" |
| Insufficient space | OS error | Show required space | "Insufficient disk space" |

---

## Related

- **Business Rules**: BR-EXPORT-001 (format support), BR-BACKUP-001 (selective backup)
- **API Endpoints**: export_record, import_record, export_backup, import_backup
- **Data Models**: records.csv, versions.csv, app_config.csv
