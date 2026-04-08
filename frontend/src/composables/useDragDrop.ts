/**
 * useDragDrop - Drag-and-drop composable with flicker prevention.
 *
 * Solves three problems:
 * 1. Drag overlay flickers when cursor moves between child elements
 *    (solved via drag counter instead of boolean flag).
 * 2. pywebview passes unhandled drops to the OS default handler
 *    (solved via window-level event prevention).
 * 3. Browser File API only exposes filenames, not full OS paths.
 *    (solved via pywebvue's get_dropped_files() backend API which
 *    reads pywebviewFullPath from native drop events).
 */
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { call } from "../bridge";

export function useDragDrop(onFilePathDrop?: (filePath: string) => void) {
  const dragCounter = ref(0);
  const isDraggingOver = computed(() => dragCounter.value > 0);

  function onDragEnter(e: DragEvent) {
    e.preventDefault();
    dragCounter.value += 1;
  }

  function onDragLeave(e: DragEvent) {
    e.preventDefault();
    dragCounter.value -= 1;
  }

  function onDragOver(e: DragEvent) {
    e.preventDefault();
  }

  async function onDrop(e: DragEvent) {
    e.preventDefault();
    dragCounter.value = 0;

    if (!onFilePathDrop) return;

    // Wait briefly for pywebvue's native drop handler to capture the paths.
    await new Promise((r) => setTimeout(r, 150));

    // Retrieve real OS file paths from the backend.
    const res = await call<string[]>("get_dropped_files");
    if (res.success && res.data && res.data.length > 0) {
      onFilePathDrop(res.data[0]);
    }
  }

  // Window-level handlers to prevent pywebview from opening files
  // in the default browser when drop is not handled.
  function onWindowDragOver(e: DragEvent) {
    if (e.dataTransfer?.types.includes("Files")) {
      e.preventDefault();
    }
  }

  function onWindowDrop(e: DragEvent) {
    if (e.dataTransfer?.types.includes("Files")) {
      e.preventDefault();
    }
  }

  onMounted(() => {
    window.addEventListener("dragover", onWindowDragOver as EventListener);
    window.addEventListener("drop", onWindowDrop as EventListener);
  });

  onBeforeUnmount(() => {
    window.removeEventListener("dragover", onWindowDragOver as EventListener);
    window.removeEventListener("drop", onWindowDrop as EventListener);
  });

  return {
    isDraggingOver,
    onDragEnter,
    onDragLeave,
    onDragOver,
    onDrop,
  };
}
