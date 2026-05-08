/** Composable for version management in the editor. */

import { ref } from "vue";
import { call } from "../bridge";
import { useAppStore } from "../stores/appStore";
import type { TranscriptRecord, Version } from "../types";

export function useVersionManagement(
  recordId: () => string,
  getRecord: () => TranscriptRecord | null,
  setRecord: (r: TranscriptRecord) => void,
  getEditorText: () => string,
  setLastVersionContent: (v: string) => void,
  saveVersion: (id: string) => Promise<number | null>,
) {
  const store = useAppStore();

  const showVersionHistory = ref(false);
  const versionCount = ref(0);
  const isSavingVersion = ref(false);

  async function refreshVersionCount() {
    const verRes = await call<Version[]>("get_version_history", recordId());
    if (verRes.success && Array.isArray(verRes.data)) {
      versionCount.value = verRes.data.length;
    }
  }

  function onVersionRestored(updated: TranscriptRecord) {
    setRecord(updated);
    setLastVersionContent(updated.transcript);
    call("mark_clean", recordId());
    showVersionHistory.value = false;
    refreshVersionCount();
  }

  async function handleSaveVersion() {
    const rec = getRecord();
    if (!rec || isSavingVersion.value) return;
    isSavingVersion.value = true;
    const ver = await saveVersion(rec.id);
    if (ver !== null) {
      setLastVersionContent(getEditorText());
      store.showToast(`Version v${ver} saved`, "success");
      setRecord({ ...rec, version: ver });
      await refreshVersionCount();
    }
    isSavingVersion.value = false;
  }

  return {
    showVersionHistory,
    versionCount,
    isSavingVersion,
    refreshVersionCount,
    onVersionRestored,
    handleSaveVersion,
  };
}
