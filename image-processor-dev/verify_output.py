#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 processed 目录输出：格式、宽度、EXIF竖图比例、透明通道、递归结构、no-upscale"""
import sys
from pathlib import Path
from PIL import Image

BASE = Path(__file__).parent
PROCESSED = BASE / "processed"

# (相对路径, 期望尺寸) —— 按 --recursive --no-upscale 的预期填写
EXPECTED = {
    "photo_landscape.webp": (800, 450),        # 2400x1350 -> 800x450
    "photo_portrait_exif.webp": (800, 1600),   # EXIF旋转后 1200x2400 -> 800x1600
    "logo_transparent.webp": (800, 500),       # 1600x1000 -> 800x500, 保留透明
    "small_icon.webp": (400, 300),             # 400px 小图，--no-upscale 不放大
    "sub_folder/product_a.webp": (800, 450),   # 1920x1080 -> 800x450，目录结构保持
    "sub_folder/deep/thumb.webp": (500, 400),  # 500px 小图，不放大
}

ok = True
for name, (ew, eh) in EXPECTED.items():
    p = PROCESSED / name
    if not p.exists():
        print(f"[缺失] {name}")
        ok = False
        continue
    with Image.open(p) as im:
        w, h = im.size
        fmt, mode = im.format, im.mode
        has_alpha = mode in ("RGBA", "LA") or (mode == "P" and "transparency" in im.info)
    status = "OK" if (w, h) == (ew, eh) else "尺寸不符"
    if (w, h) != (ew, eh):
        ok = False
    print(f"[{status}] {name}: {fmt} {mode} {w}x{h} (期望 {ew}x{eh}) alpha={has_alpha}")

# 透明 PNG 转 webp 后透明区域必须仍是透明的（左上角像素 alpha 应为 0）
with Image.open(PROCESSED / "logo_transparent.webp") as im:
    corner = im.convert("RGBA").getpixel((2, 2))
    print(f"透明PNG角像素: {corner}")
    if corner[3] > 10:
        print("[失败] 透明通道丢失!")
        ok = False
    else:
        print("[OK] 透明通道保留")

# EXIF 竖图必须是竖的（高 > 宽）
with Image.open(PROCESSED / "photo_portrait_exif.webp") as im:
    if im.size[1] > im.size[0]:
        print("[OK] EXIF 竖图方向纠正正确（竖版）")
    else:
        print("[失败] EXIF 方向未纠正")
        ok = False

print("\n总结:", "全部通过" if ok else "存在问题")
sys.exit(0 if ok else 1)
