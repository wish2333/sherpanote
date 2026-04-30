# AI Text Processing

## Metadata

- **ID**: WF-004
- **Version**: 1.1.0
- **Owner**: LLM Module (py/llm.py, main.py)
- **Trigger**: User clicks process button on EditorView, or auto-process after transcription
- **Last Updated**: 2026-04-29

---

## Overview

Process transcribed text with AI via OpenAI-compatible API. Supports multiple processing modes (polish, note, mindmap, brainstorm) with streaming responses. Multiple API presets allow switching between providers. Results auto-save to record.

---

## Pre-conditions

- [ ] Record has non-empty transcript
- [ ] At least one AI preset is configured with valid API key
- [ ] AI provider endpoint is reachable
- [ ] User is on EditorView page

---

## Flow

### Step 1: Select Processing Mode

**Actor**: User
**Action**: Choose mode from: polish, note, mindmap, brainstorm (or custom prompt)
**Validation**: Mode is recognized
**On Failure**: Default to "polish" mode

### Step 2: Select AI Preset (if multiple)

**Actor**: User
**Action**: Switch between configured presets via dropdown
**Validation**: Preset has valid API key and endpoint
**On Failure**: Show "Invalid preset" error

### Step 3: Start Processing

**Actor**: User
**Action**: Click process button, `process_text_stream(text, mode, custom_prompt, record_id)` called
**Validation**: Transcript is non-empty, API connection available
**On Failure**: Show error dialog, suggest checking API key

### Step 4: Streaming Display

**Actor**: System
**Action**: Stream tokens via `on_token(chunk)` callback, render in MarkdownRenderer or MindMapPreview
**Validation**: Tokens arrive with < 2s first-token latency
**On Failure**: If stream breaks, show partial result, offer retry

### Step 5: Cancel (optional)

**Actor**: User
**Action**: Click cancel button, `cancel_ai()` aborts stream
**Validation**: Stream is actually terminated
**On Failure**: Force cancel, discard partial result

### Step 6: Auto-save Result

**Actor**: System
**Action**: `_persist_ai_result(record_id, mode, result)` saves AI output to `ai_results_json` field, creates version if content changed
**Validation**: Result non-empty, record exists
**On Failure**: Show "Save failed" error, offer manual retry

### Step 7: Continue Output (if truncated)

**Actor**: User
**Action**: Click "Continue" button, `continue_text_stream(previous_output, mode, custom_prompt, record_id)` appends to previous output
**Validation**: Previous output exists
**On Failure**: Re-process from scratch

---

## Post-conditions

- [ ] AI result saved to record's `ai_results_json`
- [ ] Version snapshot created if content changed
- [ ] Result visible in EditorView

---

## Error Handling

| Error Scenario | Detection | Recovery | User Feedback |
|---------------|-----------|----------|---------------|
| API key invalid | 401 response | Prompt update key | "Invalid API key" |
| Rate limit | 429 response | Auto-retry with backoff | "Rate limited, retrying..." |
| Network error | Connection timeout | Retry 3 times | "Network error" |
| Response too long | Truncation detected | Show "Continue" button | "Output truncated" |
| Model not found | API error | Suggest check model name | "Model not found" |
| Empty transcript | Input check | Block processing | "No text to process" |

---

## Related

- **Business Rules**: BR-AI-001 (processing modes), BR-AI-002 (preset management)
- **API Endpoints**: process_text_stream, cancel_ai, continue_text_stream, test_ai_connection
- **State Machine**: Record State Machine (draft -> processing -> completed)
- **Data Models**: records.csv (ai_results_json field)
