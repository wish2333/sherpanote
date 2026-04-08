<script setup lang="ts">
/**
 * AudioManageView - Audio file management page.
 *
 * Lists all audio files in the data/audio directory,
 * shows which records they are linked to, and provides
 * delete/open/transcribe actions.
 */
import { ref, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { call, onEvent } from "../bridge";
import { useAppStore } from "../stores/appStore";

interface AudioFileInfo {
  file_path: string;
  file_name: string;
  size_mb: number;
  linked_records: { id: string; title: string }[];
}

interface TranscriptRecord {
  id: string;
  title: string;
  audio_path: string | null;
  transcript: string;
  segments: { text: string; start_time: number; end_time: number }[];
}

const store = useAppStore();
const router = useRouter();
const audioFiles = ref<AudioFileInfo[]>([]);
const isLoading = ref(false);
const deletingPath = ref<string | null>(null);
const transcribingPath = ref<string | null>(null);

function formatSize(mb: number): string {
  if (mb < 1) {
    return `${(mb * 1024).toFixed(0)} KB`;
  }
  return `${mb.toFixed(1)} MB`;
}

function formatDate(path: string): string {
  try {
    const name = path.split(/[/\\]/).pop() || "";
    const match = name.match(/(\d{4}-\d{2}-\d{2})/);
    if (match) return match[1];
    return "";
  } catch {
    return "";
  }
}

async function loadAudioFiles() {
  isLoading.value = true;
  const res = await call<AudioFileInfo[]>("list_audio_files");
  if (res.success && res.data) {
    audioFiles.value = res.data;
  } else {
    store.showToast(res.error ?? "Failed to load audio files", "error");
  }
  isLoading.value = false;
}

async function handleOpenFolder() {
  const res = await call<{ path: string }>("open_audio_folder");
  if (res.success) return;
  store.showToast(res.error ?? "Failed to open folder", "error");
}

function handleDelete(filePath: string) {
  deletingPath.value = filePath;
  const modal = document.getElementById("delete-audio-modal") as HTMLDialogElement;
  if (modal) modal.showModal();
}

async function confirmDelete() {
  if (!deletingPath.value) return;
  const res = await call("delete_audio_file", deletingPath.value);
  if (res.success) {
    audioFiles.value = audioFiles.value.filter((f) => f.file_path !== deletingPath.value);
    store.showToast("Audio file deleted", "success");
  } else {
    store.showToast(res.error ?? "Failed to delete", "error");
  }
  deletingPath.value = null;
  const modal = document.getElementById("delete-audio-modal") as HTMLDialogElement;
  if (modal) modal.close();
}

function cancelDelete() {
  deletingPath.value = null;
  const modal = document.getElementById("delete-audio-modal") as HTMLDialogElement;
  if (modal) modal.close();
}

function openRecord(id: string) {
  router.push(`/editor/${id}`);
}

async function handleTranscribe(filePath: string) {
  if (transcribingPath.value) {
    store.showToast("A transcription is already in progress", "warning");
    return;
  }
  transcribingPath.value = filePath;
  store.showToast("Starting transcription...", "info");

  // Listen for completion event.
  const offComplete = onEvent<{ segments: { text: string; start_time: number; end_time: number }[]; text: string; audio_path: string }>(
    "transcribe_complete",
    async (detail) => {
      offComplete();
      offError();
      const fileName = filePath.split(/[/\\]/).pop() || "Imported";
      const record = await call<TranscriptRecord>("save_record", {
        title: fileName.replace(/\.[^.]+$/, ""),
        transcript: detail.text ?? "",
        segments: detail.segments ?? [],
        audio_path: detail.audio_path ?? filePath,
      });
      if (record.success && record.data) {
        store.showToast("Transcription complete", "success");
        await loadAudioFiles();
        router.push(`/editor/${record.data.id}`);
      } else {
        store.showToast("Failed to save record", "error");
      }
      transcribingPath.value = null;
    },
  );

  const offError = onEvent<{ error: string }>("transcribe_error", (detail) => {
    offComplete();
    offError();
    store.showToast(detail.error ?? "Transcription failed", "error");
    transcribingPath.value = null;
  });

  // Store cleanup handles in case of unmount.
  cleanupFns.push(offComplete, offError);

  const res = await call("transcribe_file", filePath);
  if (!res.success) {
    offComplete();
    offError();
    store.showToast(res.error ?? "Failed to start transcription", "error");
    transcribingPath.value = null;
  }
}

// Cleanup event listeners on unmount.
const cleanupFns: (() => void)[] = [];

onMounted(loadAudioFiles);

onBeforeUnmount(() => {
  cleanupFns.forEach((fn) => fn());
  cleanupFns.length = 0;
});
</script>

<template>
  <div class="mx-auto max-w-5xl px-4 py-6">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-bold tracking-tight text-base-content">
        Audio Files
      </h1>
      <button class="btn btn-outline btn-sm" @click="handleOpenFolder">
        Open Folder
      </button>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="audioFiles.length === 0"
      class="flex flex-col items-center justify-center py-16 text-base-content/50"
    >
      <svg class="mb-3 h-12 w-12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M9 19V6l12-3v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="18" cy="15" r="3" />
      </svg>
      <p class="mb-1 text-lg">No audio files</p>
      <p class="text-sm">Audio files from recordings and imports will appear here.</p>
    </div>

    <!-- Audio file list -->
    <div v-else class="space-y-2">
      <div
        v-for="file in audioFiles"
        :key="file.file_path"
        class="card bg-base-100 border border-base-300 shadow-sm"
      >
        <div class="card-body p-4">
          <div class="flex items-center justify-between">
            <div class="min-w-0 flex-1">
              <h3 class="text-base font-medium truncate">
                {{ file.file_name }}
              </h3>
              <div class="mt-1 flex items-center gap-3 text-sm text-base-content/60">
                <span>{{ formatSize(file.size_mb) }}</span>
                <span v-if="formatDate(file.file_path)" class="text-base-content/40">
                  {{ formatDate(file.file_path) }}
                </span>
              </div>
              <!-- Linked records -->
              <div v-if="file.linked_records.length > 0" class="mt-2">
                <span class="text-xs text-base-content/40">Linked to:</span>
                <div class="flex flex-wrap gap-1 mt-1">
                  <button
                    v-for="rec in file.linked_records"
                    :key="rec.id"
                    class="badge badge-outline badge-sm cursor-pointer hover:badge-primary"
                    @click="openRecord(rec.id)"
                  >
                    {{ rec.title || rec.id.slice(0, 8) }}
                  </button>
                </div>
              </div>
              <div v-else class="mt-2">
                <span class="badge badge-ghost badge-sm">No linked record</span>
              </div>
            </div>
            <div class="flex items-center gap-1 ml-4">
              <!-- Transcribe button for unlinked files -->
              <button
                v-if="file.linked_records.length === 0"
                class="btn btn-ghost btn-xs"
                :class="{ 'loading': transcribingPath === file.file_path }"
                :disabled="!!transcribingPath"
                title="Transcribe this audio file"
                @click="handleTranscribe(file.file_path)"
              >
                <svg class="h-4 w-4 text-base-content/40 hover:text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
                  <path d="M19 10v2a7 7 0 01-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
              </button>
              <!-- Delete button -->
              <button
                class="btn btn-ghost btn-xs"
                title="Delete audio file"
                @click="handleDelete(file.file_path)"
              >
                <svg class="h-4 w-4 text-base-content/40 hover:text-error" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
                  <path d="M10 11v6" />
                  <path d="M14 11v6" />
                  <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete confirmation modal -->
    <dialog id="delete-audio-modal" class="modal">
      <div class="modal-box">
        <h3 class="text-lg font-bold">Delete Audio File</h3>
        <p class="py-4 text-sm">
          Are you sure you want to delete this audio file? This action cannot be undone.
          Any records linked to this file will lose their audio.
        </p>
        <div class="modal-action">
          <button class="btn btn-ghost btn-sm" @click="cancelDelete">Cancel</button>
          <button class="btn btn-error btn-sm" @click="confirmDelete">Delete</button>
        </div>
      </div>
      <form method="dialog" class="modal-backdrop" @click="cancelDelete">
        <button>close</button>
      </form>
    </dialog>
  </div>
</template>
