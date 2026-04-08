## 2026.04.08 09-00

## 问题

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