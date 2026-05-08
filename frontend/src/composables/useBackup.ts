/** Composable for backup export/import operations. */

import { ref } from "vue";
import { call, pickDirectory, pickFile, exportBackup, importBackup } from "../bridge";
import { useAppStore } from "../stores/appStore";
import type { BackupOptions, BackupSummary } from "../bridge";

export function useBackup(onImportSuccess?: () => void) {
  const store = useAppStore();

  const backupOptions = ref<BackupOptions>({
    include_config: false,
    include_presets: true,
    include_records: true,
    include_versions: true,
    include_audio: false,
  });
  const isExporting = ref(false);
  const isImporting = ref(false);
  const importResult = ref<BackupSummary | null>(null);
  const importConfirmOpen = ref(false);
  const pendingImportPath = ref<string | null>(null);

  async function handleExport() {
    const res = await pickDirectory();
    if (!res.success || !res.data) return;

    const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const filename = `sherpanote_backup_${timestamp}.zip`;
    const outputPath = `${res.data.path}/${filename}`;

    isExporting.value = true;
    try {
      const result = await exportBackup(outputPath, backupOptions.value);
      if (result.success) {
        store.showToast("Backup exported successfully", "success");
      } else {
        store.showToast(result.error || "Export failed", "error");
      }
    } catch {
      store.showToast("Export failed", "error");
    } finally {
      isExporting.value = false;
    }
  }

  async function handlePickImportFile() {
    const res = await pickFile(["ZIP Files (*.zip)"]);
    if (!res.success || !res.data) return;
    pendingImportPath.value = res.data.path;
    importConfirmOpen.value = true;
  }

  async function confirmImport() {
    if (!pendingImportPath.value) return;
    isImporting.value = true;
    importConfirmOpen.value = false;
    try {
      const result = await importBackup(pendingImportPath.value);
      if (result.success && result.data) {
        importResult.value = result.data;
        store.showToast("Backup imported successfully. Reloading page...", "success");
        const configRes = await call<Record<string, unknown>>("get_config");
        if (configRes.success && configRes.data) {
          const cfg = configRes.data as Record<string, unknown>;
          if (cfg.ai) {
            const ai = cfg.ai as Record<string, unknown>;
            store.aiConfig = {
              provider: (ai.provider as string) ?? "openai",
              model: (ai.model as string) ?? "gpt-4o-mini",
              api_key: (ai.api_key as string | null) ?? null,
              base_url: (ai.base_url as string | null) ?? null,
              temperature: (ai.temperature as number) ?? 0.7,
              max_tokens: (ai.max_tokens as number) ?? 8192,
            };
          }
          if (cfg.asr) {
            const asr = cfg.asr as Record<string, unknown>;
            store.asrConfig = {
              ...store.asrConfig,
              ...Object.fromEntries(Object.entries(asr).filter(([, v]) => v !== undefined)),
            } as typeof store.asrConfig;
          }
          store.autoAiModes = (cfg.auto_ai_modes as string[]) ?? [];
        }
        onImportSuccess?.();
      } else {
        store.showToast(result.error || "Import failed", "error");
      }
    } catch {
      store.showToast("Import failed", "error");
    } finally {
      isImporting.value = false;
      pendingImportPath.value = null;
    }
  }

  function cancelImport() {
    importConfirmOpen.value = false;
    pendingImportPath.value = null;
  }

  return {
    backupOptions,
    isExporting,
    isImporting,
    importResult,
    importConfirmOpen,
    pendingImportPath,
    handleExport,
    handlePickImportFile,
    confirmImport,
    cancelImport,
  };
}
