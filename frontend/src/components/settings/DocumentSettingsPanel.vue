<script setup lang="ts">
/**
 * DocumentSettingsPanel - Document extraction engine and plugin management.
 *
 * Provides UI for selecting PDF processing engines, installing/uninstalling
 * optional backends (docling, opendataloader-pdf), and configuring environment
 * settings (Java path, docling model directory).
 */
import { ref, computed, watch, onMounted } from "vue";
import { useAppStore } from "../../stores/appStore";
import { usePlugin } from "../../composables/usePlugin";
import { pickFile, pickDirectory } from "../../bridge";
import type { PluginConfig, DocumentConfig } from "../../types";

const props = defineProps<{
  pluginConfig: PluginConfig;
  documentConfig: DocumentConfig;
}>();

const emit = defineEmits<{
  "update:pluginConfig": [value: PluginConfig];
  "update:documentConfig": [value: DocumentConfig];
  saveRequested: [];
}>();

const store = useAppStore();
const {
  pluginStatuses,
  availableBackends,
  javaResult,
  installingPackage,
  installProgress,
  uninstallingPackage,
  isDetectingJava,
  lastError,
  loadStatuses,
  doInstall,
  doUninstall,
  doDestroyVenv,
  doPreDownloadDocling,
  runDetectJava,
} = usePlugin();

// ---- Derived state ----
// Check both availableBackends API and pluginStatuses for reliability
const isDoclingAvailable = computed(
  () => availableBackends.value.docling === true
     || pluginStatuses.value.docling?.installed === true,
);
const isOpendataAvailable = computed(
  () => availableBackends.value.opendataloader === true
     || pluginStatuses.value.opendataloader?.installed === true,
);
const isTextEngineUnavailable = computed(() => {
  const engine = props.documentConfig.text_pdf_engine;
  return (
    (engine === "docling" && !isDoclingAvailable.value) ||
    (engine === "opendataloader" && !isOpendataAvailable.value)
  );
});
const isScanEngineUnavailable = computed(() => {
  return (
    props.documentConfig.scan_pdf_engine === "docling" &&
    !isDoclingAvailable.value
  );
});

// ---- Backend metadata ----
interface BackendMeta {
  key: string;
  displayName: string;
  description: string;
  pipName: string;
  diskEstimate: string;
  networkNote: string;
}

const backends: BackendMeta[] = [
  {
    key: "docling",
    displayName: "Docling",
    description:
      "AI 驱动的文档提取，支持排版分析和表格。首次使用需下载约 1.5GB 模型。",
    pipName: "docling",
    diskEstimate: "约 2 GB",
    networkNote:
      "首次模型下载约需 1.5GB 网络流量。",
  },
  {
    key: "opendataloader",
    displayName: "OpenDataLoader-PDF",
    description:
      "基于 Java 的 PDF 排版提取。需要 Java 11+。",
    pipName: "opendataloader-pdf",
    diskEstimate: "约 500 MB",
    networkNote: "需要网络下载包。",
  },
];

// ---- Install confirm dialog ----
const showInstallDialog = ref(false);
const installTarget = ref<BackendMeta | null>(null);
const uninstallConfirm = ref<string | null>(null);

function requestInstall(backend: BackendMeta) {
  installTarget.value = backend;
  showInstallDialog.value = true;
}

function confirmInstall() {
  if (!installTarget.value) return;
  showInstallDialog.value = false;
  store.showToast(
    `正在安装 ${installTarget.value.displayName}...`,
    "info",
  );
  doInstall(installTarget.value.pipName);
}

function requestUninstall(key: string) {
  uninstallConfirm.value = key;
}

async function confirmUninstall(key: string) {
  uninstallConfirm.value = null;
  await doUninstall(key);
}

// ---- Watch for install errors ----
watch(
  () => lastError.value,
  (msg) => {
    if (msg) {
      store.showToast(msg, "error");
      lastError.value = null;
    }
  },
);

// ---- Watch for install completion toast ----
watch(
  () => installingPackage.value,
  (newVal, oldVal) => {
    if (!newVal && oldVal) {
      // installingPackage transitioned from non-null to null = completed
      if (!lastError.value) {
        store.showToast("插件安装成功", "success");
      }
    }
  },
);

// ---- Java detection ----
const manualJavaPath = computed({
  get: () => props.pluginConfig.manual_java_path ?? "",
  set: (v) => {
    emit("update:pluginConfig", {
      ...props.pluginConfig,
      manual_java_path: v || null,
    });
  },
});

const doclingArtifactsPath = computed({
  get: () => props.pluginConfig.docling_artifacts_path ?? "",
  set: (v) => {
    emit("update:pluginConfig", {
      ...props.pluginConfig,
      docling_artifacts_path: v || null,
    });
  },
});

function handlePickJavaPath() {
  pickFile([
    "可执行文件 (*.exe)",
    "所有文件 (*.*)",
  ]).then((res) => {
    if (res.success && res.data) {
      manualJavaPath.value = res.data.path;
    }
  });
}

function handlePickDoclingArtifacts() {
  pickDirectory().then((res) => {
    if (res.success && res.data) {
      doclingArtifactsPath.value = res.data.path;
    }
  });
}

// ---- Engine selection ----
function updateTextEngine(engine: DocumentConfig["text_pdf_engine"]) {
  emit("update:documentConfig", {
    ...props.documentConfig,
    text_pdf_engine: engine,
  });
}

function updateScanEngine(engine: DocumentConfig["scan_pdf_engine"]) {
  emit("update:documentConfig", {
    ...props.documentConfig,
    scan_pdf_engine: engine,
  });
}

// ---- Destroy venv ----
const showDestroyConfirm = ref(false);

async function handleDestroyVenv() {
  showDestroyConfirm.value = false;
  store.showToast("正在销毁插件虚拟环境...", "info");
  await doDestroyVenv();
  if (!lastError.value) {
    store.showToast("插件虚拟环境已销毁", "success");
  }
}

// ---- Init ----
onMounted(() => {
  loadStatuses();
  runDetectJava();
});
</script>

<template>
  <div class="space-y-4">
    <!-- Card 1: PDF Processing Mode -->
    <div class="card bg-base-100 border border-base-300 shadow-md">
      <div class="card-body">
        <h3 class="card-title text-base">PDF 处理模式</h3>
        <p class="text-sm text-base-content/60">
          为不同类型的 PDF 选择默认处理引擎。
        </p>

        <!-- Text-layer PDF engine -->
        <div class="form-control w-full max-w-xl">
          <label class="label">
            <span class="label-text font-medium">文本层 PDF 引擎</span>
          </label>
          <select
            class="select select-bordered select-sm"
            :value="documentConfig.text_pdf_engine"
            @change="
              updateTextEngine(
                ($event.target as HTMLSelectElement).value as DocumentConfig['text_pdf_engine'],
              )
            "
          >
            <option value="markitdown">
              markitdown（纯 Python，无需模型）
            </option>
            <option
              value="opendataloader"
              :disabled="!isOpendataAvailable"
            >
              opendataloader-pdf{{ !isOpendataAvailable ? "（未安装）" : "" }}
            </option>
            <option value="docling" :disabled="!isDoclingAvailable">
              docling{{ !isDoclingAvailable ? "（未安装）" : "" }}
            </option>
            <option value="ppocr">PP-OCR（始终可用）</option>
          </select>
          <label class="label">
            <span class="label-text-alt text-base-content/50">
              <span v-if="documentConfig.text_pdf_engine === 'markitdown'">
                轻量提取，适合文本为主的 PDF。
              </span>
              <span v-else-if="documentConfig.text_pdf_engine === 'opendataloader'">
                需要 Java 11+。排版保持效果好。
              </span>
              <span v-else-if="documentConfig.text_pdf_engine === 'docling'">
                AI 增强，支持表格提取。首次使用需下载约 1.5GB 模型。
              </span>
              <span v-else> 即使对文本 PDF 也回退为图片 OCR。</span>
            </span>
          </label>
        </div>

        <div
          v-if="isTextEngineUnavailable"
          class="alert alert-warning mt-2"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
          <span class="text-sm">
            所选引擎未安装。请在下方"后端管理"中安装，或选择其他引擎。
          </span>
        </div>

        <!-- Scan PDF engine -->
        <div class="form-control w-full max-w-xl mt-2">
          <label class="label">
            <span class="label-title font-medium">
              扫描 PDF 引擎（无文本层）
            </span>
          </label>
          <select
            class="select select-bordered select-sm"
            :value="documentConfig.scan_pdf_engine"
            @change="
              updateScanEngine(
                ($event.target as HTMLSelectElement).value as DocumentConfig['scan_pdf_engine'],
              )
            "
          >
            <option value="ppocr">PP-OCR（始终可用）</option>
            <option value="docling" :disabled="!isDoclingAvailable">
              docling{{ !isDoclingAvailable ? "（未安装）" : "" }}
            </option>
          </select>
          <label class="label">
            <span class="label-text-alt text-base-content/50">
              <span v-if="documentConfig.scan_pdf_engine === 'docling'">
                使用 docling OCR 后端，AI 排版分析。
              </span>
              <span v-else>
                PDF 页面转图片，再运行 PP-OCR。
              </span>
            </span>
          </label>
        </div>

        <div
          v-if="isScanEngineUnavailable"
          class="alert alert-warning mt-2"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
          <span class="text-sm">
            Docling 未安装。请在下方"后端管理"中安装。
          </span>
        </div>
      </div>
    </div>

    <!-- Card 2: Backend Management -->
    <div class="card bg-base-100 border border-base-300 shadow-md">
      <div class="card-body">
        <h3 class="card-title text-base">后端管理</h3>
        <p class="text-sm text-base-content/60">
          安装和管理可选的文档提取后端。
        </p>

        <div
          v-for="backend in backends"
          :key="backend.key"
          class="border border-base-300 rounded-lg p-4"
        >
          <div class="flex items-start justify-between gap-4">
            <!-- Left: info -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-medium">{{ backend.displayName }}</span>
                <span
                  v-if="
                    pluginStatuses[backend.key]?.installed &&
                    pluginStatuses[backend.key]?.version
                  "
                  class="badge badge-success badge-xs"
                >
                  v{{ pluginStatuses[backend.key]?.version }}
                </span>
                <span
                  v-else-if="
                    installingPackage === backend.pipName
                  "
                  class="badge badge-info badge-xs"
                >
                  安装中...
                </span>
                <span v-else class="badge badge-warning badge-xs">
                  未安装
                </span>
              </div>
              <p class="text-sm text-base-content/60 mt-1">
                {{ backend.description }}
              </p>
              <!-- Progress bar during installation -->
              <div
                v-if="installingPackage === backend.pipName"
                class="mt-2"
              >
                <progress
                  class="progress progress-primary w-56"
                  :max="100"
                  :value="80"
                ></progress>
                <p class="text-xs text-base-content/50 mt-1">
                  {{ installProgress ?? "准备中..." }}
                </p>
              </div>
            </div>

            <!-- Right: actions -->
            <div class="flex items-center gap-2 shrink-0">
              <template v-if="pluginStatuses[backend.key]?.installed">
                <!-- Docling: pre-download models button -->
                <button
                  v-if="backend.key === 'docling'"
                  class="btn btn-ghost btn-xs"
                  :disabled="installingPackage !== null"
                  @click="doPreDownloadDocling()"
                >
                  下载模型
                </button>
                <button
                  v-if="uninstallConfirm !== backend.key"
                  class="btn btn-ghost btn-xs"
                  @click="requestUninstall(backend.key)"
                >
                  卸载
                </button>
                <button
                  v-else
                  class="btn btn-error btn-xs"
                  @click="confirmUninstall(backend.key)"
                >
                  确认卸载?
                </button>
              </template>
              <template v-else>
                <button
                  class="btn btn-primary btn-xs"
                  :disabled="
                    installingPackage !== null ||
                    uninstallingPackage !== null
                  "
                  @click="requestInstall(backend)"
                >
                  安装
                </button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Install confirm dialog -->
    <dialog
      v-if="showInstallDialog && installTarget"
      class="modal"
      :open="showInstallDialog"
    >
      <div class="modal-box">
        <h3 class="font-bold text-lg">
          安装 {{ installTarget.displayName }}？
        </h3>
        <p class="py-4">{{ installTarget.description }}</p>
        <div class="space-y-1 text-sm">
          <p>
            预计磁盘占用：
            <span class="font-medium">{{
              installTarget.diskEstimate
            }}</span>
          </p>
          <p class="text-base-content/60">
            {{ installTarget.networkNote }}
          </p>
        </div>
        <div class="modal-action">
          <button
            class="btn btn-ghost btn-sm"
            @click="showInstallDialog = false"
          >
            取消
          </button>
          <button class="btn btn-primary btn-sm" @click="confirmInstall">
            安装
          </button>
        </div>
      </div>
      <form method="dialog" class="modal-backdrop">
        <button @click="showInstallDialog = false">close</button>
      </form>
    </dialog>

    <!-- Card 3: Environment Settings -->
    <div class="card bg-base-100 border border-base-300 shadow-md">
      <div class="card-body">
        <h3 class="card-title text-base">环境设置</h3>
        <p class="text-sm text-base-content/60">
          配置可选后端的运行环境。
        </p>

        <!-- Java Path -->
        <div class="form-control w-full max-w-xl">
          <label class="label">
            <span class="label-text font-medium">java.exe 路径</span>
            <span class="label-text-alt text-base-content/50">
              opendataloader-pdf 所需
            </span>
          </label>
          <div class="flex items-center gap-2">
            <input
              v-model="manualJavaPath"
              type="text"
              placeholder="自动检测或手动指定"
              class="input input-bordered input-sm flex-1"
            />
            <button
              class="btn btn-ghost btn-sm"
              @click="handlePickJavaPath"
            >
              浏览
            </button>
            <button
              class="btn btn-ghost btn-sm"
              :disabled="isDetectingJava"
              @click="runDetectJava()"
            >
              <span
                v-if="isDetectingJava"
                class="loading loading-spinner loading-xs"
              ></span>
              检测
            </button>
          </div>
          <!-- Detection result -->
          <label v-if="javaResult" class="label">
            <span v-if="javaResult?.found" class="label-text-alt text-success break-all">
              Java {{ javaResult?.version }}
              <span class="opacity-70" :title="javaResult?.path">{{ javaResult?.path }}</span>
            </span>
            <span v-else class="label-text-alt text-error">
              {{ javaResult?.error ?? "未检测到 Java 11+" }}
              -- 请从
              <a
                href="https://adoptium.net/"
                target="_blank"
                rel="noopener"
                class="link link-primary"
              >
                Adoptium
              </a>
              安装
            </span>
          </label>
        </div>

        <!-- Docling Model Directory -->
        <div class="form-control w-full max-w-xl mt-2">
          <label class="label">
            <span class="label-text font-medium">
              Docling 模型目录
            </span>
            <span class="label-text-alt text-base-content/50">
              可选
            </span>
          </label>
          <div class="flex items-center gap-2">
            <input
              v-model="doclingArtifactsPath"
              type="text"
              placeholder="data\docling（默认）"
              class="input input-bordered input-sm flex-1"
            />
            <button
              class="btn btn-ghost btn-sm"
              @click="handlePickDoclingArtifacts"
            >
              Browse
            </button>
            <button
              v-if="doclingArtifactsPath"
              class="btn btn-ghost btn-xs"
              @click="doclingArtifactsPath = ''"
            >
              重置
            </button>
          </div>
          <label class="label">
            <span class="label-text-alt text-base-content/50 break-all">
              留空则使用默认目录 (data\docling)。点击"下载模型"可将模型下载到指定目录。
            </span>
          </label>
        </div>

        <!-- Destroy venv -->
        <div class="divider text-xs">维护</div>
        <div class="flex items-center justify-between">
          <div>
            <span class="text-sm font-medium">销毁插件虚拟环境</span>
            <p class="text-xs text-base-content/50">
              删除所有已安装的插件后端，释放磁盘空间。
            </p>
          </div>
          <button
            v-if="!showDestroyConfirm"
            class="btn btn-error btn-xs"
            @click="showDestroyConfirm = true"
          >
            销毁
          </button>
          <div v-else class="flex items-center gap-2">
            <button
              class="btn btn-ghost btn-xs"
              @click="showDestroyConfirm = false"
            >
              取消
            </button>
            <button
              class="btn btn-error btn-xs"
              @click="handleDestroyVenv"
            >
              确认销毁
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
