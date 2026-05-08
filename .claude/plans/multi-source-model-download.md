# Implementation Plan: Multi-Source ASR Model Download System

## Overview

Replace the current single-URL mirror download system with a structured multi-source download system supporting HuggingFace, HF-Mirror, GitHub, GitHub Proxy, and ModelScope. Also update the model catalog with newer models, add proxy settings, and provide manual download links in settings.

## Architecture Changes

| File | Change |
|------|--------|
| `py/model_registry.py` | Major rewrite: new `ModelEntry` with per-source URLs, updated catalog |
| `py/model_manager.py` | Add proxy support, `huggingface_hub` download path, multi-source dispatch |
| `py/config.py` | Replace `mirror_url` with `download_source`, `custom_ghproxy_domain`, `proxy_mode`, `proxy_url` |
| `py/asr.py` | Add Qwen3-ASR and funasr-nano recognizer detection/creation |
| `main.py` | Update bridge: `install_model` now accepts source context, new `get_download_links` |
| `frontend/src/types.ts` | Updated source types and config fields |
| `frontend/src/views/SettingsView.vue` | New source selector, proxy settings, manual download links, updated model list |
| `frontend/src/bridge.ts` | Updated model-related helper signatures |
| `pyproject.toml` | Add `huggingface_hub` dependency |

---

## Phase 1: Config & Registry Data Models (3 files)

### 1.1 Update `AsrConfig` (`py/config.py`)
- Replace `mirror_url: str | None` with structured fields:
  - `download_source: str = "github"` -- "huggingface" | "hf_mirror" | "github" | "ghproxy" | "modelscope"
  - `custom_ghproxy_domain: str | None = None`
  - `proxy_mode: str = "none"` -- "none" | "system" | "custom"
  - `proxy_url: str | None = None`
- **Migration**: `from_dict` checks for old `mirror_url` key and maps to new `download_source`
- Risk: Medium -- backward compat migration needed

### 1.2 Redesign `ModelEntry` (`py/model_registry.py`)
- New fields on `ModelEntry`:
  - `sha256: str | None = None`
  - `sources: tuple[str, ...]` -- which sources carry this model
  - `hf_repo_id: str | None`, `hf_filename: str | None` -- HuggingFace specifics
  - `modelscope_model_id: str | None`, `modelscope_file_path: str | None`
  - `manual_download_links: tuple[dict[str, str], ...]` -- for manual-only items
- Replace `GITHUB_BASE_URL` constant with `get_download_url(model, source, ghproxy_domain)` function
- Risk: Medium -- core data structure

### 1.3 Update frontend types (`frontend/src/types.ts`)
- Update `AsrConfig` interface with new fields
- Add `sources` and `manual_download_links` to `ModelEntry`
- Risk: Low

---

## Phase 2: New Model Catalog (1 file)

### 2.1 Replace model catalog (`py/model_registry.py`)

**Retained models (backward compat):**
- `sherpa-onnx-streaming-paraformer-bilingual-zh-en` (streaming)
- `silero_vad` (VAD)

**New offline models:**
| Model | Sources | Size |
|-------|---------|------|
| sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25 | GH, HF, HF-Mirror | TBD |
| sherpa-onnx-sense-voice-funasr-nano-2025-12-17 | GH, HF, HF-Mirror, MS | TBD |
| sherpa-onnx-whisper-distil-large-v3.5 | GH, HF, HF-Mirror | TBD |
| sherpa-onnx-whisper-distil-large-v3 | GH, HF, HF-Mirror | TBD |
| sherpa-onnx-paraformer-zh-small-2024-03-09 | GH, HF, HF-Mirror, MS | 74MB |

**New streaming models:**
| Model | Sources | Notes |
|-------|---------|-------|
| sherpa-onnx-funasr-nano-int8-2025-12-30 | GH, HF, HF-Mirror, MS | Low-latency real-time |
| sherpa-onnx-streaming-paraformer-bilingual-zh-en | GH, HF, HF-Mirror | Retained |
| sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20 | GH, HF, HF-Mirror | New |

**Manual download links only (subtitle tools):**
- sherpa-onnx generate-subtitles sense_voice zh_en_ko_ja_yue
- sherpa-onnx generate-subtitles paraformer_2023_09_14 zh_en

**VAD:** silero_vad (retained, all sources)

### 2.2 Multi-source URL resolver (`py/model_registry.py`)
- `get_download_url(model, source, ghproxy_domain=None)`:
  - `github`: `https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{archive_name}`
  - `huggingface`: `https://huggingface.co/{hf_repo_id}/resolve/main/{hf_filename}`
  - `hf_mirror`: same as HF but endpoint `https://hf-mirror.com`
  - `ghproxy`: `{ghproxy_domain}/https://github.com/.../{archive_name}`
  - `modelscope`: `https://modelscope.cn/api/v1/models/{model_id}/repo?Revision=master&FilePath={file_path}`
- Risk: Medium -- ModelScope URL pattern needs runtime verification

---

## Phase 3: Download Infrastructure (2 files)

### 3.1 Add `huggingface_hub` dependency (`pyproject.toml`)
- Add `"huggingface_hub>=0.20.0"` to dependencies
- Risk: Low

### 3.2 Proxy support in `download_archive` (`py/model_manager.py`)
- Accept `proxy_url` parameter
- `"none"` -> `ProxyHandler({})` (explicitly bypass)
- `"system"` -> no handler (Python default uses system proxy)
- `"custom"` -> `ProxyHandler({"http": url, "https": url})`
- Risk: Medium -- proxy format edge cases

### 3.3 HuggingFace download path (`py/model_manager.py`)
- New `download_from_huggingface(repo_id, filename, endpoint, proxy_url, ...)` using `huggingface_hub.hf_hub_download()`
- Handles progress reporting and cancellation
- Risk: Medium

### 3.4 ModelScope download path (`py/model_manager.py`)
- Uses direct HTTP URL, reuses `download_archive()` with ModelScope URL
- Risk: Medium -- API may need auth/redirect handling

### 3.5 Unified download dispatcher (`py/model_manager.py`)
- `download_model(model, source, dest_path, ghproxy_domain, proxy_mode, proxy_url, ...)` routes to correct download function
- Risk: Low

### 3.6 Update `ModelInstaller` (`py/model_manager.py`)
- Accept new source/proxy params in `__init__`
- Use `download_model()` dispatcher in `_install()`
- Enable SHA256 verification with `entry.sha256`
- Risk: Medium

---

## Phase 4: ASR Recognizer Integration (1 file)

### 4.1 Qwen3-ASR offline recognizer (`py/asr.py`)
- Detect by directory name `"qwen3"` or `"qwen3-asr"`
- Try `from_sense_voice()` first (likely API for this model type)
- If sherpa-onnx has dedicated `from_qwen3_asr()`, use that
- **Risk: HIGH** -- Qwen3-ASR support in sherpa-onnx needs runtime verification
- Mitigation: Add try/except with clear error message about required sherpa-onnx version

### 4.2 FunASR nano recognizer (`py/asr.py`)
- If files match Paraformer pattern -> use `from_paraformer()`
- If files match SenseVoice pattern -> use `from_sense_voice()`
- Add to `_find_streaming_model()` fallback list
- Risk: Medium

### 4.3 Update model discovery fallbacks (`py/asr.py`)
- Add new model names to `_find_streaming_model()` and `_find_offline_model()` candidate lists
- Risk: Low -- purely additive

---

## Phase 5: Bridge API Updates (1 file)

### 5.1 Update `SherpaNoteAPI` (`main.py`)
- Pass new config fields to `ModelInstaller`
- Update `install_model()` to create installer with current source/proxy settings
- Update `list_available_models()` to include `sources` and `manual_download_links`
- Add `get_download_links(model_id)` exposed method
- Risk: Low

---

## Phase 6: Frontend Settings UI (2 files)

### 6.1 Redesign download source selector (`SettingsView.vue`)
- Dropdown: HuggingFace / HF-Mirror / GitHub (default) / GitHub Proxy / ModelScope
- Conditional inputs:
  - `ghproxy`: show domain input with placeholder from ghproxy.link
  - `modelscope`: show info text about limited model availability
- Risk: Medium

### 6.2 Add proxy settings section (`SettingsView.vue`)
- Proxy mode: None / System / Custom
- Conditional: custom URL input when "Custom" selected
- Risk: Low

### 6.3 Manual download links display (`SettingsView.vue`)
- Collapsible "Manual Download" section per model with clickable links
- Separate "Tools" section for subtitle generation tools (links only)
- Risk: Low

### 6.4 Source availability badges (`SettingsView.vue`)
- Show source badges (HF, MS, GH) on each model
- Gray out "Download" button when model unavailable on selected source
- Risk: Low

### 6.5 Update bridge helpers (`bridge.ts`)
- Add `getDownloadLinks(modelId)` helper
- Risk: Low

---

## Key Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| sherpa-onnx may not support Qwen3-ASR | HIGH | Try `from_sense_voice()` first; add version check |
| ModelScope API URL pattern unknown | MEDIUM | Verify at runtime; fallback to manual links |
| `huggingface_hub` increases bundle size | MEDIUM | Optional dep; fallback to raw HTTP if needed |
| Old models break for existing users | LOW | Keep old entries in catalog; disk scan still finds them |
| New recognizer types may need newer sherpa-onnx | HIGH | try/except with clear upgrade error messages |

## Manual Test Checklist

- [ ] Config migration: old `mirror_url` loads without error
- [ ] All 5 download sources work (test with small model)
- [ ] Proxy: none/system/custom all affect download behavior
- [ ] Qwen3-ASR model downloads and transcribes successfully
- [ ] FunASR nano works for streaming
- [ ] Old installed models still appear and work
- [ ] Manual download links are clickable and correct
- [ ] Source badges show correctly; unavailable models are grayed out
- [ ] Download cancel + resume works
- [ ] Subtitle tools show as links only (not downloadable through app)
