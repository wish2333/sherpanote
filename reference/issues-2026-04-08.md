## 2026.04.08 11-30

### 问题

- 在音频管理器进行的转录过程中如果切到其他界面会导致记录无法正确保存
- 需要添加多套API预设的保存方案，方便用户切换（多个提供商、多模型的切换，如多个OPENAI format提供商、Openrouter等多模型提供商）
- 现在转录出来的内容没有标点符号，这是可以优化的吗
- 添加AI处理预设管理（名称、提示词、默认行为、组合处理一键导出等）
- version history好像没有实际功能
- export左边那个AI选项好像没有实际功能

### 修改后问题

- API添加预设没有测试连接的功能
- 记录中AI处理的选项没有实现可以预设（设置界面中也没有相关内容）
- 设置中没有关于AI处理默认行为（如转录完成后立刻进行某项或某些项对应AI处理等）的设置
- 记录中没有对AI-API预设的选择；没有对AI处理生成的内容进行持久化的前端界面和后端功能

### 修改内容

  1. API预设测试连接

  - 后端 main.py: 新增 test_ai_preset_connection(preset_id=None, config=None) 端点，支持按预设ID或内联配置测试连接
  - 前端 SettingsView.vue: 预设创建/编辑表单内新增 "Test" 按钮，测试结果显示在表单中

  2. AI处理预设管理（Settings界面）

  - 前端 SettingsView.vue: 新增 "Processing" 选项卡，包含完整的CRUD界面：
    - 列表展示所有预设（内置/自定义标签区分）
    - 新建/编辑表单（名称、模式、提示词模板textarea）
    - 内置预设不可删除，自定义预设可编辑/删除
    - {text} 占位符提示

  3. 转录后自动AI处理

  - 后端 config.py: AppConfig 新增 auto_ai_modes: tuple[str, ...] 字段
  - 后端 main.py: 新增 _auto_process_record() 方法，在 import_and_transcribe
    保存记录后自动按序执行选中的AI处理模式，通过 auto_ai_progress / auto_ai_complete 事件推送进度
  - 前端 SettingsView.vue: ASR选项卡中新增 "Auto AI Processing" 多选区域（Polish/Notes/Mind Map/Brainstorm
    复选框），切换即时保存

  4. 记录中AI预设选择和结果持久化

  - 前端 AiProcessor.vue: 完整重写
    - 新增 AI Provider 下拉选择器：展示所有API预设，点击切换活跃预设
    - 新增 Processing Preset 下拉选择器：内置/自定义分组展示
    - 已保存结果列表增加 删除按钮，可逐个删除已保存的AI结果
    - 结果数量 badge 展示
    - 所有操作都有明确的反馈

● 修复完成。问题原因：PyWebVue 桥接不支持 None 作为可选位置参数传入——JS 端传 null 作为第一个参数时，桥接无法正确匹配
  Python 方法签名。

  - 后端 main.py: 将 test_ai_preset_connection(self, preset_id: str = None, config: dict = None) 改为
    test_ai_preset_connection(self, config: dict)，只接收一个必需的 config 字典参数
  - 前端 SettingsView.vue: 将 call("test_ai_preset_connection", null, config) 改为 call("test_ai_preset_connection",
    config)

### 修改后问题-2

- AI结果保存的位置应该和Transcript的框一样大在它下面，因为可能有很多Results，所以应该需要可以这些，Transcript框也需要可折叠。现在显示Results的地方可以改成Results的导航。而且Results需要可以删除
- 还需要注意切割的问题。看看怎么设计能够让输出防止被最大输出的上下文框截断。

### 修改内容

  1. EditorView 布局重构

  - 垂直布局：音频播放器、内容区域上下堆叠
  - 左右分栏：左侧 1/4 宽度是 AI 控制面板（预设选择 + 已保存结果导航），右侧 3/4 宽度是内容区
  - 内容区 Tab 切换：Transcript / AI Result 两个 tab，互相切换
  - Transcript 可折叠：点击标题栏可折叠/展开，折叠时显示 3 行预览；展开时有 Segments 子折叠区 + textarea
  - AI Result 全尺寸展示：与 Transcript 区域同等大小，最大高度 70vh 可滚动，顶部有 Save/Copy/Map 按钮
  - Audio 播放器也可折叠

  2. AiProcessor 改为导航/控制面板

  - 精简为紧凑的控制面板：API 预设下拉 + 处理预设下拉 + 模式按钮 + Process 按钮
  - Saved Results 变为导航列表：点击某条结果会在右侧内容区全尺寸展示
  - 每条结果有删除按钮
  - 流式处理中的截断检测和警告提示

  3. 输出截断防护 (llm.py)

  - _estimate_max_tokens() 方法：根据输入文本长度动态估算合理的 max_tokens
    - 短文本 (<500字): 输出约 4x 输入
    - 中等文本 (500-5000字): 输出约 2x 输入
    - 长文本 (>5000字): 输出约 1.2x 输入
    - 下限 1024，上限为用户配置值
  - finish_reason 检测：流式输出时检查每个 chunk 的 finish_reason，如果是 "length" 则标记为截断
  - 后端在 ai_complete 事件中附带 truncated: true/false
  - 前端在结果区域显示橙色 "Truncated" 标签并弹出 toast 提醒

### 修改后问题-3

- AI处理Result的命名应该是预设名称而非custom
- 前端报错
- 内容区排版有问题，宽度太窄了。而且转录结果不应该和AI Results切换，转录结果和 可切换的AI results应当在排版上上下排列
- 截断检测和警告之后能否有让AI继续输出的解决方案？
- AIPROCESSING这个选择框里面，关于AI处理模式的选择逻辑有点乱，用户是应该在下拉框还是点击按钮切换呢（我建议点击按钮切换）而且这一栏的字体和宽度都有点小了，看着不太舒服，

### 修改总结

● All 4 tasks are complete. Here's a summary of the changes:

  1. TypeScript build errors (11 fixed)

  - Removed unused imports (AiMode, AiProcessingPreset) from appStore.ts, EditorView.vue, SettingsView.vue,
    useAiProcess.ts
  - Removed invalid "custom" mode from AI_MODES in useAiProcess.ts
  - Converted offToken/offAiComplete/offAiError from unused const to proper cleanup-managed variables with
    setupAiListeners() pattern
  - Removed unused onResultSaved function
  - Fixed is_active type error in SettingsView.vue with Record<string, unknown> cast
  - Fixed unused customPrompt variable in AiProcessor.vue

  2. AI result naming uses preset name

  - AiProcessor.vue: displayModes now uses preset_{id} as mode key when a processing preset is selected
  - Added getResultLabel() to show preset name (not raw key) in the saved results list
  - customPrompt is now passed through emit("process", mode, presetId, customPrompt) and forwarded to the backend
  - AiResults type changed from Partial<Record<AiMode, string>> to Record<string, string> to support arbitrary preset
    keys

  3. Layout restructured

  - Changed from grid-cols-4 (1/4 + 3/4) to grid-cols-5 (1/5 + 4/5) for wider content area
  - Removed tab switching between Transcript/AI Result
  - Transcript and AI Result are now vertically stacked - Transcript always visible (collapsible), AI Result appears
    below when active
  - Transcript textarea reduced to min-h-[30vh], AI Result area min-h-[40vh]

  4. "Continue" output for truncated results

  - Backend (llm.py): Added continue_stream() method that sends the previous output as context with a "continue from
    where you left off" instruction
  - Backend (main.py): Added continue_text_stream exposed endpoint, emits ai_continue_complete event
  - Frontend (EditorView.vue): Added handleContinueOutput() function, ai_continue_complete event listener that appends
    continuation to existing content, and a "Continue" button (warning style) shown only when truncationWarning is true

  Manual test items

  - Open editor view, verify transcript and AI result stack vertically
  - Collapse/expand transcript
  - Run an AI processing with a built-in mode, verify result saves with correct mode name
  - Select a processing preset, run it, verify result saves with preset_ prefixed key and shows preset name in
    navigation
  - Test truncation: use a low max_tokens setting, process a long text, verify "Truncated" badge and "Continue" button
    appear
  - Click "Continue", verify output appends and badge updates
  - Click "Continue" again if still truncated, verify it works repeatedly

● Build passes. Two fixes applied:

  1. Nested button warning - Changed the Transcript collapsible header from <button> to <div role="button"
    class="cursor-pointer">. The copy button inside is now a proper child of a div instead of a nested button.
  2. Width too narrow - Changed grid from grid-cols-5 (1/5 + 4/5) to grid-cols-6 with explicit lg:col-span-1 (sidebar)
    and lg:col-span-5 (content). The sidebar now takes ~17% width and the content area takes ~83%, giving substantially
    more room to Transcript and AI Result panels.

### 修改后bug

我发现results的命名仍然不太对，比如我在设置添加了一个新预设名为“123”，result命名却是preset_xxx，应该是123_xxx。此外  ，如果文本太长，AI处理报错（或者不是因为太长而是自动检测字数却错误计算token导致输出超过max-token？），而且过程中没有进行流式传输。又测试了一下长文本，中间出现了两次上下文超标，能否优化检测和max_token设置，让上下文不至于那么容易超标，现在很多模型的max_token都大雨4096了。既然我们现在支持过长的任务继续功能了，应该在设置界面添加一个选项，让自动识别max_token功能可以开关。

我还发现多段生成的AI Results没有真正持久化，前端刷新或切换界面之后不见了。

### 修改总结

  1. Result 命名修复
  - mode key 格式从 preset_{uuid} 改为 {presetName}_preset_{uuid}
  - 例如预设 "123" 处理后，result key 为 123_preset_abc123，导航列表中显示 123
  - getResultLabel 通过 _preset_ 分隔符提取用户可见的名称部分
  - 内置模式 (polish/note/mindmap/brainstorm) 不受影响，仍然是原始 key

  2. 流式传输修复
  - process_text_stream 和 continue_text_stream 都改为在后台线程中运行流式循环
  - @expose 方法立即返回 {"status": "streaming"}，不阻塞主线程
  - 后台线程中的 on_token 回调通过 _emit("ai_token") 推送 token，主线程空闲时可以正常投递事件到前端
  - 这与 transcribe_file 等其他流式操作的模式一致

● Build passes.总结修复内容：

  1. Continue 输出重复 bug (关键)
  - 根因：ai_token 事件在流式传输时已经通过 accumulatedText += text 更新了 currentResultContent
  - 然后 ai_continue_complete 又执行了 currentResultContent.value += detail.result，导致新内容被追加了两次
  - 修复：ai_continue_complete handler 中不再 append detail.result，仅处理截断状态判断

  2. max_tokens 默认值提升
  - 后端 AiConfig 默认 max_tokens: 4096 -> 8192
  - 前端 appStore 默认: 4096 -> 8192
  - test_ai_preset_connection fallback: 4096 -> 8192
  - set_active_ai_preset fallback: 4096 -> 8192

  3. Token 估算优化
  - 中文文本 1 字符约 1.5 token，之前的乘数没有考虑这点
  - 短文本 (<500): 3x -> 中等 (500-3000): 2x -> 长文本 (3000-10000): 1.5x -> 超长 (>10000): 1x
  - 下限从 1024 提升到 2048，避免极短输出

  4. Continue 的 max_tokens 修复
  - 之前 continue_stream 用 min(configured_max, len(previous_output)) 计算长度，会随输出长度增长
  - 改为直接使用 self._config.max_tokens，确保续写有足够空间

  5. GeneratorExit 噪音抑制
  - process_stream 和 continue_stream 的流式循环加 try/finally + stream.close()
  - 正常关闭流，避免垃圾回收时触发 GeneratorExit 日志

● Build passes.改动总结：

  后端
  - AppConfig 新增 auto_max_tokens: bool = True 字段，支持序列化/反序列化
  - AIProcessor.__init__ 新增 auto_max_tokens 参数
  - _estimate_max_tokens 新增 auto: bool 参数，auto=False 时直接返回 configured_max，跳过估算
  - _get_ai() 创建处理器时传入 self._config.auto_max_tokens

  前端
  - AppSettings 类型新增 auto_max_tokens: boolean
  - SettingsView 新增 autoMaxTokens 状态，loadConfig/saveConfig 传递该字段
  - AI 设置选项卡 Temperature 下方新增 toggle 开关：
    - Auto Max Tokens - 开启时根据输入长度自动估算 max_tokens（适合一般使用）
    - 关闭时直接使用模型配置的完整 max_tokens 值（适合长文本需要完整输出的场景）

  1.   Max Tokens 三选项 - 从 join 按钮组改为 radio + label 列表布局：

       - 每个选项是一个 <label> 包裹 radio + 文字区域
       - Radio 使用 DaisyUI radio-primary radio-sm
       - 每个选项有 标题 (Auto / Fixed / Model Default) 和 描述行 (Estimate based on input length / Use the value below / No
         limit, let model decide)
       - 选中状态通过 :checked 绑定

       Custom 数值输入 - 仅在 mode 为 custom 时显示，可编辑 max_tokens 值。

     ● 改动：

       - 滑块尺寸 - range-primary -> range-primary range-xs，更细的滑条
       - 布局 - 把 Precise / 滑条 / Creative 放进同一行 label > flex，用 shrink-0 固定两端文字宽度（w-12），滑条 flex-1
         自动撑满中间
       - 对齐 - Precise 左对齐 text-left，Creative 右对齐 text-right，两端文字与滑条起始/结束位置对齐

     ● Build passes. 回应你的后续消息 -- 我检查了完整链路：

       后端 - 存储/读取都没问题：_row_to_dict 会把 ai_results_json 字段解析为 ai_results 对象，save_record 会把 ai_results
       序列化写回。

       根因在前端：AI 处理完成后（包括 continue），结果只存在 currentResultContent 这个响应式变量里。只有用户手动点击 Save
       按钮才会调用 save_record 持久化。如果用户刷新或切换界面，这些内存中的数据就丢失了。

       修复：提取了 persistResult 公共函数，在 ai_complete 和 ai_continue_complete 事件回调结束时自动调用
       autoSaveResult()，处理完成即自动写入数据库。手动 Save 按钮仍保留，用于用户想确认保存的场景。

### 问题

记录的Version History好像仍然没有用啊，这个能否修复，在软件退出时自动保存修改了的记录多一个版本（最多记录可以在Setting中设置0），并添加一个按钮（需要比复制按钮大有“保存版本”字样）在记录内的Transcript部分。

### 修改总结

  每次自动保存（编辑时每2秒一次）时都会创建一个版本，这会导致版本历史记录变得嘈杂。实际上，Version History
  特性被大量自动生成的版本所破坏。

  后端 (py/storage.py)

  - 移除了 save() 中所有自动创建版本的逻辑——现在 save() 仅对 records 表执行 CRUD 操作，完全不会触及 versions 表
  - 新增 _get_current_version(record_id) ——从 versions 表中获取最高版本号
  - 新增 create_version(record_id, max_versions) ——为记录的当前状态创建一个版本快照，可选择修剪超过 max_versions
    的旧版本
  - 新增 _prune_versions(record_id, max_versions) ——删除超过限制的最旧版本（0 = 不限制）

  后端 (main.py)

  - 新增 _dirty_record_ids 集合，用于跟踪未保存修改的记录
  - 新增 save_version(record_id) API ——显式创建版本，将记录标记为干净
  - 新增 mark_dirty(record_id) / mark_clean(record_id) API ——在前端和后端之间通信脏状态
  - 新增 atexit 处理程序，用于在应用退出时自动保存脏记录的版本

  前端 (useStorage.ts)

  - 新增 saveVersion(recordId) 函数

  前端 (EditorView.vue)

  - 新增 "Save Version" 按钮（btn-primary btn-sm，带有 save 图标和文本）在 Transcript 区域 header，右键位于复制按钮旁
  - 新增 isDirty 跟踪 ——每次编辑时都会设置
  - 新增 handleSaveVersion() ——显式创建版本，显示 toast 通知，并刷新计数
  - 新增 refreshVersionCount() ——在版本创建后正确刷新 badge
  - 新增 对 onBeforeUnmount 的 auto-save ——如果记录是脏的，在导航离开时自动保存一个版本
  - 修复 versionCount 追踪 ——不再在每个自动保存时虚假地增加计数

  前端 (SettingsView.vue)

  - 新增 "Max Version History" 数字输入 (0 = unlimited, default 20) 在 ASR 选项卡中
  - 与 update_config 集成用于加载/保存

  Manual Test Items

  1. 在一个记录中编辑 transcript ——验证在版本历史面板中不会自动创建版本
  2. 点击 "Save Version" 按钮 ——验证 toast 显示版本号，badge 更新，版本出现在历史记录中
  3. 在 Settings > ASR Engine 中更改 "Max Version History" 为 3，然后保存多个版本 ——验证旧版本被自动删除
  4. 编辑一个记录，然后导航回主页 ——验证自动保存一个版本 (检查版本历史面板)
  5. 编辑一个记录，然后关闭应用程序 ——验证在退出时保存了一个版本 (通过重新打开并检查版本历史)
  6. 将 "Max Version History" 设置为 0 ——验证可以创建无限数量的版本

### 修改后问题

  1.点击Save Version之后，Version History那里的Current仍是旧版本的，应该切换为新版本。
  2.此外，记录需要有删除功能
  3.而且Max Version History应当在一个General（新增放在Setting各项最左边）页面设置而不是Asr。
  4.还有！现在没有修改而切换界面也会自动保存一个新版本，这不对，没哟修改不要保存新版本
  5.记录里的左侧版本、AI等功能栏太窄了，应当与右边的文字栏，1:2比例即可
  6.复制按钮和Save Version按钮位置互换

> 还有一个大问题，current仍然错误标识，导致不应该有的版本保存。
> 首先，点进一个记录时，并没有标识current是哪个版本，这样对比是否修改是怎么对比的，测试中我点进入，输入1，删除1，实际
> 没有修改，退出时却保存了新版本。
> 然后，Restore之后Current标识没有改变到Restore的版本处，退出时保存了新版本
> 还有，Save Version按钮处的current切换虽然有效且正确，但是如果在打开了History列表时点击Save
> Version，列表没有实时修改，需要重新打开列表才会刷新。

### 修改总结

  1. Version History "current" badge not updating after Save Version

    - EditorView.vue:430-432 -- handleSaveVersion() 现在更新 record.value = { ...record.value, version: ver }，这样
  VersionHistory 组件接收到新版本，并且“current” 徽章会正确地高亮显示。
  2. Max Version History 移至 General 标签

    - SettingsView.vue:35 -- 标签类型现在包含 "general"
    - SettingsView.vue:505-530 -- 添加了 "General" 作为最左侧的选项卡
    - SettingsView.vue:540-569 -- 新的 "General" 部分包含版本历史设置，并带有 "Save" 按钮
    - 从 "ASR Engine" 部分移除了 max_versions 输入
3. 无修改时不应自动保存版本

    - EditorView.vue:146 -- 添加了 isInitialLoad 防护标志
    - EditorView.vue:150 -- 在 loadRecord() 中，在设置 editorText 之前设置为 true
    - EditorView.vue:165 -- 在 nextTick 之后设置为 false，以避免 watcher 触发
    - EditorView.vue:183 -- watcher 在 isInitialLoad 为 true 时提前返回，防止假阳性脏标记
4. 左侧面板比例调整 (1:2)

    - EditorView.vue:700 -- 将 lg:grid-cols-5 改为 lg:grid-cols-3，并将列范围从 1/4 改为 1/2，实现 1:2 的比例
5. 按钮位置互换

    - EditorView.vue:705-728 -- "Save Version" 按钮现在在 "Copy" 按钮之前

  - 添加了 storage.delete_version(record_id, version) 后端方法
  - 添加了 delete_version API 端点到 main.py
  - 添加了 deleteVersion(recordId, version) 到 useStorage.ts
  - 更新了 VersionHistory.vue：每个版本条目右侧现在有 Restore 和 Delete (红色垃圾桶图标) 两个按钮，Delete
      会直接删除该版本并刷新列表
  - EditorView 监听 deleted 事件以刷新版本计数 badge

  1. 脏检测改为内容对比（修复"无修改也保存版本"）

  - 移除了 isDirty 布尔值，改为 lastVersionContent 字符串
  - loadRecord() 初始化 lastVersionContent = transcript
  - handleSaveVersion() 保存后更新 lastVersionContent = editorText
  - onVersionRestored() 恢复后更新 lastVersionContent = transcript
  - onBeforeUnmount 比较 editorText !== lastVersionContent，而非布尔值
  - mark_dirty / mark_clean 也基于内容对比，输入再删除回来会正确 mark_clean

  2. Restore 后 current 正确更新（修复"恢复后退出又保存新版本"）

  - main.py:restore_version 现在在恢复内容后调用 storage.create_version()，创建一个新的版本快照
  - 返回 record["version"] = new_ver，前端拿到正确的 current 版本号
  - 前端 onVersionRestored 同步更新 lastVersionContent，退出时不会误判为脏

  3. VersionHistory 列表实时刷新（修复"打开 History 时点 Save Version 不更新列表"）

  - VersionHistory 组件绑定 :key="'vh-' + versionCount"
  - 每次 saveVersion 或 deleteVersion 后 versionCount 变化，组件自动重新挂载并重新加载数据

## 2026.04.08 09-00

### 问题

-  重新转录按钮应该在点进某个Record之后的界面里，且现在还没有绑定上转录功能
-  音频播放功能尚未实现
-  点进某条Record之后的界面里，Transcript框添加一个一键复制按钮
-  Records中删除某条之后音频文件未删除，不知道数据库清理没有。点击删除之后，音频文件默认不清除，数据库默认要清除。想要添加一个音频文件管理页面（标记清楚是否仍有Record）
-  开启麦克风录制之后或上传文件之后，切换界面的话，回到Record界面又回到初始状态了。希望禁止切换界面或者切换界面后保持Record界面状态
- 不同模型可能运行方式有差别：
  -  如果运行sherpa-onnx-paraformer-zh-small-2024-03-09，可以正常运转；如果运行sherpa-onnx-paraformer-trilingual-zh-cantonese-en，报错如下：
    09:14:32 [INFO] pywebvue.bridge: execute_task: executing task c21ba1c3-80e2-48db-ba54-d70b337d1819 (command: create_offline_recognizer, args: None) 09:14:32 [INFO] py.asr: Using SenseVoice offline model 09:14:33 [ERROR] pywebvue.bridge: _execute_task: task c21ba1c3-80e2-48db-ba54-d70b337d1819 failed: Failed to load model because protobuf parsing failed. Traceback (most recent call last): File "Q:\Git\GiteaManager\sherpanote\pywebvue\bridge.py", line 126, in execute_task result = self.dispatch_task(command, args) File "Q:\Git\GiteaManager\sherpanote\main.py", line 96, in dispatch_task recognizer = self._asr._create_offline_recognizer(_sherpa, model_dir) File "Q:\Git\GiteaManager\sherpanote\py\asr.py", line 517, in _create_offline_recognizer return sherpa_onnx.OfflineRecognizer.from_sense_voice( File "Q:\Git\GiteaManager\sherpanote.venv\lib\site-packages\sherpa_onnx\offline_recognizer.py", line 299, in from_sense_voice self.recognizer = _Recognizer(recognizer_config) RuntimeError: Failed to load model because protobuf parsing failed. 09:14:33 [INFO] pywebvue.bridge: Task c21ba1c3-80e2-48db-ba54-d70b337d1819 completed: success=False 09:14:33 [INFO] pywebvue.bridge: Cleaned up pending result for task c21ba1c3-80e2-48db-ba54-d70b337d1819 09:14:33 [ERROR] **main**: transcribe_file failed: Task 'create_offline_recognizer' failed: Failed to load model because protobuf parsing failed. Traceback (most recent call last): File "Q:\Git\GiteaManager\sherpanote\main.py", line 232, in _work self.run_on_main_thread("create_offline_recognizer", timeout=60.0) File "Q:\Git\GiteaManager\sherpanote\pywebvue\bridge.py", line 193, in run_on_main_thread raise RuntimeError(f"Task '{command}' failed: {result}") RuntimeError: Task 'create_offline_recognizer' failed: Failed to load model because protobuf parsing failed.
-  重新转录按钮点击后无反应，且会删除标题、断开记录与音频的链接
-  未连接音频的Transcript框可修改，实时转录的不可修改但可跳转
-  文件转录时没有前端提示或进度条
-  文件上传的记录和通过音频管理界面转录的记录也有重新识别按钮，这个不需要。而且Records界面也不需要重新识别按钮，只在录制记录里显示就行了
-  完成重新转录之后，进度条和100%转圈圈没有消失
-  希望上传的文件也能被管理，也就是新加一种上传方式（旧的方式也需要保留），识别的流程是先复制到data/audio中然后进行和重转录一样的流程
-  data目录下的data.db-wal在删了记录之后会更大，这个是什么文件，这个现象是否有问题

### 解决方案

-  重新转录按钮添加到EditorView，实现handleRetranscribe函数和事件监听器
-  修复音频播放问题，使用base64数据URL替代file://协议
-  在转录标题旁添加复制按钮，支持clipboard API回退
-  创建AudioManageView显示音频文件列表，实现删除时只清除音频链接而非整个记录
-  添加导航守卫，录制时禁止切换页面
-  修复三语Paraformer模型崩溃问题，改进模型检测逻辑
-  添加完整日志记录追踪转录过程
-  为实时转录文本添加可编辑框，确保传入AI的是可修改框内容
-  添加转录过程页面切换提示
-  限制重新转录仅在麦克风录制记录中显示
-  修复转录完成后进度条不消失的问题
-  新增import_and_transcribe功能，复制文件到data/audio目录后进行转录
-  data.db-wal是SQLite的WAL(Write-Ahead Logging)文件，是正常机制，无需担心