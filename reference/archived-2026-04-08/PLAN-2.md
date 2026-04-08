# Implementation Plan: SherpaNote User Feedback Fixes (2026.04.08)

## Requirements Restatement

Six user-reported issues need to be addressed:

1. **Audio Manager transcription lost on navigation** - When transcribing in AudioManageView, switching to another page causes the record to not be saved correctly (event listeners are cleaned up on unmount).
2. **Multi-provider API preset management** - Users need to save multiple API configurations (multiple OpenAI-format providers, OpenRouter, etc.) and quickly switch between them.
3. **Transcription lacks punctuation** - Offline ASR output has no punctuation marks; this can be improved with an LLM-based post-processing step or different ASR models.
4. **AI processing preset management** - Users need named presets with custom prompts, default behaviors, and the ability to combine/batch process and one-click export.
5. **Version History appears non-functional** - The version history feature works but may appear empty because versions are only created on text edits, not on AI saves or initial creation.
6. **Export "AI" checkbox appears non-functional** - The AI toggle in ExportMenu works but is confusing UI since it's just a checkbox label.

---

## Analysis & Root Causes

### Issue 1: Transcription lost on page navigation
**Root cause**: `AudioManageView.vue:157-160` - `onBeforeUnmount` calls `cleanupFns.forEach(fn => fn())` which removes the `transcribe_complete` and `transcribe_error` event listeners. When the user navigates away, the backend thread finishes transcription and emits `transcribe_complete`, but no listener exists to handle it.

**Fix**: Reuse the existing `import_and_transcribe` backend endpoint which already handles the full flow (transcribe + save) in a background thread. The frontend just needs to wait for the completion event and navigate.

### Issue 2: Multi-provider API presets
**Current state**: `AiConfig` is a single frozen dataclass stored in `app_config` JSON blob. Only one AI provider can be active at a time with manual switching.

**Fix**: Add an `ai_presets` table to SQLite for storing multiple preset configurations. Add a preset selector UI in Settings and a quick-switch dropdown in the AI processing panel.

### Issue 3: No punctuation in transcription
**Root cause**: sherpa-onnx offline models (Paraformer, Whisper) output raw tokens without punctuation.

**Fix**: Add an optional LLM-based punctuation restoration post-processing step after ASR transcription. Use a lightweight prompt through the existing AI pipeline. Make it opt-in via a settings toggle.

### Issue 4: AI processing preset management
**Current state**: `llm.py` has 4 hardcoded prompt templates. Users cannot create custom prompts or save configurations.

**Fix**: Add an `ai_processing_presets` table to SQLite. Each preset has: name, prompt template, default mode. UI in Settings allows CRUD on presets. The AiProcessor panel gets a preset selector.

### Issue 5: Version History appears non-functional
**Root cause**: Versions are only created when `save()` is called with an existing record ID (storage.py:96-104). Initial record creation does not count as a version. The history button is a small icon that users may not notice.

**Fix**: Create an initial version (v1) on first save. Add a version count badge on the history button for discoverability.

### Issue 6: Export "AI" checkbox confusing
**Root cause**: The checkbox labeled "AI" (ExportMenu.vue:68-71) is technically functional but the UX is poor - bare checkbox with tiny label, easy to miss.

**Fix**: Move the toggle inside the dropdown menu as a labeled item with clearer text.

---

## Implementation Phases

### Phase 1: Bug Fix - Audio Manager Transcription Persistence [Critical]

**Files modified**:
- `AudioManageView.vue` - Update `handleTranscribe` to call `import_and_transcribe` instead of `transcribe_file` + manual `save_record`

**Approach**: The existing `import_and_transcribe` backend endpoint already does exactly what we need - it copies the file (if needed), transcribes it, saves the record, and emits `import_transcribe_complete` with the record data. Since the file is already in `data/audio/`, the copy is essentially a no-op (same path). The key improvement is that the backend thread handles the `save_record` call, so navigation away from AudioManageView won't lose the result.

**Specific changes in `AudioManageView.vue`**:
1. Change `handleTranscribe` to call `import_and_transcribe` instead of `transcribe_file`
2. Listen for `import_transcribe_complete` event instead of `transcribe_complete`
3. Remove the manual `save_record` call from the event handler
4. On completion, navigate to the editor page
5. Remove the `TranscriptRecord` interface import if no longer needed

---

### Phase 2: Multi-Provider API Presets [High Priority]

**Files created**:
- `py/presets.py` - PresetStore class for CRUD on AI presets (SQLite table operations)

**Files modified**:
- `main.py` - Add CRUD endpoints: `list_ai_presets`, `create_ai_preset`, `update_ai_preset`, `delete_ai_preset`, `set_active_ai_preset`
- `SettingsView.vue` - Add preset management section in AI tab (list, add, edit, delete, activate)
- `AiProcessor.vue` - Add quick preset switcher dropdown at top of panel
- `frontend/src/types.ts` - Add `AiPreset` type definition
- `frontend/src/stores/appStore.ts` - Store preset list and active preset ID

**Data model**:
```sql
CREATE TABLE IF NOT EXISTS ai_presets (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    provider    TEXT NOT NULL DEFAULT 'openai',
    model       TEXT NOT NULL,
    api_key     TEXT,
    base_url    TEXT,
    temperature REAL NOT NULL DEFAULT 0.7,
    max_tokens  INTEGER NOT NULL DEFAULT 4096,
    is_active   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

**UI Design**:
- Settings AI tab: "API Presets" card above the current config form
- Preset list showing: name, provider badge, model name
- "Add Preset" button -> inline form (name, provider, model, api_key, base_url, temperature)
- Active preset highlighted with a checkmark; click any preset to activate
- Edit/Delete actions per preset
- When a preset is activated, populate the config form below for fine-tuning
- AiProcessor panel: small dropdown at top to switch active preset without leaving the page

---

### Phase 3: Punctuation Restoration [Medium Priority]

**Files modified**:
- `py/llm.py` - Add `restore_punctuation(text: str) -> str` method with a lightweight prompt
- `py/config.py` - Add `auto_punctuate: bool = True` to `AsrConfig`
- `main.py` - Add punctuation step in `transcribe_file`, `import_and_transcribe`, `retranscribe_record` background threads
- `SettingsView.vue` - Add "Auto Punctuation" toggle in ASR settings section

**Approach**:
- After ASR produces raw text, if `auto_punctuate` is enabled AND AI is configured, run a fast LLM call
- Prompt: "Add punctuation marks (commas, periods, question marks, etc.) to the following text. Output only the punctuated text without any other changes.\n\nText: {text}"
- Apply to the full concatenated text before saving the record
- If AI is not configured or the call fails, silently fall back to raw text (log a warning)
- The punctuation call is non-streaming for speed

---

### Phase 4: AI Processing Preset Management [Medium Priority]

**Files created**:
- `py/processing_presets.py` - ProcessingPresetStore class

**Files modified**:
- `py/storage.py` - Add `ai_processing_presets` table to schema init
- `py/llm.py` - Support custom prompts from presets in `process()` and `process_stream()`
- `main.py` - CRUD endpoints for processing presets
- `AiProcessor.vue` - Preset selector and custom prompt editor UI
- `SettingsView.vue` - Add "AI Processing Presets" tab/section
- `frontend/src/types.ts` - Add `AiProcessingPreset` type

**Data model**:
```sql
CREATE TABLE IF NOT EXISTS ai_processing_presets (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    mode        TEXT NOT NULL DEFAULT 'custom',
    prompt      TEXT NOT NULL,
    is_default  INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

**Built-in presets** (seeded on first run):
1. Polish (existing hardcoded prompt)
2. Notes (existing hardcoded prompt)
3. Mind Map (existing hardcoded prompt)
4. Brainstorm (existing hardcoded prompt)

**Custom preset features**:
- Name, mode selection, custom prompt text area
- Mark as default for a mode
- In AiProcessor: preset dropdown replaces the hardcoded mode buttons
- When a custom preset is selected, show the prompt in a read-only field (editable in Settings)

---

### Phase 5: Version History Improvements [Low Priority]

**Files modified**:
- `py/storage.py` - Create initial v1 version snapshot on first record save
- `EditorView.vue` - Add version count badge on the history button
- `VersionHistory.vue` - Show a text preview per version for quick comparison

**Specific changes**:
1. In `storage.py save()`: After inserting a new record (not update), also insert a v1 version snapshot
2. In `EditorView.vue`: Fetch version count on record load, show as a badge number on the clock icon button
3. In `VersionHistory.vue`: Display first ~80 chars of transcript text per version entry for visual comparison

---

### Phase 6: Export UI Improvements [Low Priority]

**Files modified**:
- `ExportMenu.vue` - Redesign the AI toggle placement and label

**Specific changes**:
- Move the AI checkbox from outside the dropdown to inside it, as the first item before the format list
- Use DaisyUI toggle component with label: "Include AI Results"
- Add a divider between the toggle and the format list

---

## Dependencies

```
Phase 1 (Bug Fix) - No dependencies, do FIRST
Phase 2 (API Presets) - Independent
Phase 3 (Punctuation) - Works standalone; can optionally integrate with Phase 4 presets
Phase 4 (AI Presets) - Independent
Phase 5 (Version History) - Independent
Phase 6 (Export UI) - Independent
```

Phases 2-6 are all independent of each other and can be done in any order after Phase 1.

---

## Risks

- **HIGH**: Phase 3 (punctuation) adds latency to every transcription when enabled. Mitigation: make it opt-in with a settings toggle; use non-streaming call for speed; fail silently if AI unavailable.
- **MEDIUM**: Phase 2 (API presets) requires new SQLite table. Mitigation: purely additive change; existing single-config still works as default.
- **LOW**: Phase 5 (version history) creating v1 on first save adds one extra DB write. Negligible impact.
- **LOW**: Phase 4 (AI presets) changes prompt lookup flow. Mitigation: built-in presets seeded automatically; fallback to hardcoded `_PROMPTS` dict if no presets exist.

---

## Complexity Summary

| Phase | Scope | Files | Complexity |
|-------|-------|-------|------------|
| 1 - Transcription fix | Bug fix | 1 | Low |
| 2 - API presets | New feature | ~6 | High |
| 3 - Punctuation | Enhancement | 4 | Medium |
| 4 - AI presets | New feature | ~7 | High |
| 5 - Version history | Enhancement | 3 | Low |
| 6 - Export UI | UX fix | 1 | Low |
