# SherpaNote Bug Fix & Feature Implementation Plan

## Requirements Restatement

Six issues to resolve, categorized by complexity:

| # | Issue | Type | Complexity |
|---|-------|------|------------|
| 1 | Re-transcribe button belongs in EditorView + needs wiring | Bug/Feature | Low |
| 2 | Audio playback not working | Bug | Medium |
| 3 | Copy button for Transcript in EditorView | Feature | Low |
| 4 | Audio file cleanup on delete + audio management page | Feature | Medium |
| 5 | Recording state lost on view switch | Bug | High |
| 6 | Trilingual Paraformer model fails (protobuf error) | Bug | Medium |

---

## Phase 1: Low-Effort Fixes (Issues 1, 3)

### 1.1 Re-transcribe in EditorView

**Problem**: The re-transcribe button is on `RecordCard` (HomeView list) but should also appear inside EditorView when viewing a record with audio. Currently EditorView has no re-transcribe capability.

**Changes**:
- `frontend/src/views/EditorView.vue`:
  - Import `call`, `onEvent` from bridge
  - Add re-transcribe function (similar to `handleRecognize` in HomeView)
  - Add `onEvent("retranscribe_complete")` and `onEvent("transcribe_progress")` listeners in `onMounted`
  - Add re-transcribe button in the header area (next to version history / export), only visible when `record.audio_path` exists
  - On re-transcribe complete, update local `record.value` and `editorText.value`

### 1.2 Copy Button for Transcript

**Problem**: EditorView's Transcript section has no copy-to-clipboard button.

**Changes**:
- `frontend/src/views/EditorView.vue`:
  - Add a "Copy" button next to the "Transcript" heading (line ~310)
  - On click, `navigator.clipboard.writeText(editorText.value)`
  - Show brief toast feedback "Copied to clipboard"

---

## Phase 2: Audio Playback Fix (Issue 2)

**Problem**: EditorView uses `file://` protocol for audio `<audio :src="'file://' + record.audio_path">` which pywebview blocks by default (CORS/security).

**Approach**: Use pywebview's built-in `window.expose` or a local HTTP API endpoint to serve audio files. The cleanest approach is to add a backend API endpoint that returns audio file bytes, and reference it via a relative URL.

**Changes**:
- `pywebvue/app.py` or `main.py`:
  - Add an `@expose` method `get_audio_url(record_id: str)` that returns the audio path for pywebview to serve
  - Alternatively, use pywebview's `AssetLoader` or custom URL scheme to serve local files
- Better approach: Use pywebview's native `create_file_dialog` is not relevant here. Instead:
  - Add a lightweight HTTP route in pywebvue bridge that serves audio files from disk
  - OR: Convert audio to base64 and embed as data URL (works for small files)
  - OR: Use pywebview's `window.evaluate_js` with a custom protocol handler

**Recommended approach**: Add a backend endpoint `serve_audio(record_id)` that returns base64-encoded audio, and construct a data URL in the frontend. For large files, this is impractical. Instead, use pywebview's **window** object to serve local files:

Actually, the cleanest fix is to configure pywebview's `server` option or use its **API** feature. Since pywebvue wraps pywebview, we should check if there's already a mechanism.

**Revised approach**: Use `pywebview`'s built-in ability to map local directories. Add an audio serving endpoint via the existing bridge:
- `main.py`: Add `@expose get_audio_base64(record_id)` - reads audio file, returns base64
- `EditorView.vue`: Call `get_audio_base64`, construct `data:audio/wav;base64,...` URL
- This works because WAV files from recording are typically small (minutes of audio)

For large files (user-uploaded mp3/m4a), we can chunk or stream. But for MVP, base64 is sufficient.

**Files changed**:
- `main.py`: Add `get_audio_base64` endpoint
- `EditorView.vue`: Use data URL instead of `file://` protocol

---

## Phase 3: Model Compatibility Fix (Issue 6)

**Problem**: `sherpa-onnx-paraformer-trilingual-zh-cantonese-en` fails with "protobuf parsing failed". The trilingual model has a `model.onnx` file, which triggers the SenseVoice code path in `_create_offline_recognizer()` (line 514-523). But this model is a Paraformer, not SenseVoice.

**Root cause**: `_create_offline_recognizer` checks for `model.onnx` first (SenseVoice), but the trilingual Paraformer model also has `model.onnx`. The SenseVoice API expects a different model architecture, so loading a Paraformer as SenseVoice fails.

**Fix**: Need to distinguish between SenseVoice and Paraformer models. Options:
1. Check for model name/path pattern (model dir name contains "sense-voice")
2. Check for SenseVoice-specific files (e.g., `pd_model.onnx` or lack of `model.int8.onnx`)
3. Check if the model directory contains `model.int8.onnx` (Paraformer) vs just `model.onnx` (SenseVoice)

Looking at the model registry:
- SenseVoice models would have `model.onnx` but NOT `model.int8.onnx`
- Paraformer models have `model.int8.onnx` (or `model.onnx` as fallback)

**Revised detection logic** in `_create_offline_recognizer`:
```
1. If model.int8.onnx exists -> Paraformer
2. If model.onnx exists AND model_dir name contains "sense-voice" -> SenseVoice
3. If model.onnx exists AND model.int8.onnx does NOT exist AND encoder.onnx does NOT exist -> SenseVoice
4. If encoder.onnx + decoder.onnx exist -> Whisper
```

Actually, looking more carefully at sherpa-onnx models:
- `sherpa-onnx-paraformer-trilingual-zh-cantonese-en` has `model.int8.onnx` (same as other Paraformer models)
- But wait, the error says "Using SenseVoice offline model" then fails. This means `model.onnx` exists in the trilingual model dir but `model.int8.onnx` does NOT exist (or is checked second).

Let me re-read the code:
```python
sense_voice_model = model_dir / "model.onnx"
if sense_voice_model.exists():
    # Uses SenseVoice path <-- THIS IS THE BUG
    return sherpa_onnx.OfflineRecognizer.from_sense_voice(...)

paraformer_model = model_dir / "model.int8.onnx"
if not paraformer_model.exists():
    paraformer_model = model_dir / "model.onnx"
```

The SenseVoice check (`model.onnx`) runs FIRST and short-circuits. The Paraformer fallback never runs.

**Fix**: Reverse the priority or add smarter detection:
- Check for `model.int8.onnx` first (Paraformer indicator)
- Only use SenseVoice path if `model.onnx` exists but `model.int8.onnx` does NOT
- OR check model directory name for "sense-voice"

**Best approach**: Check `model.int8.onnx` first (Paraformer), then `model.onnx` with model-dir name heuristic.

**Files changed**:
- `py/asr.py`: `_create_offline_recognizer` method - reorder detection logic

---

## Phase 4: Recording State Persistence (Issue 5)

**Problem**: When recording or file-uploading, navigating away from RecordView and back resets all state. `RecordView.onUnmounted` calls `stopListening()` and `resetState()`, destroying the recording session.

**Approach**: Use a Pinia store to persist recording state across view switches, and prevent navigation while recording is active.

**Option A**: Prevent navigation entirely during recording (simpler)
- Add a global navigation guard in router
- Show toast "Cannot navigate while recording"
- Disable sidebar nav links during recording

**Option B**: Persist state and resume (more complex but better UX)
- Move recording state (isRecording, elapsedTime, etc.) to Pinia store
- Keep the streaming session alive across view switches
- RecordView picks up state on mount if session is active

**Recommended**: Option A (prevent navigation) is safer and simpler. Recording is a critical operation that shouldn't be interrupted. We can also auto-save on navigate-away attempt.

**Changes**:
- `frontend/src/stores/appStore.ts`: Add `isRecording` flag (already exists)
- `frontend/src/router/index.ts`: Add `beforeEach` navigation guard that checks `store.isRecording` and blocks navigation with a confirm dialog
- `RecordView.vue`: No changes needed (keep `onUnmounted` cleanup as safety net)
- Alternative: Disable navbar links during recording via `v-disabled` binding

**Files changed**:
- `frontend/src/router/index.ts`: Add navigation guard
- `frontend/src/App.vue`: Disable nav during recording (if navbar exists)

---

## Phase 5: Audio File Management (Issue 4)

**Problem**: Deleting a record does not delete the associated audio file. User wants:
- Default behavior: DB record deleted, audio file kept
- New feature: Audio file management page showing all audio files with "linked to record" status

### 5.1 Verify DB Cleanup

Current `storage.py:delete()` correctly removes from `records` and `versions` tables. This is fine.

### 5.2 Audio Management Page

**New view**: `AudioManageView.vue` at route `/audio`

**Backend**:
- `main.py`: Add `@expose list_audio_files()` - scans `data/audio/` directory, cross-references with DB records to show linked/unlinked status
- `main.py`: Add `@expose delete_audio_file(file_path)` - deletes a single audio file from disk
- `main.py`: Add `@expose get_audio_file_info(file_path)` - returns file size, duration, linked records

**Frontend**:
- `frontend/src/views/AudioManageView.vue`: Table/list showing audio files with columns: filename, size, linked record(s), actions (delete, open folder)
- Add route `/audio` in router
- Add nav link in App.vue navbar/sidebar

**Files changed**:
- `main.py`: Add 3 new endpoints
- `frontend/src/views/AudioManageView.vue`: New file
- `frontend/src/router/index.ts`: Add route
- `frontend/src/App.vue`: Add nav link

---

## Implementation Order

1. **Phase 1** (Issues 1, 3) - Simple UI additions, no backend changes
2. **Phase 3** (Issue 6) - Critical bug fix, small code change
3. **Phase 2** (Issue 2) - Audio playback, medium effort
4. **Phase 4** (Issue 5) - Recording state, router-level change
5. **Phase 5** (Issue 4) - Audio management, new page

## Risks

- **Phase 2**: Base64 approach may be slow for large audio files (>50MB). Mitigate by streaming or using pywebview's native file serving if available.
- **Phase 4**: Navigation guard may need fine-tuning for edge cases (e.g., browser back button, direct URL entry).
- **Phase 5**: Scanning large audio directories could be slow. Add pagination or lazy loading.
