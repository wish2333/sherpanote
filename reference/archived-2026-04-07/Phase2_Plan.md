│ SherpaNote Phase 2 实施计划：前端核心页面与组件                                                                      │
│                                                                                                                      │
│ Context                                                                                                              │
│                                                                                                                      │
│ SherpaNote 项目已完成 Phase 0（基础设施）和 Phase 1（Python 后端），所有 17 个 Bridge 端点和 6                       │
│ 种事件推送均已就绪。前端已有 4 个视图桩文件、bridge 通信层、类型定义、路由和样式。现在需要进入 Phase                 │
│ 2，构建完整可用的前端 UI。                                                                                           │
│                                                                                                                      │
│ 核心目标：将视图中的内联逻辑提取为 composables 和                                                                    │
│ components，增强现有视图功能（删除、拖拽导入、音频播放同步、版本历史等），遵循 MVP 原则。                            │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 实施步骤（共 18 步，分 3 个子阶段）                                                                                  │
│                                                                                                                      │
│ Phase 2A：基础设施层（Composables + Store 扩展）                                                                     │
│                                                                                                                      │
│ Step 1. 扩展 appStore                                                                                                │
│ - 文件：frontend/src/stores/appStore.ts                                                                              │
│ - 改动：增加 toast 通知系统（message + type + 3秒自动消失）和 activeSegmentIndex 状态                                │
│ - 依赖：无                                                                                                           │
│                                                                                                                      │
│ Step 2. 创建 useStorage composable                                                                                   │
│ - 新建：frontend/src/composables/useStorage.ts（~120行）                                                             │
│ - 封装所有数据 CRUD 的 Bridge 调用：loadRecords, getRecord, saveRecord, deleteRecord, searchRecords, getVersions,    │
│ restoreVersion, exportRecord                                                                                         │
│ - 依赖：Step 1                                                                                                       │
│                                                                                                                      │
│ Step 3. 创建 useRecording composable                                                                                 │
│ - 新建：frontend/src/composables/useRecording.ts（~150行）                                                           │
│ - 从 RecordView 提取录音逻辑：麦克风权限、AudioContext、ScriptProcessorNode、Base64 编码、计时器                     │
│ - 依赖：无                                                                                                           │
│                                                                                                                      │
│ Step 4. 创建 useTranscript composable                                                                                │
│ - 新建：frontend/src/composables/useTranscript.ts（~100行）                                                          │
│ - 封装转写数据管理：partial_result/final_result 事件监听、segments 列表、文件转写进度                                │
│ - 依赖：无                                                                                                           │
│                                                                                                                      │
│ Step 5. 创建 useAiProcess composable                                                                                 │
│ - 新建：frontend/src/composables/useAiProcess.ts（~80行）                                                            │
│ - 从 EditorView 提取 AI 处理逻辑：流式接收 ai_token/ai_complete 事件、结果状态管理                                   │
│ - 依赖：无                                                                                                           │
│                                                                                                                      │
│ Phase 2B：可复用组件                                                                                                 │
│                                                                                                                      │
│ Step 6. ThemeToggle.vue（~50行）                                                                                     │
│ - 新建：frontend/src/components/ThemeToggle.vue                                                                      │
│ - 从 App.vue 提取主题切换按钮（sun/moon SVG + store.toggleDarkMode）                                                 │
│                                                                                                                      │
│ Step 7. RecordCard.vue（~70行）                                                                                      │
│ - 新建：frontend/src/components/RecordCard.vue                                                                       │
│ - 从 HomeView 提取稿件卡片（标题、时长、时间、分类 badge、AI badge、删除按钮）                                       │
│ - Props：record: TranscriptRecord; Emits：click, delete                                                              │
│                                                                                                                      │
│ Step 8. SearchBar.vue（~80行）                                                                                       │
│ - 新建：frontend/src/components/SearchBar.vue                                                                        │
│ - 从 HomeView 提取搜索栏，增加分类筛选下拉                                                                           │
│ - 内置 300ms 防抖                                                                                                    │
│                                                                                                                      │
│ Step 9. AudioRecorder.vue（~100行）                                                                                  │
│ - 新建：frontend/src/components/AudioRecorder.vue                                                                    │
│ - 录音控制面板（开始/停止按钮、录音指示器、计时器、文件上传）                                                        │
│ - 使用 useRecording composable                                                                                       │
│                                                                                                                      │
│ Step 10. TranscriptPanel.vue（~80行）                                                                                │
│ - 新建：frontend/src/components/TranscriptPanel.vue                                                                  │
│ - 实时转写显示面板（已确认文本 + partial 灰色斜体 + 自动滚动）                                                       │
│ - Props：segments, partialText, showTimestamps                                                                       │
│                                                                                                                      │
│ Step 11. AiProcessor.vue（~150行）                                                                                   │
│ - 新建：frontend/src/components/AiProcessor.vue                                                                      │
│ - AI 处理面板（4种模式选择、流式渲染、已保存结果列表、复制按钮、基础 Markdown 渲染）                                 │
│ - 使用 useAiProcess composable                                                                                       │
│                                                                                                                      │
│ Step 12. ExportMenu.vue（~60行）                                                                                     │
│ - 新建：frontend/src/components/ExportMenu.vue                                                                       │
│ - 导出下拉菜单（md/txt/docx/srt 4种格式 + loading 状态）                                                             │
│ - 使用 useStorage composable                                                                                         │
│                                                                                                                      │
│ Step 13. VersionHistory.vue（~120行）                                                                                │
│ - 新建：frontend/src/components/VersionHistory.vue                                                                   │
│ - 版本历史侧边栏（版本列表、当前版本高亮、回退确认对话框）                                                           │
│ - 使用 useStorage composable                                                                                         │
│                                                                                                                      │
│ Phase 2C：视图重构与增强                                                                                             │
│                                                                                                                      │
│ Step 14. 修改 App.vue                                                                                                │
│ - 使用 ThemeToggle 组件替换内联主题切换代码                                                                          │
│ - 增加 toast 通知容器                                                                                                │
│                                                                                                                      │
│ Step 15. 重构 HomeView                                                                                               │
│ - 使用 SearchBar + RecordCard + useStorage 重构                                                                      │
│ - 增加删除确认（DaisyUI modal）、拖拽导入、分类筛选                                                                  │
│                                                                                                                      │
│ Step 16. 重构 RecordView                                                                                             │
│ - 使用 AudioRecorder + TranscriptPanel + useRecording + useTranscript 重构                                           │
│ - 支持从 HomeView 拖拽导入文件（通过 route query ?file=xxx）                                                         │
│                                                                                                                      │
│ Step 17. 重构 EditorView（最复杂）                                                                                   │
│ - 使用 AiProcessor + ExportMenu + VersionHistory 重构                                                                │
│ - 增加音频播放器（HTML5 audio + 自定义控制条）                                                                       │
│ - 增加 segment 点击跳转和播放高亮同步                                                                                │
│ - 增加标题可编辑                                                                                                     │
│                                                                                                                      │
│ Step 18. 增强 SettingsView                                                                                           │
│ - 增加 ASR 配置区域（模型目录、语言选择、GPU 开关）                                                                  │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 关键文件清单                                                                                                         │
│                                                                                                                      │
│ 新建文件（13个）                                                                                                     │
│                                                                                                                      │
│ frontend/src/composables/useStorage.ts                                                                               │
│ frontend/src/composables/useRecording.ts                                                                             │
│ frontend/src/composables/useTranscript.ts                                                                            │
│ frontend/src/composables/useAiProcess.ts                                                                             │
│ frontend/src/components/ThemeToggle.vue                                                                              │
│ frontend/src/components/RecordCard.vue                                                                               │
│ frontend/src/components/SearchBar.vue                                                                                │
│ frontend/src/components/AudioRecorder.vue                                                                            │
│ frontend/src/components/TranscriptPanel.vue                                                                          │
│ frontend/src/components/AiProcessor.vue                                                                              │
│ frontend/src/components/ExportMenu.vue                                                                               │
│ frontend/src/components/VersionHistory.vue                                                                           │
│                                                                                                                      │
│ 修改文件（6个）                                                                                                      │
│                                                                                                                      │
│ frontend/src/stores/appStore.ts                                                                                      │
│ frontend/src/App.vue                                                                                                 │
│ frontend/src/views/HomeView.vue                                                                                      │
│ frontend/src/views/RecordView.vue                                                                                    │
│ frontend/src/views/EditorView.vue                                                                                    │
│ frontend/src/views/SettingsView.vue                                                                                  │
│                                                                                                                      │
│ 无需修改（保持现状）                                                                                                 │
│                                                                                                                      │
│ frontend/src/main.ts                                                                                                 │
│ frontend/src/bridge.ts                                                                                               │
│ frontend/src/types/index.ts                                                                                          │
│ frontend/src/router/index.ts                                                                                         │
│ frontend/src/styles/main.css                                                                                         │
│ frontend/src/env.d.ts                                                                                                │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 依赖关系                                                                                                             │
│                                                                                                                      │
│ Step 1 (appStore)                                                                                                    │
│   |                                                                                                                  │
│   v                                                                                                                  │
│ Step 2 (useStorage) -- Step 3 (useRecording) -- Step 4 (useTranscript) -- Step 5 (useAiProcess)                      │
│   |                           |                          |                          |                                │
│   v                           v                          v                          v                                │
│ Step 6 (ThemeToggle)    Step 9 (AudioRecorder)     Step 10 (TranscriptPanel)    Step 11 (AiProcessor)                │
│ Step 7 (RecordCard)                                                                  Step 12 (ExportMenu)            │
│ Step 8 (SearchBar)                                                                   Step 13 (VersionHistory)        │
│   |                           |                          |                          |                                │
│   +---------------------------+--------------------------+--------------------------+                                │
│                                               |                                                                      │
│                                               v                                                                      │
│                               Step 14-18 (Views 重构)                                                                │
│                                                                                                                      │
│ 并行策略：                                                                                                           │
│ - Step 2-5 可并行开发（无相互依赖）                                                                                  │
│ - Step 6-8 可并行开发                                                                                                │
│ - Step 9-13 可并行开发（各自依赖对应的 composable）                                                                  │
│ - Step 14 在 Step 6 后可开始                                                                                         │
│ - Step 15-18 需等待对应组件完成                                                                                      │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 手动测试指南                                                                                                         │
│                                                                                                                      │
│ HomeView                                                                                                             │
│                                                                                                                      │
│ - 页面加载显示记录列表                                                                                               │
│ - 搜索框 300ms 防抖正常                                                                                              │
│ - 分类筛选正常过滤                                                                                                   │
│ - 点击卡片跳转到编辑器                                                                                               │
│ - 删除记录弹出确认框                                                                                                 │
│ - 拖拽音频文件触发转写                                                                                               │
│ - 空状态提示正常                                                                                                     │
│                                                                                                                      │
│ RecordView                                                                                                           │
│                                                                                                                      │
│ - 开始录音请求麦克风权限                                                                                             │
│ - 录音中显示计时器和 partial 文本                                                                                    │
│ - 停止录音后保存并跳转编辑器                                                                                         │
│ - 上传文件后进度条正常                                                                                               │
│ - 页面关闭时自动停止录音                                                                                             │
│                                                                                                                      │
│ EditorView                                                                                                           │
│                                                                                                                      │
│ - 加载记录数据正确                                                                                                   │
│ - 编辑后 2 秒自动保存                                                                                                │
│ - AI 流式输出正常显示                                                                                                │
│ - AI 结果保存到已保存列表                                                                                            │
│ - 导出 4 种格式正常                                                                                                  │
│ - 版本历史显示和回退正常                                                                                             │
│ - 音频播放和 segment 同步正常                                                                                        │
│                                                                                                                      │
│ SettingsView                                                                                                         │
│                                                                                                                      │
│ - AI 和 ASR 配置正常加载和保存                                                                                       │
│ - 重启后配置已持久化                                                                                                 │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 风险                                                                                                                 │
│                                                                                                                      │
│ ┌───────────────────────────────────────────┬────────┬──────────────────────────────────────────┐                    │
│ │                   风险                    │  等级  │                   缓解                   │                    │
│ ├───────────────────────────────────────────┼────────┼──────────────────────────────────────────┤                    │
│ │ pywebview 中 ScriptProcessorNode 兼容性   │ MEDIUM │ 增加 feature detection，不支持时显示提示 │                    │
│ ├───────────────────────────────────────────┼────────┼──────────────────────────────────────────┤                    │
│ │ HTML5 drag/drop 在 pywebview 中可能不触发 │ MEDIUM │ 优先使用 Bridge.get_dropped_files()      │                    │
│ ├───────────────────────────────────────────┼────────┼──────────────────────────────────────────┤                    │
│ │ 音频同步在流式录音中无精确时间戳          │ LOW    │ 只在文件转写 segment 上启用跳转          │                    │
│ └───────────────────────────────────────────┴────────┴──────────────────────────────────────────┘  