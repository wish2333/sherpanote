<script setup lang="ts">
/**
 * OcrView - 图片/PDF OCR 识别页面。
 *
 * 支持单张图片、批量（多文件分别生成记录）和顺序（合并为一个记录）处理模式。
 * 用户通过拖放或点击按钮选择文件，在列表中预览后点击开始处理。
 */
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useRouter } from "vue-router";
import { onEvent, pickImageFiles, ocrProcess, cancelOcr, getImagePreview } from "../bridge";
import { useDragDrop } from "../composables/useDragDrop";
import { useAppStore } from "../stores/appStore";
import type { OcrFileEntry, OcrMode } from "../types";

const router = useRouter();
const store = useAppStore();

// ---- State ----
const files = ref<OcrFileEntry[]>([]);
const ocrMode = ref<OcrMode>("single");
const titleInput = ref("");
const isProcessing = ref(false);
const progress = ref({ current: 0, total: 0, percent: 0 });
const previewMap = ref<Record<string, string>>({});

const canProcess = computed(() => files.value.length > 0 && !isProcessing.value);

// ---- Drag & Drop ----
const {
  isDraggingOver: isDragOver,
  onDragEnter,
  onDragLeave,
  onDragOver,
  onDrop,
} = useDragDrop((filePath: string) => {
  addFileEntry(filePath);
});

// ---- File management ----
function formatSize(sizeMb: number): string {
  if (sizeMb < 0.01) return "";
  if (sizeMb >= 1) return `${sizeMb.toFixed(1)} MB`;
  return `${(sizeMb * 1024).toFixed(0)} KB`;
}

async function addFileEntry(p: string) {
  if (files.value.some((f) => f.path === p)) return;
  const name = p.split(/[\\/]/).pop() ?? p;
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  const type: "image" | "pdf" = ext === "pdf" ? "pdf" : "image";
  let sizeMb = 0;
  try {
    const fs = await (window as any).pywebview?.api?.get_file_size?.(p);
    if (fs?.success && fs.data > 0) {
      sizeMb = Number((fs.data / (1024 * 1024)).toFixed(2));
    }
  } catch {
    // ignore
  }
  files.value.push({ path: p, name, type, size_mb: sizeMb });
}

async function addFiles() {
  const res = await pickImageFiles();
  if (!res.success || !res.data) return;
  const newPaths = res.data as string[];
  for (const p of newPaths) {
    await addFileEntry(p);
  }
}

function removeFile(index: number) {
  const removed = files.value.splice(index, 1);
  for (const r of removed) {
    delete previewMap.value[r.path];
  }
}

function clearFiles() {
  files.value = [];
  previewMap.value = {};
}

// ---- Previews ----
async function loadPreview(entry: OcrFileEntry) {
  if (previewMap.value[entry.path]) return;
  try {
    const res = await getImagePreview(entry.path);
    if (res.success && res.data) {
      previewMap.value[entry.path] = `data:${res.data.mime};base64,${res.data.base64}`;
    }
  } catch {
    // Preview not critical, skip silently
  }
}

watch(files, () => {
  files.value.forEach((entry) => loadPreview(entry));
}, { deep: true });

// ---- Processing ----
async function startOcr() {
  if (!canProcess.value) return;
  isProcessing.value = true;
  progress.value = { current: 0, total: 0, percent: 0 };

  let mode = ocrMode.value;
  if (files.value.length === 1) {
    mode = "single";
  }

  const filePaths = files.value.map((f: OcrFileEntry) => f.path);
  const title = titleInput.value.trim() || undefined;

  await ocrProcess(filePaths, mode, title);
}

function cancelProcessing() {
  cancelOcr();
}

// ---- Events ----
let offProgress: (() => void) | null = null;
let offComplete: (() => void) | null = null;

onMounted(() => {
  offProgress = onEvent<{ status: string; current: number; total: number; percent: number }>(
    "ocr_progress",
    (detail) => {
      progress.value = {
        current: detail.current,
        total: detail.total,
        percent: detail.percent,
      };
    },
  );
  offComplete = onEvent<{ status: string; records?: Array<{ id: string }>; error?: string }>(
    "ocr_complete",
    (detail) => {
      isProcessing.value = false;
      if (detail.status === "done" && detail.records && detail.records.length > 0) {
        store.showToast("OCR 识别完成", "success");
        router.push(`/editor/${detail.records[0].id}`);
      } else if (detail.status === "cancelled") {
        store.showToast("OCR 已取消", "info");
      } else if (detail.status === "error") {
        store.showToast(`OCR 识别失败: ${detail.error ?? "未知错误"}`, "error");
      }
    },
  );
});

onUnmounted(() => {
  offProgress?.();
  offComplete?.();
});
</script>

<template>
  <div
    class="container mx-auto max-w-4xl px-4 py-6"
    @dragenter="onDragEnter"
    @dragleave="onDragLeave"
    @dragover="onDragOver"
    @drop="onDrop"
  >
    <h1 class="text-2xl font-bold tracking-tight text-base-content mb-6">OCR</h1>

    <!-- Upload area -->
    <div class="card bg-base-100 border border-base-300 shadow-md mb-6">
      <div class="card-body">
        <div
          class="border-2 border-dashed rounded-lg p-8 text-center transition-colors"
          :class="isDragOver ? 'border-primary bg-primary/5' : 'border-base-300 hover:border-primary'"
        >
          <svg class="h-10 w-10 mx-auto text-base-content/30 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
          <p v-if="!isDragOver" class="text-base-content/60 text-sm">拖放图片/PDF 文件到此处，或</p>
          <p v-else class="text-primary font-medium text-sm">松开以添加文件</p>
          <p class="text-base-content/40 text-xs mt-1">支持 PNG, JPG, BMP, TIFF, WebP, PDF</p>
          <button
            class="btn btn-primary btn-sm mt-3"
            :disabled="isProcessing"
            @click="addFiles"
          >
            选择文件
          </button>
        </div>

        <!-- Title input -->
        <div class="form-control mt-4">
          <label class="label">
            <span class="label-text text-sm">标题（可选）</span>
          </label>
          <input
            v-model="titleInput"
            type="text"
            placeholder="留空则自动生成标题"
            class="input input-bordered input-sm w-full"
          />
        </div>
      </div>
    </div>

    <!-- File list -->
    <div v-if="files.length > 0" class="card bg-base-100 border border-base-300 shadow-md mb-6">
      <div class="card-body">
        <div class="flex items-center justify-between mb-3">
          <h2 class="card-title text-base">
            文件列表
            <span class="badge badge-sm">{{ files.length }}</span>
          </h2>
          <div class="flex gap-2">
            <button class="btn btn-ghost btn-xs" @click="clearFiles">清空</button>
            <button class="btn btn-primary btn-xs" @click="addFiles">添加文件</button>
          </div>
        </div>

        <!-- Mode selector (only when multiple files) -->
        <div v-if="files.length > 1" class="flex items-center gap-3 mb-4">
          <span class="text-sm text-base-content/70">处理模式：</span>
          <div class="join">
            <button
              v-for="m in ([
                { value: 'batch', label: '批量（分别生成记录）' },
                { value: 'sequential', label: '顺序（合并为一个记录）' },
              ] as const)"
              :key="m.value"
              class="join-item btn btn-sm"
              :class="ocrMode === m.value ? 'btn-primary' : 'btn-ghost'"
              @click="ocrMode = m.value"
            >
              {{ m.label }}
            </button>
          </div>
        </div>

        <!-- Mode description -->
        <div class="text-xs text-base-content/50 mb-3">
          <span v-if="files.length === 1">单文件模式：一张图片 -> 一条记录</span>
          <span v-else-if="ocrMode === 'batch'">批量模式：每个文件生成一条单独的记录</span>
          <span v-else>顺序模式：所有文件合并为一条记录</span>
        </div>

        <!-- File entries -->
        <div class="space-y-2 max-h-80 overflow-y-auto">
          <div
            v-for="(file, idx) in files"
            :key="file.path"
            class="flex items-center gap-3 p-2 rounded-lg bg-base-200 hover:bg-base-300 transition-colors"
          >
            <!-- Thumbnail -->
            <div class="w-12 h-12 rounded overflow-hidden flex-shrink-0 bg-base-300 flex items-center justify-center">
              <img
                v-if="previewMap[file.path]"
                :src="previewMap[file.path]"
                :alt="file.name"
                class="w-full h-full object-cover"
                @error="delete previewMap[file.path]"
              />
              <span v-else class="text-xs text-base-content/40">
                {{ file.type === "pdf" ? "PDF" : "IMG" }}
              </span>
            </div>

            <!-- File info -->
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium truncate">{{ file.name }}</p>
              <div class="flex items-center gap-2">
                <span
                  class="badge badge-xs"
                  :class="file.type === 'pdf' ? 'badge-warning' : 'badge-info'"
                >
                  {{ file.type === "pdf" ? "PDF" : "IMG" }}
                </span>
                <span v-if="formatSize(file.size_mb)" class="text-xs text-base-content/40">
                  {{ formatSize(file.size_mb) }}
                </span>
              </div>
            </div>

            <!-- Remove button -->
            <button
              class="btn btn-ghost btn-xs btn-circle"
              @click="removeFile(idx)"
              :disabled="isProcessing"
            >
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Process button -->
    <div v-if="files.length > 0" class="flex justify-center gap-3">
      <button
        class="btn btn-primary"
        :class="{ 'btn-disabled': !canProcess }"
        :disabled="!canProcess"
        @click="startOcr"
      >
        <svg v-if="!isProcessing" class="h-4 w-4 mr-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
        </svg>
        <span v-if="isProcessing" class="loading loading-spinner loading-sm"></span>
        {{ isProcessing ? "处理中..." : "开始识别" }}
      </button>
      <button
        v-if="isProcessing"
        class="btn btn-ghost"
        @click="cancelProcessing"
      >
        取消
      </button>
    </div>

    <!-- Progress bar -->
    <div v-if="isProcessing" class="card bg-base-100 border border-base-300 shadow-md mt-6">
      <div class="card-body">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-base-content/70">
            正在处理 {{ progress.current }} / {{ progress.total }}
          </span>
          <span class="text-sm font-medium">{{ progress.percent }}%</span>
        </div>
        <progress
          class="progress progress-primary w-full"
          :value="progress.percent"
          max="100"
        ></progress>
      </div>
    </div>
  </div>
</template>
