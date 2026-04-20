准备开发2.0.0版本，新增界面与功能：OCR。选型：RapidOCR>3.8.0+OnnxRuntime+本地模型（可选PP-OCRv5和PP-OCRv4，从https://www.modelscope.cn/models/RapidAI/RapidOCR/tree/master/onnx下载）
相关信息：

- 需要使用的包：rapidocr onnxruntime（已手动安装）

- 具体模型名称(具体把准确文件下载到`软件目录/data/rapidocr/`，不要下多下错)

  - v4
    - cls: ch_ppocr_mobile_v2.0_cls_mobile.onnx
    - det: ch_PP-OCRv4_det_server.onnx
    - rec: ch_PP-OCRv4_rec_server.onnx
  - v5
    - cls: ch_PP-LCNet_x1_0_textline_ori_cls_server.onnx
    - det: ch_PP-OCRv5_det_server.onnx
    - rec: ch_PP-OCRv5_rec_server.onnx

- 本地模型指定方式

  - 下面以通过初始化参数传入为例：

    ```python
    from rapidocr import RapidOCR
    engine = RapidOCR(params={"Det.model_path": "models/ch_PP-OCRv4_det_infer.onnx"} ) 
    img_url = "https://img1.baidu.com/it/u=3619974146,1266987475&fm=253&fmt=auto&app=138&f=JPEG?w=500&h=516"
    result = engine(img_url)
    print(result)
    result.vis("vis_result.jpg") 
    ```

    上面第 4 行通过 `Det.model_path` 指定了本地已经下载好的文本检测模型。文本方向分类和文本识别模型也可同样指定。(`Cls.model_path` 和 `Rec.model_path` 同理)

  - 其他参数设置

    ```
    from rapidocr_onnxruntime import RapidOCR
    
    # 自定义配置
    ocr = RapidOCR(
        det_model_path='models/det_model.onnx',      # 检测模型路径
        rec_model_path='models/rec_model.onnx',      # 识别模型路径
        cls_model_path='models/cls_model.onnx',      # 分类模型路径
        det_thresh=0.5,                               # 检测阈值
        rec_batch_num=6,                              # 识别批处理大小
        use_cuda=False,                               # 是否使用GPU
        engine_type='onnxruntime'                     # 推理引擎类型
    )
    ```

- 功能需求
  - 在主页添加一个单独的view，设置界面也添加一个单独的设置
  - 用户可以上传图片、多张图片（两种模式：单独批处理生成多个记录or按照顺序处理生成一个记录）、PDF（每页形成一张图片后再按照顺序处理生成一个记录）。
  - 上传与处理中间可以通过文件列表显示，再点击处理才处理
  - 与当前记录系统及界面兼容