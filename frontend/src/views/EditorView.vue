<script setup lang="ts">
/**
 * EditorView - Transcript editing and AI results page.
 *
 * Layout: full-width, vertically stacked:
 * 1. Header bar (title, actions)
 * 2. Audio player (collapsible)
 * 3. Left column: AI control panel | Right column: content area
 *    - Content area has tabs: Transcript / AI Results
 *    - Transcript is collapsible
 *    - AI Results is full-size, scrollable, with save/copy
 */
import { ref, onMounted, onBeforeUnmount, watch, computed, nextTick } from "vue";
import { useRouter, useRoute } from "vue-router";
import { call, onEvent } from "../bridge";
import { useStorage } from "../composables/useStorage";
import { useAppStore } from "../stores/appStore";
import AiProcessor from "../components/AiProcessor.vue";
import MarkdownRenderer from "../components/MarkdownRenderer.vue";
import MindMapPreview from "../components/MindMapPreview.vue";
import ExportMenu from "../components/ExportMenu.vue";
import VersionHistory from "../components/VersionHistory.vue";
import type { TranscriptRecord, Segment, AiResults, Version } from "../types";

const store = useAppStore();
const router = useRouter();
const route = useRoute();
const recordId = computed(() => route.params.id as string);

const { getRecord, saveRecord, saveVersion } = useStorage();

// Record data
const record = ref<TranscriptRecord | null>(null);
const isLoading = ref(true);
const editorText = ref("");
const saveStatus = ref<"idle" | "editing" | "saving" | "saved">("idle");

// Audio player
const audioRef = ref<HTMLAudioElement | null>(null);
const isPlaying = ref(false);
const audioCurrentTime = ref(0);
const audioDuration = ref(0);
const audioDataUrl = ref("");
const audioVolume = ref(0.8);
const isMuted = ref(false);
const showSegments = ref(true);
const showAudio = ref(true);
const showVersionHistory = ref(false);

// Re-transcribe
const isRetranscribing = ref(false);

// Version count badge
const versionCount = ref(0);

const showTranscript = ref(true);

// AI result state
const activeResultMode = ref<string | null>(null);
const currentResultContent = ref("");
const isAiProcessing = ref(false);
const showMindMap = ref(false);
const truncationWarning = ref(false);
let accumulatedText = "";

async function handleRetranscribe() {
  if (!record.value || isRetranscribing.value) return;
  isRetranscribing.value = true;
  store.showToast("Starting recognition...", "info");
  const res = await call("retranscribe_record", record.value.id);
  if (!res.success) {
    store.showToast(res.error ?? "Recognition failed", "error");
    isRetranscribing.value = false;
  }
}

async function copyTranscript() {
  const text = editorText.value;
  if (!text) {
    store.showToast("Nothing to copy", "warning");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    store.showToast("Copied to clipboard", "success");
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
    store.showToast("Copied to clipboard", "success");
  }
}

// Category & tags
const availableCategories = ["", "Course", "Meeting", "Interview", "Lecture", "Personal"];
const newTag = ref("");

function onCategoryChange() {
  if (!record.value) return;
  saveRecord({ ...record.value, category: record.value.category });
}

function addTag() {
  if (!record.value || !newTag.value.trim()) return;
  const tag = newTag.value.trim();
  if (record.value.tags.includes(tag)) {
    newTag.value = "";
    return;
  }
  const updated = { ...record.value, tags: [...record.value.tags, tag] };
  saveRecord(updated).then((saved) => {
    if (saved) record.value = saved;
  });
  newTag.value = "";
}

function removeTag(tag: string) {
  if (!record.value) return;
  const updated = { ...record.value, tags: record.value.tags.filter((t) => t !== tag) };
  saveRecord(updated).then((saved) => {
    if (saved) record.value = saved;
  });
}

// Auto-save with debounce
let saveTimer: ReturnType<typeof setTimeout>;
let isInitialLoad = true; // Guard: suppress dirty flag during initial data load
// Content of the transcript at the time of the last version snapshot.
// Used to detect REAL changes vs no-op edits (type then delete).
let lastVersionContent = "";

async function loadRecord() {
  isLoading.value = true;
  isInitialLoad = true; // Suppress watcher during initial load
  const data = await getRecord(recordId.value);
  if (data) {
    record.value = data;
    editorText.value = data.transcript || "";
    lastVersionContent = data.transcript || "";
    if (data.audio_path) {
      await loadAudioDataUrl(data.audio_path);
    }
  }
  const verRes = await call<{ length: number }>("get_version_history", recordId.value);
  if (verRes.success && verRes.data) {
    versionCount.value = Array.isArray(verRes.data) ? verRes.data.length : 0;
  }
  isLoading.value = false;
  // Allow watcher to track changes after load completes
  nextTick(() => { isInitialLoad = false; });
}

async function loadAudioDataUrl(audioPath: string) {
  try {
    const res = await call<{ base64: string; mime: string }>("get_audio_base64", audioPath);
    if (res.success && res.data) {
      audioDataUrl.value = `data:${res.data.mime};base64,${res.data.base64}`;
    } else {
      audioDataUrl.value = "";
    }
  } catch {
    audioDataUrl.value = "";
  }
}

watch(editorText, () => {
  if (!record.value) return;
  if (isInitialLoad) return; // Don't mark dirty during initial data load
  saveStatus.value = "editing";
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    saveStatus.value = "saving";
    const updated = await saveRecord({
      ...record.value!,
      transcript: editorText.value,
    });
    if (updated) {
      record.value = updated;
      // Compare against last version snapshot, not just "was edited"
      const hasRealChange = editorText.value !== lastVersionContent;
      if (hasRealChange) {
        call("mark_dirty", record.value.id);
      } else {
        call("mark_clean", record.value.id);
      }
      saveStatus.value = "saved";
      setTimeout(() => {
        saveStatus.value = "idle";
      }, 2000);
    } else {
      saveStatus.value = "idle";
    }
  }, 2000);
});

async function saveTitle() {
  if (!record.value) return;
  const updated = await saveRecord({ ...record.value, title: record.value.title });
  if (updated) {
    record.value = updated;
  }
}

// Audio playback sync.
function onTimeUpdate() {
  if (!audioRef.value) return;
  audioCurrentTime.value = audioRef.value.currentTime;
  const current = audioRef.value.currentTime;
  const segments = record.value?.segments ?? [];
  const active = segments.find(
    (s) => s.start_time <= current && s.end_time > current,
  );
  store.activeSegmentIndex = active?.index ?? -1;
}

function onLoadedMetadata() {
  if (audioRef.value) {
    audioDuration.value = audioRef.value.duration;
  }
}

function togglePlayback() {
  if (!audioRef.value) return;
  if (isPlaying.value) {
    audioRef.value.pause();
  } else {
    audioRef.value.play();
  }
  isPlaying.value = !isPlaying.value;
}

function toggleMute() {
  if (!audioRef.value) return;
  isMuted.value = !isMuted.value;
  audioRef.value.muted = isMuted.value;
}

function onVolumeChange(value: number) {
  audioVolume.value = value;
  if (!audioRef.value) return;
  audioRef.value.volume = value;
  if (value > 0 && isMuted.value) {
    isMuted.value = false;
    audioRef.value.muted = false;
  }
}

function seekToSegment(segment: Segment) {
  if (!audioRef.value) return;
  audioRef.value.currentTime = segment.start_time;
  audioRef.value.play();
  isPlaying.value = true;
}

function formatAudioTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

// ---- AI Processing ----

let offToken: (() => void) | null = null;
let offAiComplete: (() => void) | null = null;
let offAiError: (() => void) | null = null;
let offAiContinueComplete: (() => void) | null = null;

function setupAiListeners() {
  offToken?.();
  offAiComplete?.();
  offAiError?.();
  offAiContinueComplete?.();

  offToken = onEvent<{ text: string }>("ai_token", ({ text }) => {
    accumulatedText += text;
    currentResultContent.value = accumulatedText;
  });

  offAiComplete = onEvent<{ result: string; truncated?: boolean; record?: TranscriptRecord }>("ai_complete", (detail) => {
    isAiProcessing.value = false;
    accumulatedText = "";
    currentResultContent.value = detail.result;
    if (detail.truncated) {
      truncationWarning.value = true;
      store.showToast("Output truncated. Increase max_tokens or click Continue.", "warning");
    }
    if (detail.record) {
      record.value = detail.record;
    } else {
      autoSaveResult();
    }
  });

  offAiContinueComplete = onEvent<{ result: string; truncated?: boolean; record?: TranscriptRecord }>("ai_continue_complete", (detail) => {
    isAiProcessing.value = false;
    accumulatedText = "";
    if (detail.truncated) {
      truncationWarning.value = true;
      store.showToast("Output still truncated. Click Continue again.", "warning");
    } else {
      truncationWarning.value = false;
      store.showToast("Output completed", "success");
    }
    if (detail.record) {
      record.value = detail.record;
    } else {
      autoSaveResult();
    }
  });

  offAiError = onEvent<{ error: string }>("ai_error", (detail) => {
    isAiProcessing.value = false;
    accumulatedText = "";
    store.showToast(detail.error, "error");
  });
}

function handleProcessRequest(mode: string, _presetId: string | null, customPrompt: string | null) {
  if (!record.value) return;
  isAiProcessing.value = true;
  truncationWarning.value = false;
  currentResultContent.value = "";
  accumulatedText = "";
  activeResultMode.value = mode;
  showMindMap.value = false;
  setupAiListeners();
  call("process_text_stream", editorText.value, mode, customPrompt ?? null, record.value.id);
}

function handleCancelAi() {
  call("cancel_ai");
  isAiProcessing.value = false;
  accumulatedText = "";
}

function handleContinueOutput() {
  if (!currentResultContent.value) return;
  isAiProcessing.value = true;
  accumulatedText = currentResultContent.value;
  truncationWarning.value = false;
  setupAiListeners();
  call("continue_text_stream", currentResultContent.value, activeResultMode.value ?? "polish", null, record.value?.id ?? null);
}

function handleSelectResult(mode: string) {
  activeResultMode.value = mode;
  const content = record.value?.ai_results?.[mode];
  if (content) {
    currentResultContent.value = content;
    showMindMap.value = mode === "mindmap";
  }
}

async function handleSaveResult() {
  if (!record.value || !currentResultContent.value || !activeResultMode.value) return;
  const saved = await persistResult(record.value, activeResultMode.value, currentResultContent.value);
  if (saved) {
    store.showToast("AI result saved", "success");
  } else {
    store.showToast("Failed to save AI result", "error");
  }
}

async function autoSaveResult() {
  if (!record.value || !currentResultContent.value || !activeResultMode.value) return;
  await persistResult(record.value, activeResultMode.value, currentResultContent.value);
}

async function persistResult(rec: TranscriptRecord, mode: string, content: string): Promise<boolean> {
  const updatedAi: AiResults = { ...rec.ai_results, [mode]: content };
  const res = await call<TranscriptRecord>("save_record", { ...rec, ai_results: updatedAi });
  if (res.success && res.data) {
    record.value = res.data;
    return true;
  }
  return false;
}

function handleCopyResult() {
  if (currentResultContent.value) {
    navigator.clipboard.writeText(currentResultContent.value);
    store.showToast("Copied to clipboard", "info");
  }
}

async function handleDeleteResult(mode: string) {
  if (!record.value) return;
  const updatedAi = { ...record.value.ai_results };
  delete updatedAi[mode as keyof AiResults];
  const res = await call<TranscriptRecord>("save_record", {
    ...record.value,
    ai_results: updatedAi,
  });
  if (res.success && res.data) {
    record.value = res.data;
    if (activeResultMode.value === mode) {
      activeResultMode.value = null;
      currentResultContent.value = "";
    }
    store.showToast("Result deleted", "info");
  }
}

function onVersionRestored(updated: TranscriptRecord) {
  record.value = updated;
  editorText.value = updated.transcript;
  // Restore creates a new version, so update lastVersionContent
  lastVersionContent = updated.transcript;
  call("mark_clean", record.value.id);
  showVersionHistory.value = false;
  refreshVersionCount();
}

async function refreshVersionCount() {
  const verRes = await call<Version[]>("get_version_history", recordId.value);
  if (verRes.success && Array.isArray(verRes.data)) {
    versionCount.value = verRes.data.length;
  }
}

const isSavingVersion = ref(false);

async function handleSaveVersion() {
  if (!record.value || isSavingVersion.value) return;
  isSavingVersion.value = true;
  const ver = await saveVersion(record.value.id);
  if (ver !== null) {
    lastVersionContent = editorText.value;
    store.showToast(`Version v${ver} saved`, "success");
    // Update record.version so VersionHistory highlights the new current
    if (record.value) {
      record.value = { ...record.value, version: ver };
    }
    await refreshVersionCount();
  }
  isSavingVersion.value = false;
}

function hasAudio(): boolean {
  return !!audioDataUrl.value;
}

let offRetranscribe: (() => void) | null = null;

onMounted(() => {
  loadRecord();
  offRetranscribe = onEvent<{
    record_id: string;
    record: TranscriptRecord;
  }>("retranscribe_complete", ({ record_id, record: updatedRecord }) => {
    if (record.value && record.value.id === record_id) {
      record.value = updatedRecord;
      editorText.value = updatedRecord.transcript;
      isRetranscribing.value = false;
      store.showToast("Recognition complete", "success");
    }
  });
});

onBeforeUnmount(async () => {
  if (offRetranscribe) {
    offRetranscribe();
    offRetranscribe = null;
  }
  offToken?.();
  offAiComplete?.();
  offAiContinueComplete?.();
  offAiError?.();

  // Save partial AI result if processing is still in progress (backend will
  // save the full result on its own; this is a fallback for very long-running jobs).
  if (isAiProcessing.value && record.value && activeResultMode.value && currentResultContent.value) {
    try {
      await persistResult(record.value, activeResultMode.value, currentResultContent.value);
    } catch {
      // Best-effort: backend will persist the complete result independently
    }
  }

  // Only save version if content actually differs from last version snapshot
  if (editorText.value !== lastVersionContent && record.value) {
    try {
      await saveVersion(record.value.id);
    } catch {
      // Best-effort: don't block navigation
    }
  }
});
</script>

<template>
  <div class="mx-auto max-w-6xl px-4 py-4">
    <!-- Header -->
    <div class="mb-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <button class="btn btn-ghost btn-sm" @click="router.push('/')">
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <input
          v-if="record"
          v-model="record.title"
          class="input input-ghost input-lg font-bold tracking-tight text-base-content max-w-md"
          @change="saveTitle"
        />
      </div>
      <div class="flex items-center gap-2">
        <button
          v-if="record?.can_retranscribe"
          class="btn btn-ghost btn-sm"
          :class="{ 'btn-disabled loading': isRetranscribing }"
          :disabled="isRetranscribing"
          title="Re-transcribe audio"
          @click="handleRetranscribe"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
            <path d="M19 10v2a7 7 0 01-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
          {{ isRetranscribing ? "转写中..." : "重新转写" }}
        </button>
        <span
          v-if="saveStatus !== 'idle'"
          class="badge badge-sm"
          :class="{
            'badge-warning': saveStatus === 'editing',
            'badge-info': saveStatus === 'saving',
            'badge-success': saveStatus === 'saved',
          }"
        >
          {{ saveStatus === "saved" ? "已保存" : saveStatus === "saving" ? "保存中..." : "未保存" }}
        </span>
        <button
          class="btn btn-ghost btn-sm btn-circle relative"
          title="版本历史"
          @click="showVersionHistory = !showVersionHistory"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <span
            v-if="versionCount > 0"
            class="absolute -top-1 -right-1 badge badge-xs badge-primary"
          >
            {{ versionCount }}
          </span>
        </button>
        <ExportMenu v-if="record" :record-id="record.id" />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-16">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>

    <!-- Main layout -->
    <div v-else-if="record" class="space-y-4">
      <!-- Category & Tags bar -->
      <div class="flex flex-wrap items-center gap-2">
        <select
          v-model="record.category"
          class="select select-bordered select-xs"
          @change="onCategoryChange"
        >
          <option value="">无分类</option>
          <option v-for="cat in availableCategories.filter(c => c)" :key="cat" :value="cat">
            {{ cat }}
          </option>
        </select>
        <div class="flex items-center gap-1 flex-wrap">
          <span
            v-for="tag in record.tags"
            :key="tag"
            class="badge badge-sm badge-outline gap-1"
          >
            {{ tag }}
            <button class="hover:text-error" @click="removeTag(tag)">
              <svg class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </span>
          <input
            v-model="newTag"
            class="input input-bordered input-xs w-24"
            placeholder="添加标签..."
            @keydown.enter.prevent="addTag"
          />
        </div>
      </div>

      <!-- Audio player bar (collapsible) -->
      <div
        v-if="hasAudio()"
        class="rounded-lg border border-base-300 bg-base-200 overflow-hidden"
      >
        <button
          class="flex items-center justify-between w-full px-3 py-2 text-sm font-medium text-base-content/70 hover:bg-base-300 transition-colors"
          @click="showAudio = !showAudio"
        >
          <span>音频播放器</span>
          <svg
            class="h-4 w-4 transition-transform"
            :class="{ 'rotate-180': showAudio }"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
        <div v-if="showAudio" class="px-3 pb-3 flex items-center gap-3">
          <button class="btn btn-ghost btn-sm btn-circle" @click="togglePlayback">
            <svg v-if="!isPlaying" class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            <svg v-else class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" />
              <rect x="14" y="4" width="4" height="16" />
            </svg>
          </button>
          <span class="text-xs font-mono text-base-content/60 min-w-[40px]">
            {{ formatAudioTime(audioCurrentTime) }}
          </span>
          <input
            type="range"
            class="range range-primary range-xs flex-1"
            min="0"
            :max="audioDuration || 0"
            step="0.1"
            :value="audioCurrentTime"
            @input="audioRef && (audioRef.currentTime = Number(($event.target as HTMLInputElement).value))"
          />
          <span class="text-xs font-mono text-base-content/60 min-w-[40px]">
            {{ formatAudioTime(audioDuration) }}
          </span>
          <div class="flex items-center gap-1 ml-1">
            <button class="btn btn-ghost btn-xs btn-circle" @click="toggleMute">
              <svg v-if="isMuted || audioVolume === 0" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                <line x1="23" y1="9" x2="17" y2="15" />
                <line x1="17" y1="9" x2="23" y2="15" />
              </svg>
              <svg v-else-if="audioVolume < 0.5" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                <path d="M15.54 8.46a5 5 0 010 7.07" />
              </svg>
              <svg v-else class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                <path d="M15.54 8.46a5 5 0 010 7.07" />
                <path d="M19.07 4.93a10 10 0 010 14.14" />
              </svg>
            </button>
            <input
              type="range"
              class="range range-primary range-xs w-16"
              min="0"
              max="1"
              step="0.05"
              :value="isMuted ? 0 : audioVolume"
              @input="onVolumeChange(Number(($event.target as HTMLInputElement).value))"
            />
          </div>
          <audio
            ref="audioRef"
            :src="audioDataUrl"
            preload="metadata"
            @timeupdate="onTimeUpdate"
            @loadedmetadata="onLoadedMetadata"
            @ended="isPlaying = false"
          ></audio>
        </div>
      </div>

      <!-- Main two-column layout -->
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <!-- Left: AI control panel -->
        <div class="lg:col-span-1 space-y-4">
          <VersionHistory
            v-if="showVersionHistory && record"
            :key="'vh-' + versionCount"
            :record-id="record.id"
            :current-version="record.version ?? 0"
            @restored="onVersionRestored"
            @deleted="refreshVersionCount"
          />
          <AiProcessor
            :record="record"
            :editor-text="editorText"
            :active-result-mode="activeResultMode"
            @process="handleProcessRequest"
            @select-result="handleSelectResult"
            @delete-result="handleDeleteResult"
            @cancel="handleCancelAi"
          />
        </div>

        <!-- Right: Content area (2/3 width) - vertically stacked -->
        <div class="lg:col-span-2 space-y-4 min-w-0">
          <!-- Transcript panel (always visible, collapsible) -->
          <div class="rounded-lg border border-base-300 bg-base-100">
            <!-- Collapsible header -->
            <div
              class="flex items-center justify-between w-full px-4 py-3 text-sm font-medium text-base-content/70 hover:bg-base-200 transition-colors cursor-pointer"
              @click="showTranscript = !showTranscript"
            >
              <div class="flex items-center gap-2">
                <svg
                  class="h-4 w-4 transition-transform"
                  :class="{ 'rotate-180': !showTranscript }"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
                <span>转写文本</span>
                <span v-if="editorText.length > 0" class="text-xs opacity-40 ml-1">
                  {{ editorText.length }} 字
                </span>
              </div>
              <button
                class="btn btn-primary btn-sm"
                :disabled="isSavingVersion"
                title="保存当前状态为版本快照"
                @click.stop="handleSaveVersion"
              >
                <span v-if="isSavingVersion" class="loading loading-spinner loading-xs"></span>
                <svg v-else class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z" />
                  <polyline points="17 21 17 13 7 13 7 21" />
                  <polyline points="7 3 7 8 15 8" />
                </svg>
                保存版本
              </button>
              <button
                class="btn btn-ghost btn-xs"
                title="复制转写文本"
                @click.stop="copyTranscript"
              >
                <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                </svg>
              </button>
            </div>

            <!-- Collapsed preview -->
            <div v-if="!showTranscript" class="px-4 pb-3">
              <p class="text-sm text-base-content/50 line-clamp-3">{{ editorText || "(empty)" }}</p>
            </div>

            <!-- Expanded content -->
            <div v-else>
              <!-- Segments view -->
              <div
                v-if="record.segments && record.segments.length > 0 && hasAudio()"
                class="mx-4 mb-2 rounded-lg border border-base-200 bg-base-100 overflow-hidden"
              >
                <button
                  class="flex items-center justify-between w-full px-3 py-2 text-xs font-medium text-base-content/60 hover:bg-base-200 transition-colors"
                  @click="showSegments = !showSegments"
                >
                  <span>时间戳分段</span>
                  <svg
                    class="h-3.5 w-3.5 transition-transform"
                    :class="{ 'rotate-180': showSegments }"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>
                <div v-if="showSegments" class="max-h-[30vh] overflow-y-auto px-2 pb-2 space-y-1">
                  <p
                    v-for="seg in record.segments"
                    :key="seg.index"
                    class="cursor-pointer rounded px-2 py-1 text-sm leading-relaxed transition-colors"
                    :class="store.activeSegmentIndex === seg.index ? 'bg-primary/15 text-primary' : 'hover:bg-base-200 text-base-content'"
                    @click="seekToSegment(seg)"
                  >
                    <span class="text-xs text-base-content/40 mr-2">
                      {{ formatAudioTime(seg.start_time) }}
                    </span>
                    <span v-if="seg.speaker" class="text-xs text-secondary mr-2">
                      {{ seg.speaker }}
                    </span>
                    {{ seg.text }}
                  </p>
                </div>
              </div>

              <!-- Textarea -->
              <textarea
                v-model="editorText"
                class="textarea textarea-ghost w-full min-h-[30vh] text-base leading-relaxed resize-none px-4 pb-4"
                placeholder="转写文本将在此处显示..."
              ></textarea>
            </div>
          </div>

          <!-- AI Result panel (always visible below transcript) -->
          <div
            v-if="activeResultMode || isAiProcessing"
            class="rounded-lg border border-base-300 bg-base-100 overflow-hidden"
          >
            <!-- Result header -->
            <div class="flex items-center justify-between px-4 py-3 border-b border-base-200">
              <div class="flex items-center gap-2">
                <h2 class="text-sm font-semibold text-base-content/70">
                  <span>{{ activeResultMode || 'AI 结果' }}</span>
                </h2>
                <span v-if="isAiProcessing" class="loading loading-dots loading-xs text-primary"></span>
                <span
                  v-if="truncationWarning"
                  class="badge badge-warning badge-xs"
                >已截断</span>
              </div>
              <div v-if="currentResultContent && !isAiProcessing" class="flex gap-1">
                <button
                  v-if="activeResultMode === 'mindmap'"
                  class="btn btn-ghost btn-xs"
                  :class="showMindMap ? 'btn-active' : ''"
                  @click="showMindMap = !showMindMap"
                  title="切换思维导图"
                >导图</button>
                <button
                  v-if="truncationWarning"
                  class="btn btn-warning btn-outline btn-xs"
                  title="继续生成"
                  @click="handleContinueOutput"
                >继续</button>
                <button
                  class="btn btn-ghost btn-xs"
                  title="保存到记录"
                  @click="handleSaveResult"
                >保存</button>
                <button
                  class="btn btn-ghost btn-xs"
                  title="复制到剪贴板"
                  @click="handleCopyResult"
                >复制</button>
              </div>
            </div>

            <!-- Result content area (scrollable) -->
            <div class="min-h-[40vh] max-h-[60vh] overflow-y-auto px-4 py-4">
              <MindMapPreview
                v-if="showMindMap && currentResultContent"
                :content="currentResultContent"
              />
              <MarkdownRenderer
                v-else-if="currentResultContent && !showMindMap"
                :content="currentResultContent"
              />
              <div v-else-if="isAiProcessing" class="flex justify-center py-16">
                <span class="loading loading-dots loading-lg text-primary"></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
