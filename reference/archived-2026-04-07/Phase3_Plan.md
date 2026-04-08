# SherpaNote Phase 3-4 Implementation Plan

## Current State Summary

Phase 0-2 are complete. The project has:

- Full Python backend (ASR, AI, Storage, Config, IO) with 17 Bridge endpoints
- Vue 3 frontend with 4 views, 8 components, 4 composables, Pinia store
- DaisyUI 5 + Tailwind CSS 4 theming (light/dark)
- Streaming AI processing (4 modes: polish, note, mindmap, brainstorm)
- Basic export (md, txt, docx, srt)
- Version history UI
- Audio sync playback in editor

## Phase 3: AI Knowledge Processing Enhancements

### 3.1 Markdown Rendering for AI Results

**Problem**: AiProcessor.vue renders AI output as raw text (`{{ currentResult }}`). Markdown formatting (headers, lists, bold, code blocks) is lost.

**Solution**: Add a lightweight Markdown renderer component.

**Files to modify**:

- `frontend/src/components/AiProcessor.vue` - Use new MarkdownRenderer
- `frontend/src/components/MarkdownRenderer.vue` - New component (simple, no dependency)

**Approach**: Create a minimal Markdown-to-HTML renderer that handles:

- Headers (h1-h4)
- Bold, italic, strikethrough
- Ordered and unordered lists
- Code blocks with language hint
- Horizontal rules
- Links

No external dependency needed - a ~100 line renderer covers the common subset that LLM outputs use.

### 3.2 Mind Map Preview

**Problem**: When AI generates a mindmap in Markmap format, it displays as plain text. A visual preview would be much more useful.

**Solution**: Add a toggle in AiProcessor to switch between text view and mind map preview.

**Files to modify**:

- `frontend/src/components/AiProcessor.vue` - Add preview toggle for mindmap mode
- `frontend/src/components/MindMapPreview.vue` - New component

**Approach**: Parse Markmap Markdown into a tree structure and render as an interactive SVG/canvas mind map. Use a simple tree layout algorithm. No external dependency.

### 3.3 Stop/Cancel AI Processing

**Problem**: Once AI processing starts, the user cannot cancel it. Long-running requests (large text + slow API) block the UI.

**Solution**: Add a cancel button during AI processing.

**Files to modify**:

- `py/llm.py` - Add cancel support (thread cancellation flag)
- `main.py` - Add `cancel_ai()` exposed method
- `frontend/src/composables/useAiProcess.ts` - Add cancel function
- `frontend/src/components/AiProcessor.vue` - Add cancel button

### 3.4 AI Config Validation and Connection Test

**Problem**: User has no way to verify their AI config works until they actually try processing.

**Solution**: Add a "Test Connection" button in Settings.

**Files to modify**:

- `main.py` - Add `test_ai_connection()` exposed method
- `frontend/src/views/SettingsView.vue` - Add test button + result indicator

---

## Phase 4: Export Enhancements & Packaging

### 4.1 Export with AI Results Toggle

**Problem**: Currently all exports include AI results if they exist. User may want to export transcript only.

**Solution**: Add options to export menu.

**Files to modify**:

- `frontend/src/components/ExportMenu.vue` - Add "Include AI Results" toggle
- `py/storage.py` - Add `include_ai` parameter to `export()`
- `main.py` - Pass `include_ai` through `export_record()`

### 4.2 Open Exported File

**Problem**: After export, user has no indication where the file was saved and must navigate to find it.

**Solution**: Open the file/folder after export, and show the path.

**Files to modify**:

- `main.py` - Add `open_file()` and `open_folder()` exposed methods using `os.startfile`/`subprocess`
- `frontend/src/components/ExportMenu.vue` - Show export path and open button after export
- `frontend/src/composables/useStorage.ts` - Return file path from export

### 4.3 PyInstaller Spec Update

**Problem**: app.spec still uses generic "app" name. Missing hidden imports for sherpa-onnx, openai, docx.

**Solution**: Update app.spec with proper app name and all required hidden imports.

**Files to modify**:

- `app.spec` - Update APP_NAME, hidden imports, add py/ package data
- `build.py` - Update app name references

### 4.4 Record Category & Tags Management

**Problem**: Records have category and tags fields in the DB and types, but the UI has no way to set them.

**Solution**: Add category/tag editing in EditorView.

**Files to modify**:

- `frontend/src/views/EditorView.vue` - Add category selector and tag input
- `frontend/src/views/HomeView.vue` - Update category filter sidebar to be functional

### 4.5 Record Import (md/txt)

**Problem**: Users can only import audio files. There's no way to import existing text notes.

**Solution**: Add import_record Bridge endpoint and import UI.

**Files to modify**:

- `main.py` - Add `import_record()` method (already in PLAN.md spec)
- `frontend/src/views/HomeView.vue` - Add import button for text files
- `frontend/src/composables/useStorage.ts` - Add importRecord function

---

## Implementation Order

1. **Phase 3.1** - MarkdownRenderer component (independent, high impact)
2. **Phase 4.4** - Category & tags UI (independent, fills gap in existing feature)
3. **Phase 4.2** - Open exported file (small, useful UX improvement)
4. **Phase 4.1** - Export AI toggle (small, builds on 4.2)
5. **Phase 3.4** - AI connection test (small, useful UX)
6. **Phase 3.3** - Cancel AI processing (medium, needs backend threading)
7. **Phase 3.2** - Mind map preview (medium, new component)
8. **Phase 4.5** - Import text records (small, new feature)
9. **Phase 4.3** - PyInstaller spec update (final, packaging)

# All tasks completed.

Here's a summary of everything implemented for Phase 3-4:

  Phase 3: AI Knowledge Processing Enhancements

  1. MarkdownRenderer Component (new)

  - frontend/src/components/MarkdownRenderer.vue - Lightweight Markdown-to-HTML renderer handling headings, bold,
    italic, strikethrough, lists, code blocks, blockquotes, horizontal rules, and links. No external dependency.
  - Integrated into AiProcessor.vue replacing the raw {{ currentResult }} text output.

  2. Mind Map Preview (new)

  - frontend/src/components/MindMapPreview.vue - Interactive SVG mind map renderer that parses Markmap Markdown headings
      into a tree and renders with pan/zoom support.
  - AiProcessor.vue updated with a "Map" toggle button for mindmap mode output.

  3. Cancel AI Processing

  - py/llm.py - Added threading.Event based cancellation flag with cancel() and _reset_cancel() methods. Streaming loop
    checks the flag between chunks.
  - main.py - Added cancel_ai() Bridge method and updated process_text_stream() to detect cancellation.
  - useAiProcess.ts - Added cancelProcessing() function.
  - AiProcessor.vue - Added "Cancel" button shown during processing.

  4. AI Connection Test

  - main.py - Added test_ai_connection() Bridge method that sends a minimal "Hello" request.
  - SettingsView.vue - Added "Test Connection" button with success/failure indicator.

  Phase 4: Export Enhancements & Packaging

  5. Category & Tags Management

  - EditorView.vue - Added category selector dropdown and tag input with add/remove in a metadata bar.
  - RecordCard.vue - Added tag badges display (up to 3 shown, "+N" for overflow).

  6. Open Exported File

  - main.py - Added open_file() and open_folder() Bridge methods (cross-platform).
  - ExportMenu.vue - Shows file path after export, "Open File" and "Open Folder" dropdown options.

  7. Export AI Toggle

  - ExportMenu.vue - Added "AI" checkbox to include/exclude AI results in exports.
  - storage.py - Added include_ai parameter to export(), _export_md(), and _export_docx().
  - main.py - Updated export_record() to pass include_ai through.

  8. Text Record Import

  - main.py - Added import_record() Bridge method for .md/.txt files.
  - useStorage.ts - Added importRecord() function.
  - HomeView.vue - Added "Import Text" button with hidden file input.

  9. PyInstaller Spec Update

  - app.spec - Changed APP_NAME to "SherpaNote", added hidden imports for openai, docx, sherpa_onnx, py package, added
    py/ to datas.
  - build.py - Updated all app name references from "app" to "SherpaNote".