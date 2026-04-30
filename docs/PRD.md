# Product Requirements Document (PRD)

> AI-powered voice learning assistant with local-first speech recognition, OCR, and AI text processing.

---

## Product Overview

### Background

SherpaNote is a desktop application designed for learners, researchers, and knowledge workers who need to capture, transcribe, and process spoken content and visual materials. Traditional note-taking requires manual effort to convert lectures, meetings, and documents into structured knowledge. SherpaNote automates this pipeline: record or import audio -> transcribe with local ASR -> process with AI -> organize and export.

All speech recognition runs locally (sherpa-onnx / whisper.cpp), ensuring privacy and offline availability. OCR and AI processing provide additional input channels and intelligent text enhancement.

### Core Value Proposition

| Value | Description |
|-------|-------------|
| Privacy-first ASR | All speech recognition runs locally, no audio data leaves the device |
| Multi-engine support | 10+ ASR models (Paraformer, SenseVoice, Whisper, Qwen3-ASR, FunASR) with GPU acceleration |
| AI-enhanced notes | Polish, summarize, mindmap, and brainstorm modes transform raw transcripts |
| OCR integration | Extract text from images and PDFs, integrate with existing records |
| Version control | Full edit history with version snapshots and restore capability |

### Target Users

| User Type | Use Case | Pain Point |
|-----------|----------|------------|
| Student | Record lectures, generate study notes | Manual transcription is slow and error-prone |
| Researcher | Process interviews and talks | Hard to organize and search audio content |
| Knowledge Worker | Meeting notes, document extraction | Switching between too many tools |
| Content Creator | Transcribe video/audio content | Need structured output from raw media |

---

## Functional Requirements

### Phase 1: Core Recording & Transcription

#### FR-1.1: Real-time Audio Recording

**As a** user, **I want** to record audio from my microphone, **so that** I can capture lectures, meetings, or dictation.

**Acceptance Criteria:**
- [ ] Record audio from system microphone with visual feedback
- [ ] Display real-time streaming transcription during recording (for supported models)
- [ ] Stop recording and save audio file to local storage
- [ ] Support switching ASR engine and model before/during recording
- [ ] Language selection (zh, en, auto-detect, +10 languages)

**Priority**: P0 (Must Have)

---

#### FR-1.2: Audio File Transcription

**As a** user, **I want** to import and transcribe existing audio files, **so that** I can process pre-recorded content.

**Acceptance Criteria:**
- [ ] Import audio files via drag-and-drop or file picker
- [ ] Transcribe with selectable ASR model and language
- [ ] Show transcription progress with segment count
- [ ] Detect duplicate files and skip re-import
- [ ] Support video download and transcription from URL (yt-dlp)

**Priority**: P0 (Must Have)

---

#### FR-1.3: Record Management

**As a** user, **I want** to browse, search, and organize my transcribed records, **so that** I can find and manage content efficiently.

**Acceptance Criteria:**
- [ ] List all records with title, duration, category, tags, and timestamp
- [ ] Filter records by category and search by keyword
- [ ] Edit record title, category, and tags
- [ ] Delete records with confirmation
- [ ] Play back audio inline with volume control

**Priority**: P0 (Must Have)

---

### Phase 2: AI Processing

#### FR-2.1: AI Text Processing Modes

**As a** user, **I want** to process transcribed text with AI, **so that** I can generate polished notes, summaries, mind maps, and more.

**Acceptance Criteria:**
- [ ] Support processing modes: polish, note, mindmap, brainstorm
- [ ] Streaming response with real-time display
- [ ] Cancel processing mid-stream
- [ ] Custom prompt override for any mode
- [ ] "Continue output" when response is truncated
- [ ] Auto-save AI results to record

**Priority**: P0 (Must Have)

---

#### FR-2.2: Multi-Provider AI Configuration

**As a** user, **I want** to configure multiple AI API providers, **so that** I can switch between OpenAI, OpenRouter, or custom endpoints.

**Acceptance Criteria:**
- [ ] Save multiple API presets (provider, model, API key, endpoint)
- [ ] Switch between presets at runtime
- [ ] Test connection before use
- [ ] Support OpenAI-compatible API format
- [ ] Customizable built-in prompt templates per mode

**Priority**: P1 (Should Have)

---

### Phase 3: Version Control

#### FR-3.1: Record Version History

**As a** user, **I want** to track changes to my records over time, **so that** I can review and restore previous versions.

**Acceptance Criteria:**
- [ ] Auto-create version snapshot when record content changes
- [ ] View version history with diff indicators
- [ ] Restore any previous version
- [ ] Delete individual versions
- [ ] Dirty state tracking (unsaved changes indicator)

**Priority**: P1 (Should Have)

---

### Phase 4: OCR

#### FR-4.1: Image and PDF Text Recognition

**As a** user, **I want** to extract text from images and PDFs, **so that** I can digitize printed materials.

**Acceptance Criteria:**
- [ ] OCR processing for images (PNG, JPG, BMP)
- [ ] OCR processing for PDF files (multi-page)
- [ ] Batch mode: each page/image creates a separate record
- [ ] Sequential mode: merge all OCR results into one record
- [ ] Auto-prefix OCR records with "OCR-" for easy identification
- [ ] Configurable OCR models (PP-OCRv4/v5, mobile/server variants)

**Priority**: P1 (Should Have)

---

### Phase 5: Export & Import

#### FR-5.1: Record Export

**As a** user, **I want** to export records in multiple formats, **so that** I can share or archive my content.

**Acceptance Criteria:**
- [ ] Export as Markdown (.md)
- [ ] Export as plain text (.txt)
- [ ] Export as Word document (.docx)
- [ ] Export as SRT subtitle file (.srt)
- [ ] Option to include/exclude AI processing results

**Priority**: P1 (Should Have)

---

#### FR-5.2: Data Backup & Restore

**As a** user, **I want** to backup and restore all my data, **so that** I can migrate between devices.

**Acceptance Criteria:**
- [ ] Backup app configuration, presets, records, and audio files
- [ ] Selective backup (choose which data types to include)
- [ ] Restore from backup with cross-platform compatibility
- [ ] Import individual record files

**Priority**: P1 (Should Have)

---

## Non-Functional Requirements

### Performance

| Metric | Target |
|--------|--------|
| App startup time | < 3s |
| ASR streaming latency | < 500ms per segment |
| AI response first token | < 2s |
| OCR processing (single image) | < 5s |
| UI interaction response | < 100ms |
| Memory usage (idle) | < 200MB |

### Privacy & Security

| Requirement | Implementation |
|-------------|---------------|
| Local ASR processing | All speech recognition on-device, no cloud upload |
| No telemetry | No usage data sent externally |
| Config stored locally | API keys and settings in local SQLite |
| Audio files local | All media stored in app data directory |

### Compatibility

| Platform | Version |
|----------|---------|
| Windows | 10+ (64-bit) |
| macOS | 12+ (Apple Silicon & Intel) |
| Python | 3.11+ |
| Node | 20+ |

---

## Design Direction

### Visual Style

- Desktop application with native window frame (pywebview)
- Dark/light theme toggle (DaisyUI theming)
- Clean, minimal interface with focus on content
- Mobile-first responsive within desktop window

---

## Out of Scope

- Cloud sync / multi-device synchronization
- Real-time collaboration
- Video recording / screen capture
- Plugin/extension system
- Mobile app (iOS/Android)
- Speech synthesis (TTS output)
- Online ASR services (all recognition is local)

---

## Success Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| User adoption | 0 | 100+ active users | GitHub stars / downloads |
| Feature completeness | v1.0 | All P0+P1 features | Release checklist |
| Transcription accuracy | N/A | Comparable to cloud ASR | User feedback / benchmarks |
| Cross-platform stability | Windows only | Windows + macOS | CI test passes |
| User satisfaction | N/A | Positive feedback | GitHub issues / discussions |
