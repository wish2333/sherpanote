<script setup lang="ts">
/**
 * App.vue - Root layout with navbar and toast notifications.
 *
 * Uses ThemeToggle component and renders toast container.
 */
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAppStore } from "./stores/appStore";
import { waitForPyWebView } from "./bridge";
import ThemeToggle from "./components/ThemeToggle.vue";

const store = useAppStore();
const router = useRouter();

onMounted(async () => {
  store.applyTheme();

  try {
    await waitForPyWebView();
    store.ready = true;
  } catch {
    store.ready = false;
  }
});
</script>

<template>
  <!-- Top navigation bar -->
  <div class="navbar bg-base-100 border-b border-base-300 px-4">
    <!-- Left: logo + navigation -->
    <div class="navbar-start gap-2">
      <a class="text-xl font-bold tracking-tight text-base-content" @click="router.push('/')">
        SherpaNote
      </a>
      <ul class="menu menu-horizontal gap-1">
        <li>
          <a
            :class="{ 'bg-base-200': $route.path === '/' }"
            @click="router.push('/')"
          >
            <span class="text-sm">Records</span>
          </a>
        </li>
        <li>
          <a
            :class="{ 'bg-base-200': $route.path === '/record' }"
            @click="router.push('/record')"
          >
            <span class="text-sm">Record</span>
          </a>
        </li>
      </ul>
    </div>

    <!-- Right: status + actions -->
    <div class="navbar-end gap-2">
      <!-- Bridge status indicator -->
      <span
        class="badge badge-sm"
        :class="store.ready ? 'badge-success' : 'badge-warning'"
      >
        {{ store.ready ? "Connected" : "Connecting..." }}
      </span>

      <!-- Theme toggle -->
      <ThemeToggle />

      <!-- Settings -->
      <button class="btn btn-ghost btn-sm btn-circle" @click="router.push('/settings')">
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12.22 2h-.44a2 2 0 00-2 2v.18a2 2 0 01-1 1.73l-.43.25a2 2 0 01-2 0l-.15-.08a2 2 0 00-2.73.73l-.22.38a2 2 0 00.73 2.73l.15.1a2 2 0 011 1.72v.51a2 2 0 01-1 1.74l-.15.09a2 2 0 00-.73 2.73l.22.38a2 2 0 002.73.73l.15-.08a2 2 0 012 0l.43.25a2 2 0 011 1.73V20a2 2 0 002 2h.44a2 2 0 002-2v-.18a2 2 0 011-1.73l.43-.25a2 2 0 012 0l.15.08a2 2 0 002.73-.73l.22-.39a2 2 0 00-.73-2.73l-.15-.08a2 2 0 01-1-1.74v-.5a2 2 0 011-1.74l.15-.09a2 2 0 00.73-2.73l-.22-.38a2 2 0 00-2.73-.73l-.15.08a2 2 0 01-2 0l-.43-.25a2 2 0 01-1-1.73V4a2 2 0 00-2-2z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      </button>
    </div>
  </div>

  <!-- Page content -->
  <main class="min-h-[calc(100vh-56px)] bg-base-100">
    <router-view />
  </main>

  <!-- Toast notifications -->
  <div class="toast toast-top toast-end z-50">
    <div
      v-for="toast in store.toasts"
      :key="toast.id"
      class="alert max-w-sm shadow-lg"
      :class="{
        'alert-success': toast.type === 'success',
        'alert-error': toast.type === 'error',
        'alert-warning': toast.type === 'warning',
        'alert-info': toast.type === 'info',
      }"
    >
      <span class="text-sm">{{ toast.message }}</span>
    </div>
  </div>
</template>
