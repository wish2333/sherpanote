/**
 * useStorage - Data CRUD composable wrapping all Bridge storage calls.
 *
 * Provides typed functions for record management, version history,
 * search, and export. All functions return ApiResponse envelopes.
 */
import { ref } from "vue";
import { call } from "../bridge";
import { useAppStore } from "../stores/appStore";
import type {
  TranscriptRecord,
  RecordFilter,
  Version,
  ExportFormat,
} from "../types";

export function useStorage() {
  const store = useAppStore();
  const isLoading = ref(false);

  /** List records with optional filter. */
  async function loadRecords(filter?: RecordFilter): Promise<TranscriptRecord[]> {
    isLoading.value = true;
    try {
      const res = await call<TranscriptRecord[]>("list_records", filter ?? null);
      if (res.success && res.data) {
        store.records = res.data;
        return res.data;
      }
      return [];
    } finally {
      isLoading.value = false;
    }
  }

  /** Fetch a single record by ID. */
  async function getRecord(id: string): Promise<TranscriptRecord | null> {
    isLoading.value = true;
    try {
      const res = await call<TranscriptRecord>("get_record", id);
      if (res.success && res.data) {
        store.currentRecord = res.data;
        return res.data;
      }
      store.showToast(res.error ?? "Failed to load record", "error");
      return null;
    } finally {
      isLoading.value = false;
    }
  }

  /** Create or update a record. Returns the saved record. */
  async function saveRecord(data: Partial<TranscriptRecord> & { id?: string }): Promise<TranscriptRecord | null> {
    const res = await call<TranscriptRecord>("save_record", data);
    if (res.success && res.data) {
      // Refresh the record in store if it matches current.
      if (store.currentRecord && res.data.id === store.currentRecord.id) {
        store.currentRecord = res.data;
      }
      return res.data;
    }
    store.showToast(res.error ?? "Failed to save record", "error");
    return null;
  }

  /** Delete a record by ID. Returns true on success. */
  async function deleteRecord(id: string): Promise<boolean> {
    const res = await call<{ record_id: string }>("delete_record", id);
    if (res.success) {
      store.records = store.records.filter((r) => r.id !== id);
      if (store.currentRecord?.id === id) {
        store.currentRecord = null;
      }
      return true;
    }
    store.showToast(res.error ?? "Failed to delete record", "error");
    return false;
  }

  /** Search records by keyword (title + transcript). */
  async function searchRecords(keyword: string): Promise<TranscriptRecord[]> {
    isLoading.value = true;
    try {
      const res = await call<TranscriptRecord[]>("search_records", keyword);
      if (res.success && res.data) {
        return res.data;
      }
      return [];
    } finally {
      isLoading.value = false;
    }
  }

  /** Get version history for a record. */
  async function getVersions(recordId: string): Promise<Version[]> {
    const res = await call<Version[]>("get_version_history", recordId);
    if (res.success && res.data) {
      return res.data;
    }
    return [];
  }

  /** Restore a record to a specific version. Returns the restored record. */
  async function restoreVersion(
    recordId: string,
    version: number,
  ): Promise<TranscriptRecord | null> {
    const res = await call<TranscriptRecord>("restore_version", recordId, version);
    if (res.success && res.data) {
      if (store.currentRecord?.id === recordId) {
        store.currentRecord = res.data;
      }
      return res.data;
    }
    store.showToast(res.error ?? "Failed to restore version", "error");
    return null;
  }

  /** Create an explicit version snapshot for a record. */
  async function saveVersion(recordId: string): Promise<number | null> {
    const res = await call<{ version: number }>("save_version", recordId);
    if (res.success && res.data) {
      return res.data.version;
    }
    store.showToast(res.error ?? "Failed to save version", "error");
    return null;
  }

  /** Delete a single version from a record's version history. */
  async function deleteVersion(recordId: string, version: number): Promise<boolean> {
    const res = await call<{ version: number }>("delete_version", recordId, version);
    if (res.success) {
      return true;
    }
    store.showToast(res.error ?? "Failed to delete version", "error");
    return false;
  }

  /** Export a record to the given format. Returns the file path. */
  async function exportRecord(
    recordId: string,
    fmt: ExportFormat,
  ): Promise<string | null> {
    const res = await call<{ file_path: string }>("export_record", recordId, fmt);
    if (res.success && res.data) {
      store.showToast(`Exported as .${fmt}`, "success");
      return res.data.file_path;
    }
    store.showToast(res.error ?? "Export failed", "error");
    return null;
  }

  /** Import a text file (.md / .txt) as a new record. Returns the record. */
  async function importRecord(filePath: string): Promise<TranscriptRecord | null> {
    const res = await call<TranscriptRecord>("import_record", filePath);
    if (res.success && res.data) {
      store.showToast("File imported", "success");
      return res.data;
    }
    store.showToast(res.error ?? "Import failed", "error");
    return null;
  }

  return {
    isLoading,
    loadRecords,
    getRecord,
    saveRecord,
    deleteRecord,
    searchRecords,
    getVersions,
    restoreVersion,
    saveVersion,
    deleteVersion,
    exportRecord,
    importRecord,
  };
}
