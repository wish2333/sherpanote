## 1. Fix Audio File Upload (MP3 System Error)

- [x] 1.1 Add `audioread` to project dependencies (pyproject.toml)
- [x] 1.2 Implement `_read_with_audioread()` helper in `py/io.py` that reads audio via audioread and converts to 16kHz mono float32 PCM
- [x] 1.3 Modify `read_audio_as_mono_16k()` in `py/io.py` to catch soundfile exceptions and fall back to `_read_with_audioread()`
- [x] 1.4 Add error logging with the original exception details when both decoders fail

## 2. Fix Drag-and-Drop Interaction

- [x] 2.1 Create `useDragDrop` composable in `frontend/src/composables/useDragDrop.ts` with drag counter logic (dragenter +1, dragleave -1)
- [x] 2.2 Add window-level `dragover` and `drop` event listeners in `useDragDrop` to prevent pywebview from passing files to the OS default handler
- [x] 2.3 Refactor `HomeView.vue` to use the new `useDragDrop` composable, replacing the boolean `isDraggingOver` with the counter-based approach
- [x] 2.4 Refactor `RecordView.vue` to use the new `useDragDrop` composable, replacing the boolean `isDraggingFile` with the counter-based approach
- [x] 2.5 Ensure global drag prevention only blocks file-type drags (check `dataTransfer.types` contains `Files`)

## 3. Audio Persistence After Recording

- [x] 3.1 Modify `SherpaASR.start_streaming()` in `py/asr.py` to pass `output_dir=<data_dir>/audio` to `PcmRecorder`
- [x] 3.2 Ensure `data/audio/` directory is created in `ensure_data_dir()` in `py/io.py`
- [x] 3.3 Verify that `stop_streaming()` returns `audio_path` and that the frontend `handleRecordingComplete` correctly passes it to `saveAsRecord()`

## 4. Manual Recognition Button

- [x] 4.1 Add `retranscribe_record(record_id)` method to `SherpaNoteAPI` in `main.py` that reads the record's `audio_path`, calls `transcribe_file`, and updates the record with new results
- [x] 4.2 Emit `transcribe_progress` events during re-transcription for progress feedback
- [x] 4.3 Handle error cases: missing record, missing audio file, no ASR model
- [x] 4.4 Add "Recognize" button to `RecordCard.vue` that is visible only when `audio_path` is not null
- [x] 4.5 Add re-transcription logic in the frontend that calls the new API and updates the record in the list

## 5. sherpa-onnx Diagnostic Script

- [x] 5.1 Create `scripts/test_sherpa.py` with uv script header (`# /// script`) declaring dependencies (sherpa-onnx, numpy, soundfile, audioread)
- [x] 5.2 Implement model directory scanning: list all found streaming and offline models with paths
- [x] 5.3 Implement `--file <path>` mode: load offline model, transcribe audio file, output results with timing logs
- [x] 5.4 Implement `--streaming` mode: load streaming model, simulate audio chunk feeding, output real-time results
- [x] 5.5 Add detailed logging for every step: model detection, model loading (with timing), audio file info (duration, sample rate, channels), inference timing, transcription results
- [x] 5.6 Add audio file readability validation using the same `soundfile` + `audioread` fallback pipeline as the main app
- [x] 5.7 Add helpful error messages when audio file cannot be decoded (suggest ffmpeg installation)
