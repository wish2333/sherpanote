<script setup lang="ts">
/**
 * EditorView - Transcript editing and AI processing page.
 *
 * Displays a record's transcript for editing, plays back
 * synchronized audio, and provides AI processing capabilities.
 *
 * Uses AiProcessor, ExportMenu, VersionHistory components.
 */
import { ref, onMounted, watch, computed } from "vue";
import { useRouter, useRoute } from "vue-router";
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
const showVersionHistory = ref(false);

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
  }
  isLoading.value = false;
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
  return !!record.value?.audio_path;
}

onMounted(loadRecord);
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
          <audio
            ref="audioRef"
            :src="`file://${record.audio_path}`"
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
            <span class="text-xs text-base-content/40">
              {{ editorText.length }} chars
            </span>
          </div>

          <!-- Segments view (with audio sync) or plain textarea -->
          <div v-if="record.segments && record.segments.length > 0 && hasAudio()" class="space-y-2 max-h-[60vh] overflow-y-auto">
            <p
              v-for="seg in record.segments"
              :key="seg.index"
              class="cursor-pointer rounded px-2 py-1 text-base leading-relaxed transition-colors"
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

          <textarea
            v-else
            v-model="editorText"
            class="textarea textarea-ghost w-full min-h-[60vh] text-base leading-relaxed resize-none"
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
          :current-version="record.version"
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
