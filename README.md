# 图片批量处理器 · Image Batch Processor

> 把一堆图片批量缩放、转格式、压缩、重命名——**命令行**和**网页**两种方式都能用，结果完全一致。

## 为什么做这个

电商运营、自媒体、经常整理照片的人，手动用 PS 一张张改太慢。这个工具只要一条命令（或一个网页），就能把整个文件夹处理完：统一宽度、转 webp/jpg、压缩体积、批量改名。

实测 6 张图：**508.4KB → 65.7KB，体积省了 87.1%**。

## 功能特性

- **批量缩放**：统一宽度（默认 800px），高度按比例自动计算
- **格式转换与压缩**：输出 webp 或 jpg，质量可调（1–95）
- **小图不放大**（`--no-upscale`）：保护画质，避免小图被拉糊
- **递归处理子文件夹**：保留原始目录结构
- **批量重命名**：前缀 + 序号、保留原名、字符替换
- **EXIF 方向自动纠正**：手机竖拍照片不会"躺倒"
- **透明 PNG 转 JPG 自动铺白底**：转 webp 则完整保留透明通道
- **健壮处理**：单张失败不中断、同名文件不互相覆盖、绝不改动原图

## 安装

需要 **Python 3.9 或更高版本**。

```bash
git clone https://github.com/qqqjie/image-processor.git
cd image-processor/image-processor-dev
```

命令行版依赖（只需 Pillow）：

```bash
pip install -r requirements.txt
```

网页版依赖（Streamlit）：

```bash
pip install -r requirements-web.txt
```

> 建议使用虚拟环境隔离依赖：
> ```bash
> python -m venv .venv
> .\.venv\Scripts\activate        # Windows
> source .venv/bin/activate       # macOS / Linux
> pip install -r requirements-web.txt
> ```

## 使用

### 方式一：命令行

```bash
# 默认：800px 宽、转 webp、质量 80，递归处理子文件夹
python image_processor.py --input "D:\你的图片文件夹" --recursive

# 批量重命名：product-001.webp、product-002.webp ...
python image_processor.py --input "D:\商品图" --rename-prefix "product-" --keep-name
```

处理后的图片会生成在**与源文件夹同级的 `processed` 目录**中，原图不会被改动。

### 方式二：网页界面（推荐给不熟悉命令行的用户）

```bash
streamlit run app.py
```

浏览器自动打开 http://localhost:8501，操作如下：

- **上传**：多选图片，或把整个文件夹打成 zip 上传（推荐，保留目录结构）
- **勾选参数**：目标宽度、输出格式、质量、小图不放大、递归子文件夹
- **批量重命名**：前缀、起始序号、保留原名、字符替换（每行一条 `旧=新`）
- **一键下载**：处理完成后直接下载 `processed.zip`

> 网页界面与命令行**共用同一套处理核心**（`process_batch` 函数），两种入口结果完全一致。zip 解压带防目录穿越（Zip Slip）保护，所有处理都在本机完成，不上传任何数据到第三方。

## 效果对比（实测数据）

| 场景 | 体积变化 |
| --- | --- |
| webp / 800px / 质量 80 / 递归 + 不放大 | 508.4KB → 65.7KB（**-87.1%**） |
| jpg / 800px / 质量 85 | 352.8KB → 94.5KB（**-73.2%**） |

## 目录结构

```
image-processor/
├── README.md                    # 你正在看的这份
└── image-processor-dev/
    ├── image_processor.py       # 核心处理逻辑 + 命令行入口
    ├── app.py                   # Streamlit 网页界面
    ├── requirements.txt         # 命令行版依赖（Pillow）
    ├── requirements-web.txt     # 网页版依赖（Streamlit + Pillow + pandas）
    ├── make_test_images.py      # 生成 6 张测试图（含子文件夹）
    ├── verify_output.py         # 输出自动校验
    ├── test_web_app.py          # 网页版单元测试
    └── USAGE.md                 # 完整使用文档：参数表 / 重命名规则 / 常见问题
```

## 文档

完整参数说明、重命名规则详解、常见问题（FAQ）见 **[USAGE.md](image-processor-dev/USAGE.md)**。

## 技术栈

Python 3.13（开发环境）· [Pillow](https://python-pillow.org/) · [Streamlit](https://streamlit.io/)
