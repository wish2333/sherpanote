import { createRouter, createWebHashHistory } from "vue-router";
import { useAppStore } from "../stores/appStore";

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("../views/HomeView.vue"),
    },
    {
      path: "/record",
      name: "record",
      component: () => import("../views/RecordView.vue"),
    },
    {
      path: "/editor/:id",
      name: "editor",
      component: () => import("../views/EditorView.vue"),
      props: true,
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("../views/SettingsView.vue"),
    },
    {
      path: "/audio",
      name: "audio",
      component: () => import("../views/AudioManageView.vue"),
    },
  ],
});

// Block navigation while recording is active to prevent state loss.
router.beforeEach((_to, _from, next) => {
  const store = useAppStore();
  if (store.isRecording) {
    store.showToast("Cannot navigate while recording is in progress", "warning");
    next(false);
  } else {
    next();
  }
});

export default router;
