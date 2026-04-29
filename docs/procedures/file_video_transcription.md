# File / Video Transcription

## Metadata

- **ID**: WF-002
- **Version**: 1.1.0
- **Owner**: ASR Module, Video Downloader (py/asr.py, py/video_downloader.py, main.py)
- **Trigger**: User drags audio file / clicks import / enters video URL
- **Last Updated**: 2026-04-29

---

## Overview

Import existing audio files or download from URL, then transcribe with selected ASR model. Supports drag-and-drop, file picker, and yt-dlp video download with cookie configuration.

---

## Pre-conditions

- [ ] ASR model is installed
- [ ] For file import: file exists and is a supported audio format
- [ ] For video download: yt-dlp and ffmpeg are available (or static-ffmpeg installed)
- [ ] Destination directory is writable

---

## Flow

### Step 1: Input Selection

**Actor**: User
**Action**: Choose input method:
  - **File**: Drag-and-drop or file picker (`pick_audio_file()`)
  - **Video URL**: Enter URL in input field
**Validation**: File extension matches supported formats; URL is valid
**On Failure**: "Unsupported format" / "Invalid URL"

### Step 2a: File Import (file path)

**Actor**: System
**Action**: `import_and_transcribe(file_path, title)` copies file to `data/audio/`, checks for duplicates via `audio_meta.json`
**Validation**: File not already imported (hash or filename check), disk space available
**On Failure**: "File already imported" skip or overwrite prompt

### Step 2b: Video Download (URL)

**Actor**: System
**Action**: `download_and_transcribe(url)` uses yt-dlp to download, extract audio, convert to MP3
**Validation**: yt-dlp executable available, ffmpeg for conversion, URL accessible
**On Failure**: "Download failed" with yt-dlp error details, suggest checking cookies/URL

### Step 3: Transcription

**Actor**: System
**Action**: `transcribe_file(file_path)` runs offline ASR with progress callbacks
**Validation**: Model loaded, audio file readable, valid audio format
**On Failure**: "Transcription failed" with error details

### Step 4: Progress Display

**Actor**: System
**Action**: Emit progress events `{ percent, info }` to frontend, display progress bar with segment count (e.g., "42% (15/30)")
**Validation**: Progress updates arrive regularly (< 1s interval)
**On Failure**: If progress stalls, show "Processing..." with elapsed time

### Step 5: Save Record

**Actor**: System
**Action**: Create record with transcript, audio metadata, and title (filename or video title)
**Validation**: Record saved successfully
**On Failure**: Retry, show "Save failed" error

### Step 6: Auto AI Process (optional)

**Actor**: System
**Action**: Same as WF-001 Step 7 - trigger if auto-process preset configured
**Validation**: AI preset valid
**On Failure**: Skip, notify user

---

## Post-conditions

- [ ] Audio file in `data/audio/`
- [ ] Record in SQLite with transcript
- [ ] Audio metadata in `audio_meta.json`
- [ ] Duration calculated and stored

---

## Error Handling

| Error Scenario | Detection | Recovery | User Feedback |
|---------------|-----------|----------|---------------|
| File not found | OS error | Check path | "File not found" |
| Duplicate file | audio_meta.json lookup | Skip or ask overwrite | "File already imported" |
| yt-dlp missing | `get_dependency_status()` | Prompt install | "Install yt-dlp first" |
| ffmpeg missing | Conversion error | Install static-ffmpeg | "Install ffmpeg first" |
| Cookie required | yt-dlp 403 error | Prompt cookie file | "Cookie may be required" |
| Network timeout | Download timeout | Retry option | "Download timed out" |
| Invalid audio | audioread error | Skip file | "Unsupported audio format" |

---

## Related

- **Business Rules**: BR-ASR-001, BR-DATA-001 (duplicate detection)
- **API Endpoints**: import_and_transcribe, download_and_transcribe, transcribe_file
- **State Machine**: File Transcription State Machine
- **Data Models**: records.csv
