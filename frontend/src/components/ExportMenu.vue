<script setup lang="ts">
/**
 * ExportMenu - Dropdown menu for exporting records.
 *
 * Supports md, txt, docx, srt formats with loading state.
 * Shows export path and open button after export.
 * Uses useStorage composable for export API calls.
 */
import { ref } from "vue";
import { call } from "../bridge";
import { useAppStore } from "../stores/appStore";
import type { ExportFormat } from "../types";

const props = defineProps<{
  recordId: string;
}>();

const store = useAppStore();

const isExporting = ref(false);
const exportingFormat = ref<ExportFormat | null>(null);
const lastExportPath = ref<string | null>(null);
const includeAi = ref(true);

const formats: { key: ExportFormat; label: string }[] = [
  { key: "md", label: "Markdown (.md)" },
  { key: "txt", label: "Plain Text (.txt)" },
  { key: "docx", label: "Word (.docx)" },
  { key: "srt", label: "Subtitles (.srt)" },
];

async function handleExport(fmt: ExportFormat) {
  isExporting.value = true;
  exportingFormat.value = fmt;
  lastExportPath.value = null;

  const res = await call<{ file_path: string }>("export_record", props.recordId, fmt, includeAi.value);
  if (res.success && res.data) {
    lastExportPath.value = res.data.file_path;
    store.showToast(`Exported as .${fmt}`, "success");
  } else {
    store.showToast(res.error ?? "Export failed", "error");
  }

  isExporting.value = false;
  exportingFormat.value = null;
}

async function openExportedFile() {
  if (!lastExportPath.value) return;
  await call("open_file", lastExportPath.value);
}

async function openExportFolder() {
  if (!lastExportPath.value) return;
  const folder = lastExportPath.value.replace(/[\\/][^\\/]+$/, "");
  await call("open_folder", folder);
}

function formatPath(path: string): string {
  return path.replace(/\\/g, "/");
}
</script>

<template>
  <div class="flex items-center gap-1">
    <!-- Export dropdown -->
    <div class="dropdown dropdown-end">
      <div tabindex="0" role="button" class="btn btn-outline btn-sm">
        <span v-if="isExporting" class="loading loading-spinner loading-xs"></span>
        导出
        <svg class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </div>
      <ul tabindex="0" class="dropdown-content menu z-[1] w-56 rounded-box border border-base-300 bg-base-100 p-2 shadow-md">
        <!-- Include AI results toggle -->
        <li class="px-1 pb-1 mb-1 border-b border-base-200">
          <label class="label cursor-pointer gap-2 justify-start">
            <input v-model="includeAi" type="checkbox" class="toggle toggle-primary toggle-xs" />
            <span class="label-text text-sm">包含 AI 结果</span>
          </label>
        </li>
        <!-- Format options -->
        <li v-for="fmt in formats" :key="fmt.key">
          <a :class="{ 'pointer-events-none opacity-50': isExporting }" @click="handleExport(fmt.key)">
            {{ fmt.label }}
            <span v-if="exportingFormat === fmt.key" class="loading loading-spinner loading-xs"></span>
          </a>
        </li>
        <!-- Open last export -->
        <div v-if="lastExportPath" class="divider my-0"></div>
        <li v-if="lastExportPath">
          <a @click="openExportedFile">
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            打开文件
          </a>
        </li>
        <li v-if="lastExportPath">
          <a @click="openExportFolder">
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
            </svg>
            打开文件夹
          </a>
        </li>
      </ul>
    </div>

    <!-- Last export path tooltip -->
    <span
      v-if="lastExportPath"
      class="text-xs text-base-content/40 max-w-[200px] truncate"
      :title="lastExportPath"
    >
      {{ formatPath(lastExportPath) }}
    </span>
  </div>
</template>
