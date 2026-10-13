# 使用说明：图片批量处理器（v1.1）

## 1. 环境要求

- Python **3.9 或更高版本**（开发测试环境为 3.13）
- 依赖库：**Pillow**（唯一的第三方依赖）

## 2. 安装步骤（本地 Windows）

如果你本地还没有 Python 环境，三选一：

1. **官网安装包**（推荐）：访问 [python.org](https://www.python.org/downloads/) 下载 Windows installer，安装时**务必勾选 “Add Python to PATH”**
2. **Microsoft Store**：商店搜索 “Python 3.12” 一键安装
3. **命令行**：`winget install Python.Python.3.12`

然后安装依赖（二选一）：

```bash
# 方式一：用 requirements.txt（推荐，把该文件放在 image_processor.py 同目录）
pip install -r requirements.txt

# 方式二：直接装
pip install Pillow
```

## 3. 快速开始

把 `image_processor.py` 放到任意目录，打开命令行（cmd / PowerShell / Git Bash），执行：

```bash
python image_processor.py --input "D:\你的图片文件夹"
```

处理完成后，图片会出现在 **与被处理文件夹同级的 `processed` 文件夹**里：

```
D:\你的图片文件夹\            <- 原始图片（不会被改动）
D:\processed\                <- 处理后的图片（自动创建）
```

## 4. 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `--input` | 是 | — | 待处理的图片文件夹路径 |
| `--width` | 否 | `800` | 目标宽度（px），高度按比例自动计算 |
| `--format` | 否 | `webp` | 输出格式：`webp` 或 `jpg` |
| `--quality` | 否 | `80` | 压缩质量 1–95，越大越清晰、体积越大 |
| `--no-upscale` | 否 | 关 | 已小于目标宽度的图片**不放大**，保持原尺寸，仅转换格式 |
| `--recursive` | 否 | 关 | **递归处理子文件夹**，输出保持原有目录结构 |

常用示例：

```bash
# 默认：800px 宽，转 webp，质量 80
python image_processor.py --input "D:\商品图"

# 1200px 宽，转 jpg，质量 85（适合上传不支持 webp 的老系统）
python image_processor.py --input "D:\商品图" --width 1200 --format jpg --quality 85

# 小图不放大（400px 的图保持 400px，不会被强行拉到 800px 变糊）
python image_processor.py --input "D:\商品图" --no-upscale

# 连同子文件夹一起处理，processed 里保持同样的目录结构
python image_processor.py --input "D:\商品图" --recursive

# 组合使用
python image_processor.py --input "D:\商品图" --recursive --no-upscale
```

## 5. 支持的输入格式

jpg / jpeg / png / webp / bmp / gif / tif / tiff（大小写不敏感，如 `.JPG` 也能识别）。

## 6. 内置特性（帮你避坑）

- **EXIF 方向自动纠正**：手机竖拍照片带旋转信息，不处理的话缩放后会“躺倒”，脚本已自动扶正
- **透明 PNG 转 JPG 自动铺白底**：JPEG 不支持透明通道，直接转黑色背景会很难看；转 webp 则完整保留透明
- **小图不放大（--no-upscale）**：默认按“统一宽度”策略会把小图也拉到目标宽度（会变糊）；加这个参数后只缩不放
- **递归子文件夹（--recursive）**：`input/子目录/a.jpg` 会输出为 `processed/子目录/a.webp`，目录结构原样保留；重复运行时不会把上次的输出再处理一遍
- **GIF 只取第一帧**：第一版不做动图
- **单张失败不中断**：某张图损坏/打不开时，跳过它继续处理其余的，最后汇总失败清单
- **同名文件不互相覆盖**：同一文件夹里 `a.jpg` 和 `a.png` 都会转成 `a.webp` 时，第二个自动命名 `a_1.webp`
- **不改动原图**：只读取源文件夹，输出全部写到 `processed`

## 7. 实测数据（2026-10-13，工作区内实测）

测试图：2400px 横版大图、2400px 竖拍图（EXIF）、1600px 透明 PNG、400px 小图、子文件夹 1920px 商品图、子文件夹 500px 小图，共 6 张。

| 场景 | 总体积变化 | 说明 |
|---|---|---|
| webp / 800px / 质量80 / 递归+不放大 | 508.4KB → 65.7KB（**-87.1%**） | 2 张小图保持原尺寸 |
| webp / 800px / 质量80（v1.0 默认行为） | 352.8KB → 54.9KB（**-84.4%**） | 全部拉到 800px |
| jpg / 800px / 质量85 | 352.8KB → 94.5KB（**-73.2%**） | 透明 PNG 正确铺白底 |

校验结论：输出宽度精确 800px（不放大模式的图除外）、比例保持、EXIF 竖图方向正确、透明通道完整保留、子文件夹结构镜像、损坏文件被优雅跳过。

## 8. 常见问题

**Q：默认会把小图放大吗？**
会。默认执行 README 定义的“统一缩放为固定宽度”，400px 的图也会拉到 800px（画质变糊）。不想放大就加 `--no-upscale`。

**Q：--recursive 会处理多深？**
无限层级。`processed` 里会镜像出相同的目录结构。输出目录自身会被自动跳过，重复运行不会污染。

**Q：重复运行会怎样？**
直接覆盖 `processed` 里的旧文件，不会累积垃圾。想重新来就先删掉 `processed` 文件夹。

**Q：webp 兼容性？**
微信、淘宝、抖音、小红书等主流平台均已支持 webp。如果遇到不支持的场景，用 `--format jpg` 即可。

**Q：质量参数怎么选？**
商品主图建议 80–85；细节要求高的（服装面料等）用 90；缩略图/预览图 70 也够。

**Q：运行报错 `No module named PIL`？**
说明 Pillow 没装上，执行 `pip install Pillow`；如果装了还报错，检查 Python 和 pip 是否是同一个环境（常见于装了多个 Python 版本）。

## 9. 自己复现测试（可选）

```bash
python make_test_images.py   # 生成 6 张测试图（含子文件夹）到 test_images/
python image_processor.py --input test_images --recursive --no-upscale
python verify_output.py      # 自动校验尺寸/格式/透明通道/EXIF/目录结构
```
