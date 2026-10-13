#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成测试图片：大图、EXIF竖拍图、透明PNG、小图、子文件夹图片，用于验证 image_processor.py"""
import random
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).parent / "test_images"
OUT.mkdir(exist_ok=True)
random.seed(42)


def gradient_with_shapes(size, name, exif_orientation=None, subdir=None):
    """生成带渐变和随机色块的测试图"""
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for x in range(w):
        c = int(255 * x / w)
        d.line([(x, 0), (x, h)], fill=(c, 120, 255 - c))
    for _ in range(25):
        cx, cy = random.randint(0, w), random.randint(0, h)
        r = random.randint(40, min(w, h) // 4)
        d.ellipse([cx - r, cy - r, cx + r, cy + r],
                  fill=tuple(random.randint(0, 255) for _ in range(3)))
    path = OUT / name if subdir is None else OUT / subdir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if exif_orientation:
        # EXIF Orientation=6 表示“需顺时针旋转90°显示”，即手机竖持拍摄的照片
        exif = Image.Exif()
        exif[274] = exif_orientation
        img.save(path, "JPEG", quality=95, exif=exif)
    else:
        img.save(path, "JPEG", quality=95)
    print(f"生成 {path.relative_to(OUT)} ({w}x{h})")


def transparent_png():
    """生成透明背景 PNG，含不透明和半透明元素"""
    w, h = 1600, 1000
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x in range(w):
        d.line([(x, 0), (x, h)], fill=(80, 160, 240, 60))
    d.ellipse([200, 200, 700, 700], fill=(220, 60, 60, 255))       # 不透明圆
    d.rectangle([900, 400, 1400, 800], fill=(60, 200, 120, 160))   # 半透明方块
    d.ellipse([1100, 150, 1300, 350], outline=(255, 255, 255, 255), width=12)
    d.rectangle([0, 0, 80, 80], fill=(0, 0, 0, 0))  # 左上角留一块全透明区域
    img.save(OUT / "logo_transparent.png", "PNG")
    print(f"生成 logo_transparent.png ({w}x{h}, 透明背景)")


def small_icon():
    """生成 400px 小图，用于验证 --no-upscale 行为"""
    w, h = 400, 300
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([50, 40, 350, 340], fill=(255, 180, 40, 255))
    d.rectangle([120, 120, 280, 260], fill=(40, 90, 200, 200))
    img.save(OUT / "small_icon.png", "PNG")
    print(f"生成 small_icon.png ({w}x{h})")


if __name__ == "__main__":
    gradient_with_shapes((2400, 1350), "photo_landscape.jpg")
    gradient_with_shapes((2400, 1200), "photo_portrait_exif.jpg", exif_orientation=6)
    transparent_png()
    small_icon()
    # 子文件夹图片（用于验证 --recursive）
    gradient_with_shapes((1920, 1080), "product_a.jpg", subdir="sub_folder")
    gradient_with_shapes((500, 400), "thumb.png", subdir="sub_folder/deep")  # 小图
    print("全部测试图片生成完毕 ->", OUT)
