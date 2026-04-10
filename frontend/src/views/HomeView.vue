<script setup lang="ts">
/**
 * HomeView - Record list page with search, filter, and drag-drop import.
 *
 * Uses SearchBar, RecordCard, and useStorage composable.
 * Supports drag-and-drop audio file import.
 */
import { ref, computed, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useStorage } from "../composables/useStorage";
import { useTranscript } from "../composables/useTranscript";
import { useDragDrop } from "../composables/useDragDrop";
import { useAppStore } from "../stores/appStore";
import SearchBar from "../components/SearchBar.vue";
import RecordCard from "../components/RecordCard.vue";
import type { TranscriptRecord, RecordFilter } from "../types";

const router = useRouter();
const route = useRoute();
const store = useAppStore();
const { isLoading, loadRecords, deleteRecord, importRecord } = useStorage();
const { transcribeFile, saveAsRecord } = useTranscript();

const records = ref<TranscriptRecord[]>([]);
const deletingId = ref<string | null>(null);

/** Extract unique categories from records. */
const categories = computed(() => {
  const cats = new Set<string>();
  records.value.forEach((r) => {
    if (r.category) cats.add(r.category);
  });
  return Array.from(cats).sort();
});

async function handleSearch(filter: RecordFilter) {
  const results = await loadRecords(filter);
  records.value = results;
}

function openRecord(id: string) {
  router.push(`/editor/${id}`);
}

function newRecord() {
  router.push("/record");
}

/** Trigger hidden file input for text import. */
const textImportInput = ref<HTMLInputElement | null>(null);

function triggerTextImport() {
  textImportInput.value?.click();
}

async function handleTextImport(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
  if (ext !== ".md" && ext !== ".txt") {
    store.showToast("Only .md and .txt files are supported for text import", "error");
    return;
  }

  // In pywebview, file.name is the full path via drag-drop.
  // For file input, we use the name as path hint.
  const record = await importRecord(file.name);
  if (record) {
    records.value = [record, ...records.value];
    router.push(`/editor/${record.id}`);
  }

  // Reset input so re-importing the same file works.
  input.value = "";
}

async function handleDelete(id: string) {
  deletingId.value = id;
  // Open DaisyUI modal.
  const modal = document.getElementById("delete-confirm-modal") as HTMLDialogElement;
  if (modal) modal.showModal();
}

async function confirmDelete() {
  if (!deletingId.value) return;
  const success = await deleteRecord(deletingId.value);
  if (success) {
    records.value = records.value.filter((r) => r.id !== deletingId.value);
  }
  deletingId.value = null;
  const modal = document.getElementById("delete-confirm-modal") as HTMLDialogElement;
  if (modal) modal.close();
}

function cancelDelete() {
  deletingId.value = null;
  const modal = document.getElementById("delete-confirm-modal") as HTMLDialogElement;
  if (modal) modal.close();
}

// Drag-and-drop support (uses counter-based composable to prevent flicker).
const audioExtensions = [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"];

const { isDraggingOver, onDragEnter, onDragLeave, onDragOver, onDrop } = useDragDrop(
  (filePath) => {
    const ext = filePath.substring(filePath.lastIndexOf(".")).toLowerCase();
    if (!audioExtensions.includes(ext)) {
      store.showToast("Unsupported audio format", "error");
      return;
    }
    handleFileImport(filePath);
  },
);

async function handleFileImport(filePath: string) {
  const result = await transcribeFile(filePath);
  if (result) {
    const record = await saveAsRecord(
      filePath.split("/").pop()?.split("\\").pop() || "Imported",
      result.text,
      result.segments,
      filePath,
    );
    if (record) {
      router.push(`/editor/${record.id}`);
    }
  }
}

onMounted(async () => {
  const results = await loadRecords();
  records.value = results;

  const fileQuery = route.query.file as string | undefined;
  if (fileQuery) {
    await handleFileImport(fileQuery);
  }
});
</script>

<template>
  <div
    class="mx-auto max-w-5xl px-4 py-6"
    @dragenter="onDragEnter"
    @dragleave="onDragLeave"
    @dragover="onDragOver"
    @drop="onDrop"
  >
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-bold tracking-tight text-base-content">
        记录
      </h1>
      <button class="btn btn-primary btn-sm" @click="newRecord">
        + 新建记录
      </button>
      <button class="btn btn-outline btn-sm" @click="triggerTextImport">
        导入文本
      </button>
      <!-- Hidden file input for text import -->
      <input
        ref="textImportInput"
        type="file"
        accept=".md,.txt"
        class="hidden"
        @change="handleTextImport"
      />
    </div>

    <!-- Search + filter -->
    <SearchBar :categories="categories" @search="handleSearch" />

    <!-- Drag overlay -->
    <div
      v-if="isDraggingOver"
      class="mb-4 rounded-lg border-2 border-dashed border-primary bg-primary/5 p-8 text-center"
    >
      <p class="text-primary font-medium">拖放音频文件到此处以转写</p>
    </div>

    <!-- Loading state -->
    <div v-if="isLoading" class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="records.length === 0"
      class="flex flex-col items-center justify-center py-16 text-base-content/50"
    >
      <svg class="mb-3 h-12 w-12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <p class="mb-1 text-lg">暂无记录</p>
      <p class="text-sm">点击"新建记录"开始录音，或拖放音频文件到此处。</p>
    </div>

    <!-- Record list -->
    <div v-else class="space-y-2">
      <RecordCard
        v-for="record in records"
        :key="record.id"
        :record="record"
        @click="openRecord(record.id)"
        @delete="handleDelete(record.id)"
      />
    </div>

    <!-- Delete confirmation modal -->
    <dialog id="delete-confirm-modal" class="modal">
      <div class="modal-box">
        <h3 class="text-lg font-bold">删除记录</h3>
        <p class="py-4 text-sm">
          确定要删除这条记录吗？此操作不可撤销。
        </p>
        <div class="modal-action">
          <button class="btn btn-ghost btn-sm" @click="cancelDelete">取消</button>
          <button class="btn btn-error btn-sm" @click="confirmDelete">删除</button>
        </div>
      </div>
      <form method="dialog" class="modal-backdrop" @click="cancelDelete">
        <button>close</button>
      </form>
    </dialog>
  </div>
</template>
