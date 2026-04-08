<script setup lang="ts">
/**
 * EditorView - Transcript editing and AI processing page.
 *
 * Displays a record's transcript for editing, plays back
 * synchronized audio, and provides AI processing capabilities.
 *
 * Uses AiProcessor, ExportMenu, VersionHistory components.
 */
import { ref, onMounted, onBeforeUnmount, watch, computed } from "vue";
import { useRouter, useRoute } from "vue-router";
import { call, onEvent } from "../bridge";
import { useStorage } from "../composables/useStorage";
import { useAppStore } from "../stores/appStore";
import AiProcessor from "../components/AiProcessor.vue";
import ExportMenu from "../components/ExportMenu.vue";
import VersionHistory from "../components/VersionHistory.vue";
import type { TranscriptRecord, Segment } from "../types";

const store = useAppStore();
const router = useRouter();
const route = useRoute();
const recordId = computed(() => route.params.id as string);

const { getRecord, saveRecord } = useStorage();

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
const showVersionHistory = ref(false);

// Re-transcribe
const isRetranscribing = ref(false);

async function handleRetranscribe() {
  if (!record.value || isRetranscribing.value) return;
  isRetranscribing.value = true;
  store.showToast("Starting recognition...", "info");
  const res = await call("retranscribe_record", record.value.id);
  if (!res.success) {
    store.showToast(res.error ?? "Recognition failed", "error");
    isRetranscribing.value = false;
  }
  // Completion handled by event listener below
}

// Copy transcript to clipboard
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
    // Fallback for older browsers / restricted contexts
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

async function loadRecord() {
  isLoading.value = true;
  const data = await getRecord(recordId.value);
  if (data) {
    record.value = data;
    editorText.value = data.transcript || "";
    // Load audio as base64 data URL for playback in pywebview.
    if (data.audio_path) {
      await loadAudioDataUrl(data.audio_path);
    }
  }
  isLoading.value = false;
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
      saveStatus.value = "saved";
      setTimeout(() => {
        saveStatus.value = "idle";
      }, 2000);
    } else {
      saveStatus.value = "idle";
    }
  }, 2000);
});

/** Save title changes. */
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

/** Handle AI result saved - update local record. */
function onResultSaved(updated: TranscriptRecord) {
  record.value = updated;
}

/** Handle version restored - update local record and editor text. */
function onVersionRestored(updated: TranscriptRecord) {
  record.value = updated;
  editorText.value = updated.transcript;
  showVersionHistory.value = false;
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

onBeforeUnmount(() => {
  if (offRetranscribe) {
    offRetranscribe();
    offRetranscribe = null;
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
        <!-- Editable title -->
        <input
          v-if="record"
          v-model="record.title"
          class="input input-ghost input-lg font-bold tracking-tight text-base-content max-w-md"
          @change="saveTitle"
        />
      </div>
      <div class="flex items-center gap-2">
        <!-- Re-transcribe (only for app-recorded audio) -->
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
          {{ isRetranscribing ? "Transcribing..." : "Re-transcribe" }}
        </button>

        <!-- Save status -->
        <span
          v-if="saveStatus !== 'idle'"
          class="badge badge-sm"
          :class="{
            'badge-warning': saveStatus === 'editing',
            'badge-info': saveStatus === 'saving',
            'badge-success': saveStatus === 'saved',
          }"
        >
          {{ saveStatus === "saved" ? "Saved" : saveStatus === "saving" ? "Saving..." : "Unsaved" }}
        </span>

        <!-- Version history toggle -->
        <button
          class="btn btn-ghost btn-sm btn-circle"
          title="Version History"
          @click="showVersionHistory = !showVersionHistory"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
        </button>

        <!-- Export -->
        <ExportMenu v-if="record" :record-id="record.id" />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-16">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>

    <!-- Editor layout -->
    <div v-else-if="record" class="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <!-- Category & Tags bar -->
      <div class="lg:col-span-3 flex flex-wrap items-center gap-2">
        <select
          v-model="record.category"
          class="select select-bordered select-xs"
          @change="onCategoryChange"
        >
          <option value="">No category</option>
          <option v-for="cat in availableCategories.filter(c => c)" :key="cat" :value="cat">
            {{ cat }}
          </option>
        </select>

        <!-- Tags -->
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
            placeholder="Add tag..."
            @keydown.enter.prevent="addTag"
          />
        </div>
      </div>

      <!-- Main editor area -->
      <div class="lg:col-span-2 space-y-4">
        <!-- Audio player bar -->
        <div
          v-if="hasAudio()"
          class="rounded-lg border border-base-300 bg-base-200 p-3 flex items-center gap-3"
        >
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
          <!-- Volume control -->
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

        <!-- Transcript editor -->
        <div class="rounded-lg border border-base-300 bg-base-100 p-4">
          <div class="mb-2 flex items-center justify-between">
            <h2 class="text-sm font-semibold text-base-content/60">Transcript</h2>
            <div class="flex items-center gap-2">
              <span class="text-xs text-base-content/40">
                {{ editorText.length }} chars
              </span>
              <button
                class="btn btn-ghost btn-xs"
                title="Copy transcript"
                @click="copyTranscript"
              >
                <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                </svg>
              </button>
            </div>
          </div>

          <!-- Segments view (with audio sync, collapsible) -->
          <div
            v-if="record.segments && record.segments.length > 0 && hasAudio()"
            class="mb-4 rounded-lg border border-base-200 bg-base-100 overflow-hidden"
          >
            <button
              class="flex items-center justify-between w-full px-3 py-2 text-sm font-medium text-base-content/70 hover:bg-base-200 transition-colors"
              @click="showSegments = !showSegments"
            >
              <span>Timestamped Segments</span>
              <svg
                class="h-4 w-4 transition-transform"
                :class="{ 'rotate-180': showSegments }"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            <div v-if="showSegments" class="max-h-[40vh] overflow-y-auto px-2 pb-2 space-y-1">
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

          <!-- Editable transcript textarea (always visible) -->
          <textarea
            v-model="editorText"
            class="textarea textarea-ghost w-full min-h-[40vh] text-base leading-relaxed resize-none"
            placeholder="Transcript will appear here..."
          ></textarea>
        </div>
      </div>

      <!-- Side panel -->
      <div class="space-y-4">
        <!-- Version History (collapsible) -->
        <VersionHistory
          v-if="showVersionHistory && record"
          :record-id="record.id"
          :current-version="record.version ?? 0"
          @restored="onVersionRestored"
        />

        <!-- AI Processing -->
        <AiProcessor
          :record="record"
          :editor-text="editorText"
          @result-saved="onResultSaved"
        />
      </div>
    </div>
  </div>
</template>
