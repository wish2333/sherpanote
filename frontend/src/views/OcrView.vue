<script setup lang="ts">
/**
 * OcrView - 图片/PDF OCR 识别页面。
 *
 * 支持单张图片、批量（多文件分别生成记录）和顺序（合并为一个记录）处理模式。
 * 用户通过拖放或点击按钮选择文件，在列表中预览后点击开始处理。
 */
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useRouter } from "vue-router";
import { onEvent, pickImageFiles, ocrProcess, cancelOcr, getImagePreview, call, getAvailableBackends, detectPdfTextLayer } from "../bridge";
import { useAppStore } from "../stores/appStore";
import type { OcrFileEntry, OcrMode, DocumentConfig, PluginConfig } from "../types";

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

// ---- PDF text layer detection ----
type PdfTextStatus = "text" | "scan" | "unknown";
const pdfTextLayer = ref<Record<string, PdfTextStatus>>({});

async function detectTextLayer(filePath: string) {
  if (pdfTextLayer.value[filePath]) return;
  pdfTextLayer.value = { ...pdfTextLayer.value, [filePath]: "unknown" as PdfTextStatus };
  try {
    const res = await detectPdfTextLayer(filePath);
    if (res.success && res.data) {
      pdfTextLayer.value = { ...pdfTextLayer.value, [filePath]: res.data.has_text ? "text" : "scan" };
    }
  } catch {
    // Detection failed silently
  }
}

// ---- Engine availability ----
const availableBackends = ref<Record<string, boolean>>({});
const textEngine = computed(() => (store.documentConfig as DocumentConfig).text_pdf_engine);
const scanEngine = computed(() => (store.documentConfig as DocumentConfig).scan_pdf_engine);

async function loadBackends() {
  const res = await getAvailableBackends();
  if (res.success && res.data) availableBackends.value = res.data;
}

const isDoclingAvail = computed(() => availableBackends.value.docling === true);
const isOpendataAvail = computed(() => availableBackends.value.opendataloader === true);

// ---- Engine change handler ----
async function setTextEngine(engine: DocumentConfig["text_pdf_engine"]) {
  store.documentConfig = { ...store.documentConfig, text_pdf_engine: engine };
  call("update_config", {
    ai: store.aiConfig, asr: store.asrConfig, ocr: store.ocrConfig,
    plugin: store.pluginConfig, document: store.documentConfig,
    auto_ai_modes: store.autoAiModes, max_tokens_mode: "auto",
  });
}

async function setScanEngine(engine: DocumentConfig["scan_pdf_engine"]) {
  store.documentConfig = { ...store.documentConfig, scan_pdf_engine: engine };
  call("update_config", {
    ai: store.aiConfig, asr: store.asrConfig, ocr: store.ocrConfig,
    plugin: store.pluginConfig, document: store.documentConfig,
    auto_ai_modes: store.autoAiModes, max_tokens_mode: "auto",
  });
}

// ---- Drag & Drop (fullscreen, multi-file) ----
const fsDragCounter = ref(0);
const isDragOver = computed(() => fsDragCounter.value > 0);

function onWindowDragEnter(e: DragEvent) {
  e.preventDefault();
  fsDragCounter.value++;
}

function onWindowDragLeave(e: DragEvent) {
  e.preventDefault();
  fsDragCounter.value--;
}

function onWindowDragOver(e: DragEvent) {
  e.preventDefault();
}

function onWindowDrop(e: DragEvent) {
  e.preventDefault();
  fsDragCounter.value = 0;
  // Wait for pywebvue's native drop handler to capture paths
  setTimeout(async () => {
    const res = await call<string[]>("get_dropped_files");
    if (res.success && res.data && res.data.length > 0) {
      let added = 0;
      for (const p of res.data) {
        await addFileEntry(p);
        added++;
      }
      if (added > 0) store.showToast(`已添加 ${added} 个文件`, "success");
    }
  }, 150);
}

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
  const type: "image" | "pdf" | "office" = ext === "pdf"
    ? "pdf"
    : ["docx", "pptx", "xlsx"].includes(ext)
      ? "office"
      : "image";
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
  if (type === "pdf") detectTextLayer(p);
}

async function addFiles() {
  try {
    const res = await pickImageFiles();
    if (!res.success || !res.data) {
      if (res.error) store.showToast(`选择文件失败: ${res.error}`, "error");
      return;
    }
    const newPaths = res.data as string[];
    let added = 0;
    for (const p of newPaths) {
      await addFileEntry(p);
      added++;
    }
    if (added > 0) store.showToast(`已添加 ${added} 个文件`, "success");
  } catch (e: any) {
    store.showToast(`选择文件失败: ${e?.message ?? e}`, "error");
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

onMounted(async () => {
  window.addEventListener("dragenter", onWindowDragEnter as EventListener);
  window.addEventListener("dragleave", onWindowDragLeave as EventListener);
  window.addEventListener("dragover", onWindowDragOver as EventListener);
  window.addEventListener("drop", onWindowDrop as EventListener);

  // Sync store with persisted backend config
  const configRes = await call<{
    plugin?: PluginConfig; document?: DocumentConfig;
  }>("get_config");
  if (configRes.success && configRes.data) {
    if (configRes.data.plugin) store.pluginConfig = configRes.data.plugin;
    if (configRes.data.document) store.documentConfig = configRes.data.document;
  }

  loadBackends();
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
  offComplete = onEvent<{ status: string; records?: Array<{ id: string }>; error?: string; backend_used?: string }>(
    "ocr_complete",
    (detail) => {
      isProcessing.value = false;
      if (detail.status === "done" && detail.records && detail.records.length > 0) {
        // Check if the engine actually used differs from the configured one
        const dc = store.documentConfig as DocumentConfig | undefined;
        if (dc && detail.backend_used) {
          const configured = dc.text_pdf_engine;
          if (configured !== "markitdown" && detail.backend_used !== configured && detail.backend_used !== "ppocr") {
            // User selected a non-default engine but a different one was used
            const nameMap: Record<string, string> = {
              docling: "Docling",
              opendataloader: "OpenDataLoader",
              markitdown: "markitdown",
              ppocr: "PP-OCR",
            };
            store.showToast(
              `注意：所选引擎 ${nameMap[configured] ?? configured} 不可用，已使用 ${nameMap[detail.backend_used] ?? detail.backend_used}`,
              "warning",
            );
          }
        }
        store.showToast("OCR 识别完成", "success");
        router.push(`/editor/${detail.records[0].id}`);
      } else if (detail.status === "cancelled") {
        store.showToast("OCR 已取消", "info");
      } else if (detail.status === "error") {
        const errMsg = detail.error ?? "Unknown error";
        store.showToast(
          `Processing failed: ${errMsg}. Try switching the default engine in Settings > OCR / Documents.`,
          "error",
        );
      }
    },
  );
});

onUnmounted(() => {
  offProgress?.();
  offComplete?.();
  window.removeEventListener("dragenter", onWindowDragEnter as EventListener);
  window.removeEventListener("dragleave", onWindowDragLeave as EventListener);
  window.removeEventListener("dragover", onWindowDragOver as EventListener);
  window.removeEventListener("drop", onWindowDrop as EventListener);
});
</script>

<template>
  <div
    class="container mx-auto max-w-4xl px-4 py-6"
  >
    <!-- Fullscreen drag overlay -->
    <div
      v-if="isDragOver"
      class="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-primary/10"
    >
      <div class="rounded-xl border-2 border-dashed border-primary bg-base-100/80 px-12 py-8 text-center">
        <svg xmlns="http://www.w3.org/2000/svg" class="mx-auto h-10 w-10 text-primary mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        <p class="text-lg font-semibold text-primary">松开以添加文件</p>
        <p class="text-base-content/50 text-sm mt-1">支持 PNG, JPG, BMP, TIFF, WebP, PDF, DOCX, PPTX, XLSX</p>
      </div>
    </div>

    <h1 class="text-2xl font-bold tracking-tight text-base-content mb-6">OCR</h1>

    <!-- Compact toolbar: title + add files -->
    <div class="flex items-center gap-3 mb-6">
      <div class="form-control flex-1">
        <input
          v-model="titleInput"
          type="text"
          placeholder="标题（可选，留空自动生成）"
          class="input input-bordered input-sm w-full"
        />
      </div>
      <button
        class="btn btn-primary btn-sm whitespace-nowrap"
        :disabled="isProcessing"
        @click="addFiles"
      >
        <svg class="h-4 w-4 mr-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        选择文件
      </button>
    </div>

    <!-- PDF Engine selector -->
    <div class="card bg-base-100 border border-base-300 shadow-md mb-6">
      <div class="card-body py-3">
        <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
          <label class="flex items-center gap-2">
            <span class="text-sm whitespace-nowrap">文本层 PDF</span>
            <select class="select select-bordered select-sm w-44"
              :value="textEngine"
              @change="setTextEngine(($event.target as HTMLSelectElement).value as DocumentConfig['text_pdf_engine'])"
            >
              <option value="markitdown">markitdown</option>
              <option value="opendataloader" :disabled="!isOpendataAvail">opendataloader{{ !isOpendataAvail ? ' (未安装)' : '' }}</option>
              <option value="docling" :disabled="!isDoclingAvail">docling{{ !isDoclingAvail ? ' (未安装)' : '' }}</option>
              <option value="ppocr">PP-OCR</option>
            </select>
          </label>
          <label class="flex items-center gap-2">
            <span class="text-sm whitespace-nowrap">扫描 PDF</span>
            <select class="select select-bordered select-sm w-44"
              :value="scanEngine"
              @change="setScanEngine(($event.target as HTMLSelectElement).value as DocumentConfig['scan_pdf_engine'])"
            >
              <option value="ppocr">PP-OCR</option>
              <option value="docling" :disabled="!isDoclingAvail">docling{{ !isDoclingAvail ? ' (未安装)' : '' }}</option>
            </select>
          </label>
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
                {{ file.type === "pdf" ? "PDF" : file.type === "office" ? "DOC" : "IMG" }}
              </span>
            </div>

            <!-- File info -->
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium truncate">{{ file.name }}</p>
              <div class="flex items-center gap-2 flex-wrap">
                <span
                  class="badge badge-xs"
                  :class="file.type === 'pdf' ? 'badge-warning' : file.type === 'office' ? 'badge-success' : 'badge-info'"
                >
                  {{ file.type === "pdf" ? "PDF" : file.type === "office" ? "DOC" : "IMG" }}
                </span>
                <span v-if="file.type === 'pdf' && pdfTextLayer[file.path]" class="badge badge-xs"
                  :class="pdfTextLayer[file.path] === 'text' ? 'badge-success' : 'badge-error'"
                >
                  {{ pdfTextLayer[file.path] === "text" ? "text" : "scan" }}
                </span>
                <span v-if="file.type === 'pdf' && !pdfTextLayer[file.path]" class="badge badge-xs badge-ghost opacity-50">
                  <span class="loading loading-spinner loading-xs"></span>
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
