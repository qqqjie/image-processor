#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Web 界面测试：直接调用 app.run_web_batch() 全流程 + Zip Slip 防护。
覆盖：默认批处理、重命名、平铺上传与非图片忽略、非法替换规则、恶意 zip。"""
import io
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

from app import run_web_batch, safe_extract_zip


class FakeUpload:
    """模拟 Streamlit 上传的文件对象（.name + .getvalue()）"""

    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getvalue(self):
        return self._data


def img_bytes(w, h, color, fmt="JPEG"):
    b = io.BytesIO()
    Image.new("RGB", (w, h), color).save(b, fmt)
    return b.getvalue()


def make_test_zip() -> bytes:
    """构造测试 zip：两张图 + 一个非图片文件，带子文件夹"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("商品图/主图A.jpg", img_bytes(1000, 700, (200, 60, 60)))
        zf.writestr("商品图/详情/B.png", img_bytes(600, 400, (60, 120, 200), "PNG"))
        zf.writestr("说明.txt", "非图片文件，应被忽略")
    return buf.getvalue()


def zip_names(zip_bytes: bytes):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return sorted(zf.namelist())


def zip_read_image(zip_bytes: bytes, name: str):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return Image.open(io.BytesIO(zf.read(name)))


def test_default_batch():
    """场景一：默认参数（webp/800px/不放大/递归）"""
    stats, rows, zip_bytes, notes = run_web_batch(
        [FakeUpload("测试.zip", make_test_zip())],
        width=800, fmt="webp", quality=80, no_upscale=True, recursive=True)
    assert stats["total"] == 2, f"应找到 2 张图，实际 {stats['total']}"
    assert stats["success"] == 2 and stats["failed"] == 0
    assert stats["skipped_scale"] == 1, "600px 的 B.png 应判定为未放大"
    assert zip_bytes, "未生成下载 zip"
    names = zip_names(zip_bytes)
    assert names == ["商品图/主图A.webp", "商品图/详情/B.webp"], f"zip 内容异常: {names}"
    with zip_read_image(zip_bytes, "商品图/主图A.webp") as im:
        assert im.format == "WEBP" and im.size[0] == 800, f"主图A 异常: {im.format} {im.size}"
    with zip_read_image(zip_bytes, "商品图/详情/B.webp") as im:
        assert im.size == (600, 400), f"B 应保持 600px，实际 {im.size}"
    print("[PASS] 场景一：默认参数批处理 + zip 下载")


def test_rename_batch():
    """场景二：启用重命名（前缀 + 保留原名）"""
    stats, rows, zip_bytes, notes = run_web_batch(
        [FakeUpload("测试.zip", make_test_zip())],
        no_upscale=True, recursive=True,
        prefix="sku-", start=1, keep_name=True)
    assert stats["success"] == 2
    names = zip_names(zip_bytes)
    expected = sorted(["商品图/sku-001_主图A.webp", "商品图/详情/sku-002_B.webp"])
    assert names == expected, f"重命名结果异常: {names}"
    print("[PASS] 场景二：重命名（前缀+保留原名，跨文件夹连续编号）")


def test_loose_files_and_ignore():
    """场景四：平铺上传图片 + 非图片文件被忽略"""
    uploads = [
        FakeUpload("a.jpg", img_bytes(1000, 500, (10, 20, 30))),
        FakeUpload("b.png", img_bytes(300, 300, (40, 50, 60), "PNG")),
        FakeUpload("notes.txt", b"hello"),
    ]
    stats, rows, zip_bytes, notes = run_web_batch(uploads, recursive=False)
    assert stats["total"] == 2 and stats["success"] == 2
    assert any("忽略" in n for n in notes), f"应提示忽略非图片: {notes}"
    assert zip_names(zip_bytes) == ["a.webp", "b.webp"]
    print("[PASS] 场景四：平铺上传 + 非图片忽略")


def test_bad_replace_rule():
    """场景五：非法替换规则必须报 ValueError"""
    try:
        run_web_batch([FakeUpload("a.jpg", img_bytes(100, 100, (1, 2, 3)))],
                      replace_text="bad-rule")
    except ValueError as exc:
        assert "格式错误" in str(exc)
        print("[PASS] 场景五：非法替换规则报错")
        return
    raise AssertionError("非法规则未报错！")


def test_zip_slip():
    """场景三：恶意 zip（含 ../ 穿越路径）必须被拒绝"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.png", img_bytes(50, 50, (1, 2, 3), "PNG"))
    with tempfile.TemporaryDirectory() as td:
        try:
            safe_extract_zip(buf.getvalue(), Path(td))
        except ValueError as exc:
            assert "非法路径" in str(exc)
            print("[PASS] 场景三：Zip Slip 攻击被拒绝")
            return
    raise AssertionError("恶意 zip 未被拒绝！")


if __name__ == "__main__":
    test_zip_slip()
    test_default_batch()
    test_rename_batch()
    test_loose_files_and_ignore()
    test_bad_replace_rule()
    print("\nWEB APP TEST ALL PASSED")
    sys.exit(0)
