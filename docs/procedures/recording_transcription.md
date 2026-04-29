# Audio Recording & Transcription

## Metadata

- **ID**: WF-001
- **Version**: 1.0.0
- **Owner**: ASR Module (py/asr.py, main.py)
- **Trigger**: User clicks record button on RecordView
- **Last Updated**: 2026-04-29

---

## Overview

Real-time audio recording from system microphone with optional streaming transcription. User selects ASR engine (sherpa-onnx or whisper.cpp), model, and language before recording. Audio is captured via Web Audio API, converted to PCM, and sent as base64 chunks to the backend for streaming recognition.

---

## Pre-conditions

- [ ] ASR model is installed (at least one model in models/ directory)
- [ ] Microphone permission is granted (macOS requires explicit permission)
- [ ] No other recording session is active
- [ ] App window is on RecordView page

---

## Flow

### Step 1: Model Selection

**Actor**: User
**Action**: Select ASR engine (sherpa-onnx / whisper.cpp), model, and language from quick settings bar
**Validation**: Model must exist in installed models list; whisper.cpp requires binary installed
**On Failure**: Show "Model not found" error, prompt user to install model

### Step 2: Model Initialization

**Actor**: System
**Action**: `init_model(language)` loads ASR model into memory, prepares streaming config
**Validation**: Model file exists, language is supported, GPU config if applicable
**On Failure**: Show initialization error dialog, return to idle state

### Step 3: Start Streaming

**Actor**: System
**Action**: `start_streaming()` begins capturing audio via Web Audio API, sends PCM chunks via `feed_audio(base64_data)`
**Validation**: Audio stream is active, sample rate matches model requirement (16kHz)
**On Failure**: Show "Recording failed" error, clean up resources

### Step 4: Real-time Display (simulated streaming)

**Actor**: System
**Action**: For models without native streaming, VAD segments audio and processes each segment, displaying partial results
**Validation**: VAD detects speech segments correctly
**On Failure**: Graceful degradation - display results when available

### Step 5: Stop Recording

**Actor**: User
**Action**: User clicks stop button, `stop_streaming()` finalizes transcript
**Validation**: Transcript is non-empty (or user confirms discard)
**On Failure**: If transcript is empty, ask user to retry or save without transcript

### Step 6: Save Record

**Actor**: System
**Action**: Audio saved as MP3 to `data/audio/`, transcript saved via `save_record()`, record created in SQLite
**Validation**: Audio file written successfully, record ID generated
**On Failure**: Retry save, show error if persistent

### Step 7: Auto AI Process (optional)

**Actor**: System
**Action**: If user has configured auto-process preset, automatically trigger AI processing on transcript
**Validation**: AI preset is valid and connected
**On Failure**: Skip auto-process, show notification, user can manually trigger later

---

## Post-conditions

- [ ] Audio file saved in `data/audio/` directory
- [ ] Record created in SQLite with transcript and metadata
- [ ] Audio metadata entry added to `audio_meta.json`
- [ ] Record visible in HomeView list
- [ ] (Optional) AI processing result saved to record

---

## Error Handling

| Error Scenario | Detection | Recovery | User Feedback |
|---------------|-----------|----------|---------------|
| Microphone not available | Browser API check | Check system settings | "Microphone not detected" |
| Model not installed | `init_model()` returns error | Prompt install | "Please install an ASR model first" |
| GPU not available | `detect_gpu()` returns false | Fall back to CPU | Silent fallback, show "Using CPU" |
| Audio too short (< 1s) | Duration check after stop | Discard or save | "Recording too short" |
| ASR crash during streaming | Exception in feed_audio | Stop recording, save partial | "Recognition error occurred" |

---

## Related

- **Business Rules**: BR-ASR-001 (Model selection), BR-ASR-002 (Language support)
- **API Endpoints**: init_model, start_streaming, feed_audio, stop_streaming, save_record
- **State Machine**: ASR Recording State Machine
- **Data Models**: records.csv
