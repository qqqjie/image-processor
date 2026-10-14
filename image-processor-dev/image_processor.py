#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片批量处理器（v1.2）
功能：
  1. 批量把指定文件夹里的图片统一缩放为固定宽度（默认 800px），保持比例
  2. 批量转换为 .webp / .jpg 并压缩体积
  3. --no-upscale：已小于目标宽度的图片不放大，仅转换格式
  4. --recursive：递归处理子文件夹，输出保持原有目录结构
  5. 批量重命名：--rename-prefix 前缀 + 按序号递增；--replace 替换原名中的特定字符

架构说明：
  process_batch() 是批处理核心，CLI 的 main() 和 Web 界面 app.py 都调用它，
  保证命令行与网页两种入口行为完全一致。

用法：
  python image_processor.py --input "图片文件夹路径" [--width 800] [--format webp|jpg]
                            [--quality 80] [--no-upscale] [--recursive]
                            [--rename-prefix 前缀] [--rename-start N] [--keep-name]
                            [--replace 旧=新] [--replace 旧=新 ...]
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

# 支持的输入图片格式（大小写不敏感）
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="图片批量处理器：批量缩放 + 格式转换(webp/jpg) + 压缩 + 批量重命名",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python image_processor.py --input D:\\photos\n"
            "  python image_processor.py --input D:\\photos --width 1200 --format jpg --quality 85\n"
            "  python image_processor.py --input D:\\photos --no-upscale\n"
            "  python image_processor.py --input D:\\photos --recursive\n"
            "  python image_processor.py --input D:\\photos --rename-prefix product- --rename-start 100\n"
            "  python image_processor.py --input D:\\photos --replace \" =_\" --replace \"（=(\"\n"
        ),
    )
    parser.add_argument("--input", required=True, help="待处理的图片文件夹路径")
    parser.add_argument("--width", type=int, default=800,
                        help="目标宽度(px)，默认 800，高度按比例自动计算")
    parser.add_argument("--format", dest="fmt", choices=["webp", "jpg"], default="webp",
                        help="输出格式，默认 webp")
    parser.add_argument("--quality", type=int, default=80,
                        help="压缩质量 1-95，默认 80")
    parser.add_argument("--no-upscale", action="store_true",
                        help="已小于目标宽度的图片不放大，保持原尺寸，仅转换格式")
    parser.add_argument("--recursive", action="store_true",
                        help="递归处理所有子文件夹，输出保持原有目录结构")
    parser.add_argument("--rename-prefix", default="",
                        help="批量重命名：新文件名 = 前缀 + 序号，如 product-001.webp")
    parser.add_argument("--rename-start", type=int, default=1,
                        help="序号起始值，默认 1")
    parser.add_argument("--keep-name", action="store_true",
                        help="配合 --rename-prefix：保留(替换后的)原名，如 product-001_红色长裙.webp")
    parser.add_argument("--replace", action="append", default=[], metavar="旧=新",
                        help="替换原名中的特定字符，可重复多条，如 --replace \" =_\"")
    args = parser.parse_args()
    if args.width <= 0:
        parser.error("--width 必须是正整数")
    if not (1 <= args.quality <= 95):
        parser.error("--quality 必须在 1-95 之间")
    if args.rename_start < 0:
        parser.error("--rename-start 不能为负数")
    return args


def human_size(num_bytes):
    """把字节数格式化为可读字符串"""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)}B" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def parse_replace_rules(rules):
    """把 ['旧=新', ...] 解析为 [(旧, 新), ...]；格式错误抛出 ValueError"""
    pairs = []
    for rule in rules or []:
        if "=" not in rule:
            raise ValueError(f"替换规则格式错误: '{rule}'，应为 旧=新，例如 --replace \" =_\"")
        old, new = rule.split("=", 1)
        if not old:
            raise ValueError(f"替换规则的“旧”不能为空: '{rule}'")
        pairs.append((old, new))
    return pairs


def build_new_stem(stem: str, seq: int, prefix: str, keep_name: bool,
                   replace_pairs) -> str:
    """按规则生成新文件名主干（不含扩展名）：
    1. 依次应用所有字符替换
    2. 若指定前缀：主干 = 前缀 + 序号（至少3位补零，超过999自动增宽）
    3. 若同时指定 keep-name：再拼接 _替换后的原名
    不传任何重命名参数时原样返回。"""
    for old, new in replace_pairs or []:
        stem = stem.replace(old, new)
    if prefix:
        stem = f"{prefix}{seq:03d}" + (f"_{stem}" if keep_name else "")
    return stem


def process_image(src: Path, dst: Path, width: int, fmt: str, quality: int,
                  no_upscale: bool = False):
    """处理单张图片：EXIF纠正 -> 等比缩放 -> 转换格式压缩保存。
    返回 (原始大小, 输出大小, 是否进行了缩放)"""
    with Image.open(src) as im:
        # 1. 按 EXIF 方向信息纠正旋转（手机竖拍照片的经典坑）
        im = ImageOps.exif_transpose(im)

        # 2. GIF 动图只取第一帧（第一版不做动图）
        if getattr(im, "is_animated", False):
            im.seek(0)

        # 3. 调色板(P)模式统一转换，避免后续保存报错
        if im.mode == "P":
            im = im.convert("RGBA" if "transparency" in im.info else "RGB")

        # 4. 按目标格式处理色彩模式
        if fmt == "jpg":
            # JPEG 不支持透明通道：先铺白底再转 RGB，否则透明区域会变黑
            if im.mode in ("RGBA", "LA"):
                rgba = im.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.getchannel("A"))
                im = background
            elif im.mode != "RGB":
                im = im.convert("RGB")
        else:  # webp 支持透明通道，保留 RGBA
            if im.mode == "LA":
                im = im.convert("RGBA")
            elif im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")

        # 5. 等比缩放：高度 = 原高 x (目标宽 / 原宽)
        #    --no-upscale 时，已不宽于目标的图片保持原尺寸
        w, h = im.size
        resized = True
        if no_upscale and w <= width:
            resized = False
        else:
            new_h = max(1, round(h * width / w))
            im = im.resize((width, new_h), Image.Resampling.LANCZOS)

        # 6. 保存（method=6 为 webp 压缩率最高档）
        if fmt == "jpg":
            im.save(dst, "JPEG", quality=quality, optimize=True)
        else:
            im.save(dst, "WEBP", quality=quality, method=6)

    return src.stat().st_size, dst.stat().st_size, resized


def collect_files(input_dir: Path, output_dir: Path, recursive: bool):
    """收集待处理文件；recursive 时递归子文件夹并排除输出目录自身"""
    if recursive:
        files = [
            p for p in input_dir.rglob("*")
            if p.is_file()
            and p.suffix.lower() in SUPPORTED_EXTS
            and output_dir not in p.parents  # 防止把上一次的输出又处理一遍
        ]
    else:
        files = [
            p for p in input_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        ]
    return sorted(files)


def make_output_path(output_dir: Path, rel: Path, seq: int, prefix: str,
                     keep_name: bool, replace_pairs, out_ext: str,
                     used_names: set) -> Path:
    """按重命名规则生成输出路径，并确保本次批量内不重名"""
    new_stem = build_new_stem(rel.stem, seq, prefix, keep_name, replace_pairs)
    dst = output_dir / rel.with_name(new_stem + out_ext)
    if dst in used_names:
        i = 1
        while dst.with_name(f"{dst.stem}_{i}{out_ext}") in used_names:
            i += 1
        dst = dst.with_name(f"{dst.stem}_{i}{out_ext}")
    used_names.add(dst)
    return dst


def process_batch(input_dir: Path, output_dir: Path, *, width: int = 800,
                  fmt: str = "webp", quality: int = 80, no_upscale: bool = False,
                  recursive: bool = False, prefix: str = "", start: int = 1,
                  keep_name: bool = False, replace_pairs=None,
                  on_event=None):
    """批处理核心：遍历 -> 重命名 -> 处理 -> 统计。
    on_event(row, stats) 为可选回调（CLI 用于打印，Web 用于更新进度条）。
    返回统计 dict：total/success/failed/skipped_scale/total_in/total_out/
    failures[(rel, err)]/rows[每文件明细]"""
    replace_pairs = replace_pairs or []
    files = collect_files(input_dir, output_dir, recursive)
    stats = {"total": len(files), "success": 0, "failed": 0, "skipped_scale": 0,
             "total_in": 0, "total_out": 0, "failures": [], "rows": []}
    if not files:
        return stats

    out_ext = ".webp" if fmt == "webp" else ".jpg"
    used_names = set()
    seq = start  # 序号按文件路径排序依次递增

    for src in files:
        rel = src.relative_to(input_dir)
        dst = make_output_path(output_dir, rel, seq, prefix, keep_name,
                               replace_pairs, out_ext, used_names)
        seq += 1
        dst.parent.mkdir(parents=True, exist_ok=True)

        row = {"rel": str(rel), "dst": str(dst.relative_to(output_dir)),
               "src_size": src.stat().st_size, "dst_size": None,
               "resized": None, "error": None}
        try:
            src_size, dst_size, resized = process_image(
                src, dst, width, fmt, quality, no_upscale)
            row["dst_size"] = dst_size
            row["resized"] = resized
            stats["success"] += 1
            stats["total_in"] += src_size
            stats["total_out"] += dst_size
            if not resized:
                stats["skipped_scale"] += 1
        except Exception as exc:  # 单张失败不中断整体流程
            row["error"] = str(exc)
            stats["failed"] += 1
            stats["failures"].append((str(rel), str(exc)))
        stats["rows"].append(row)
        if on_event:
            on_event(row, stats)

    return stats


def _cli_printer(row, stats):
    """CLI 进度回调：逐文件打印"""
    if row["error"]:
        print(f"[失败] {row['rel']}: {row['error']}")
    else:
        note = "" if row["resized"] else "   (未放大，保持原尺寸)"
        print(f"[成功] {row['rel']}  ->  {row['dst']}   "
              f"{human_size(row['src_size'])} -> {human_size(row['dst_size'])}{note}")


def main():
    args = parse_args()

    try:
        replace_pairs = parse_replace_rules(args.replace)
    except ValueError as exc:
        print(f"[错误] {exc}")
        sys.exit(1)

    input_dir = Path(args.input).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"[错误] 文件夹不存在或不是目录: {input_dir}")
        sys.exit(1)

    # 输出目录：输入目录同级的 processed 文件夹
    output_dir = input_dir.parent / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.rename_prefix:
        rename_desc = f"前缀 {args.rename_prefix} + 序号(起 {args.rename_start})"
        if args.keep_name:
            rename_desc += " + 保留原名"
    elif replace_pairs:
        rename_desc = "字符替换: " + ", ".join(f"{o}->{n}" for o, n in replace_pairs)
    else:
        rename_desc = "关"

    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    print(f"处理参数: 宽度 {args.width}px | 格式 {args.fmt} | 质量 {args.quality}"
          f" | 不放大: {'开' if args.no_upscale else '关'}"
          f" | 递归: {'开' if args.recursive else '关'}"
          f" | 重命名: {rename_desc}")
    print("-" * 60)

    stats = process_batch(
        input_dir, output_dir, width=args.width, fmt=args.fmt,
        quality=args.quality, no_upscale=args.no_upscale,
        recursive=args.recursive, prefix=args.rename_prefix,
        start=args.rename_start, keep_name=args.keep_name,
        replace_pairs=replace_pairs, on_event=_cli_printer)

    print("-" * 60)
    if stats["total"] == 0:
        print(f"[提示] {input_dir} 中没有找到图片文件"
              f"（支持: {', '.join(sorted(SUPPORTED_EXTS))}）")
        sys.exit(0)

    print(f"处理完成: 成功 {stats['success']} 张, 失败 {stats['failed']} 张"
          + (f"（其中 {stats['skipped_scale']} 张未放大）"
             if stats["skipped_scale"] else ""))
    if stats["success"]:
        diff = stats["total_in"] - stats["total_out"]
        if diff >= 0:
            print(f"总体积: {human_size(stats['total_in'])} -> "
                  f"{human_size(stats['total_out'])}"
                  f" (节省 {human_size(diff)}, {diff / stats['total_in'] * 100:.1f}%)")
        else:
            print(f"总体积: {human_size(stats['total_in'])} -> "
                  f"{human_size(stats['total_out'])}"
                  f" (增加 {human_size(-diff)})")

    if stats["failures"]:
        print("\n失败详情:")
        for name, err in stats["failures"]:
            print(f"  - {name}: {err}")

    sys.exit(0 if stats["failed"] == 0 else 2)


if __name__ == "__main__":
    main()
