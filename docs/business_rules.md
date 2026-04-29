# Business Rules

> Domain-specific rules that govern system behavior for SherpaNote.
> AI MUST consult these rules before implementing any feature.

---

## Version Change Index

| Version | Rule Area | Description |
|---------|-----------|-------------|
| v2.0.0 | BR-OCR | OCR naming, processing modes |
| v1.3.0 | BR-ASR, BR-MODEL | Whisper integration, GPU, model management |
| v1.2.0 | BR-MODEL | Multi-source download |
| v1.1.0 | BR-AI, BR-VER | Multi-preset, auto-process, versioning |
| v1.0.0 | Initial | All initial business rules |

---

## Rule: ASR (Automatic Speech Recognition)

### BR-ASR-001: Model Selection

| Rule | Description | Exception |
|------|-------------|-----------|
| sherpa-onnx primary | Default ASR engine is sherpa-onnx | User can switch to whisper.cpp |
| Model must exist | Cannot start recording without installed model | Show install prompt |
| Language match | Model must support selected language | Auto-detect mode bypasses this |
| GPU auto-detect | If NVIDIA GPU detected, prefer CUDA variant | User can force CPU mode |

### BR-ASR-002: Language Support

| Language | Code | Support |
|----------|------|---------|
| Chinese | zh | All models |
| English | en | All models |
| Auto-detect | auto | Paraformer, SenseVoice |
| Cantonese | yue | Trilingual Paraformer |
| Japanese | ja | Whisper models |
| Korean | ko | Whisper models |
| +10 more | various | Whisper models |

### BR-ASR-003: Audio Processing

| Rule | Description | Exception |
|------|-------------|-----------|
| Sample rate 16kHz | All audio resampled to 16kHz for ASR | Whisper.cpp handles its own resampling |
| MP3 output | Recorded/imported audio saved as MP3 | WAV for intermediate processing |
| Duration tracking | Audio duration calculated after transcription | N/A |
| Duplicate detection | Import checks `audio_meta.json` before copying | User can force re-import |

---

## Rule: AI Processing

### BR-AI-001: Processing Modes

| Mode | Purpose | Output Format |
|------|---------|---------------|
| polish | Improve readability, fix punctuation | Markdown text |
| note | Generate structured study notes | Markdown with headers |
| mindmap | Create mind map from content | Markdown list (hierarchical) |
| brainstorm | Generate ideas and expansions | Markdown text |

### BR-AI-002: Preset Management

| Rule | Description | Exception |
|------|-------------|-----------|
| At least one preset | Cannot process without configured AI preset | N/A |
| Active preset | One preset must be marked active | N/A |
| Test before use | Connection test required before first use | N/A |
| Custom prompts | User can override built-in prompts | Reset to default available |

### BR-AI-003: Auto-processing

| Rule | Description | Exception |
|------|-------------|-----------|
| Optional auto-process | After transcription, auto-trigger AI if configured | User can disable |
| Single mode only | Auto-process uses the configured default mode | N/A |
| Silent failure | Auto-process failure does not block record save | Show notification only |

---

## Rule: OCR (Optical Character Recognition)

### BR-OCR-001: Naming Convention

| Rule | Description | Exception |
|------|-------------|-----------|
| OCR prefix | Batch mode records auto-prefixed with "OCR-" | Single mode uses user-provided title |
| Source filename | Batch mode appends original filename after prefix | N/A |

### BR-OCR-002: Processing Modes

| Mode | Behavior | Record Count |
|------|----------|-------------|
| batch | Each image/page becomes a separate record | N records (N = files + pages) |
| single | All text merged into one record | 1 record |

### BR-OCR-003: Model Management

| Rule | Description | Exception |
|------|-------------|-----------|
| v4/v5 models | Support PP-OCRv4 and PP-OCRv5 detection models | N/A |
| Mobile/Server | Mobile (lightweight) and Server (accurate) variants | N/A |
| Component-based | det (detection), rec (recognition), cls (classification) managed separately | N/A |

---

## Rule: Versioning

### BR-VER-001: Version Limits

| Setting | Value | Description |
|---------|-------|-------------|
| Max versions per record | 20 | Oldest versions pruned when exceeded |
| Auto-version threshold | Content changed | Version created only when content actually differs |
| Version numbering | Sequential integers | Starts from 1, increments per record |

### BR-VER-002: Auto-versioning Triggers

| Action | Creates Version |
|--------|----------------|
| save_record() with content change | Yes (if transcript or AI results differ) |
| retranscribe_record() | Yes (snapshot before overwrite) |
| AI result persist | Yes (via _persist_ai_result) |
| Manual save_version() | Always |
| Edit title/category/tags | No |
| mark_dirty/mark_clean | No |

---

## Rule: Model Management

### BR-MODEL-001: Download Sources

| Source | URL Pattern | Notes |
|--------|------------|-------|
| HuggingFace | huggingface.co | Default, requires internet |
| HF Mirror | hf-mirror.com | China mirror of HuggingFace |
| GitHub Proxy | github.com/proxy | Alternative for blocked regions |
| ModelScope | modelscope.cn | Chinese AI community |

### BR-MODEL-002: Model Types

| Type | Description | Examples |
|------|-------------|---------|
| streaming | Real-time recognition models | Paraformer (streaming) |
| offline | File transcription models | Paraformer (offline), Whisper |
| vad | Voice Activity Detection | silero-vad |

### BR-MODEL-003: Whisper.cpp Specific

| Rule | Description | Exception |
|------|-------------|-----------|
| Binary required | whisper-cli binary must be installed separately | N/A |
| Multi-variant | cpu/blas/cuda variants available | Auto-select based on GPU |
| Multi-version | Multiple whisper model sizes can coexist | N/A |

---

## Rule: Data Validation

### BR-DATA-001: Record Validation

| Field | Validation | Error Message |
|-------|-----------|---------------|
| id | Non-empty UUID | Auto-generated |
| title | Optional, max 500 chars | "Title too long" |
| transcript | Optional text | N/A |
| category | Optional string | N/A |
| tags | JSON array of strings | "Invalid tags format" |
| audio_path | Valid path or empty | "Audio file not found" |

### BR-DATA-002: AI Config Validation

| Field | Validation | Error Message |
|-------|-----------|---------------|
| api_key | Non-empty when provider requires | "API key required" |
| base_url | Valid URL format | "Invalid API endpoint" |
| model | Non-empty string | "Model name required" |

---

## Rule: Error Handling

### Error Response Rules

| Error Type | User Message | Log Level | Retry |
|------------|-------------|-----------|-------|
| Network timeout | "Network error, please check connection" | WARN | Yes (3x) |
| API auth failure | "Invalid API key, please check settings" | ERROR | No |
| Model not found | "Model not installed" | INFO | No |
| File not found | "File not found" | WARN | No |
| OCR no text | "No text detected in image" | INFO | No |
| Disk full | "Insufficient disk space" | ERROR | No |

### Error Recovery Rules

| Scenario | Auto Recovery | Manual Recovery |
|----------|--------------|-----------------|
| Download timeout | Retry with backoff (3 attempts) | Switch download source |
| ASR crash | Restart model | Restart app |
| AI stream break | Save partial result | Re-process manually |
| DB corruption | N/A | Restore from backup |

---

## Rule: Defaults and Limits

| Setting | Default | Max | Min |
|---------|---------|-----|-----|
| Audio recording sample rate | 16000 Hz | 48000 Hz | 16000 Hz |
| Max versions per record | 20 | 50 | 1 |
| Model download retries | 3 | 5 | 1 |
| AI max_tokens | Auto-calculated | Model limit | 100 |
| Search keyword length | - | 200 chars | 1 char |
| Record title length | - | 500 chars | 0 (optional) |
| VAD silence threshold | 0.8s | 3s | 0.3s |
| OCR batch size | Unlimited | - | 1 file |
