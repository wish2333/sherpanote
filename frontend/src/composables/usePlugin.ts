import { ref, onUnmounted, type Ref } from "vue";
import {
  getPluginStatus,
  installPlugin,
  uninstallPlugin,
  destroyPluginVenv,
  preDownloadDocling,
  detectJava,
  getAvailableBackends,
  onEvent,
} from "../bridge";
import type { PluginPackageStatus, JavaDetectionResult } from "../types";

export interface UsePluginReturn {
  pluginStatuses: Ref<Record<string, PluginPackageStatus>>;
  availableBackends: Ref<Record<string, boolean>>;
  javaResult: Ref<JavaDetectionResult | null>;
  installingPackage: Ref<string | null>;
  installProgress: Ref<string | null>;
  uninstallingPackage: Ref<string | null>;
  isDetectingJava: Ref<boolean>;
  lastError: Ref<string | null>;
  loadStatuses: () => Promise<void>;
  doInstall: (name: string) => void;
  doUninstall: (name: string) => Promise<void>;
  doDestroyVenv: () => Promise<void>;
  doPreDownloadDocling: () => void;
  runDetectJava: () => Promise<void>;
}

export function usePlugin(): UsePluginReturn {
  const pluginStatuses = ref<Record<string, PluginPackageStatus>>({});
  const availableBackends = ref<Record<string, boolean>>({});
  const javaResult = ref<JavaDetectionResult | null>(null);
  const installingPackage = ref<string | null>(null);
  const installProgress = ref<string | null>(null);
  const uninstallingPackage = ref<string | null>(null);
  const isDetectingJava = ref(false);
  const lastError = ref<string | null>(null);

  const offProgress = onEvent<{ message: string }>(
    "plugin_install_progress",
    (detail) => {
      installProgress.value = detail.message;
    },
  );

  const offComplete = onEvent<{ name: string; version: string }>(
    "plugin_install_complete",
    () => {
      installingPackage.value = null;
      installProgress.value = null;
      loadStatuses();
    },
  );

  const offError = onEvent<{ name: string; error: string }>(
    "plugin_install_error",
    (detail) => {
      installingPackage.value = null;
      installProgress.value = null;
      const msg = detail.error ?? "Unknown error";
      const isNetworkError =
        /timeout|connection|resolve|network|offline/i.test(msg);
      if (isNetworkError) {
        lastError.value =
          "Install failed: network unavailable. Plugin installation requires an internet connection.";
      } else {
        lastError.value = `Install failed: ${msg}`;
      }
    },
  );

  onUnmounted(() => {
    offProgress();
    offComplete();
    offError();
  });

  async function loadStatuses(): Promise<void> {
    const [statusRes, backendRes] = await Promise.all([
      getPluginStatus(),
      getAvailableBackends(),
    ]);
    if (statusRes.success && statusRes.data) {
      const map: Record<string, PluginPackageStatus> = {};
      for (const [key, val] of Object.entries(statusRes.data)) {
        map[key] = {
          name: key,
          installed: val.installed,
          version: val.version,
        };
      }
      pluginStatuses.value = map;
    }
    if (backendRes.success && backendRes.data) {
      availableBackends.value = backendRes.data;
    }
  }

  function doInstall(name: string): void {
    if (installingPackage.value) return;
    installingPackage.value = name;
    installProgress.value = null;
    lastError.value = null;
    installPlugin(name);
  }

  async function doUninstall(name: string): Promise<void> {
    if (uninstallingPackage.value) return;
    uninstallingPackage.value = name;
    try {
      const res = await uninstallPlugin(name);
      if (res.success) {
        await loadStatuses();
      } else {
        lastError.value = res.error ?? "Uninstall failed";
      }
    } finally {
      uninstallingPackage.value = null;
    }
  }

  function doPreDownloadDocling(): void {
    if (installingPackage.value) return;
    installingPackage.value = "docling-models";
    installProgress.value = null;
    lastError.value = null;
    preDownloadDocling();
  }

  async function doDestroyVenv(): Promise<void> {
    const res = await destroyPluginVenv();
    if (res.success) {
      pluginStatuses.value = {};
      availableBackends.value = {};
      lastError.value = null;
    } else {
      lastError.value = res.error ?? "Destroy failed";
    }
  }

  async function runDetectJava(): Promise<void> {
    isDetectingJava.value = true;
    try {
      const res = await detectJava();
      if (res.success && res.data) {
        javaResult.value = res.data;
      } else {
        javaResult.value = {
          found: false,
          path: null,
          version: null,
          error: res.error ?? "Detection failed",
        };
      }
    } catch {
      javaResult.value = {
        found: false,
        path: null,
        version: null,
        error: "Detection failed",
      };
    } finally {
      isDetectingJava.value = false;
    }
  }

  return {
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
  };
}
