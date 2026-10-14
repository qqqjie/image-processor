#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片批量处理器 Web 界面（Streamlit）

上传图片或 zip -> 勾选参数 -> 开始处理 -> 打包下载 processed.zip
复用 image_processor.py 的 process_batch()，与命令行行为完全一致。

架构：
  run_web_batch() 是 Web 侧的全流程纯逻辑（落盘->解压->处理->打包），
  界面只负责渲染和收集参数；测试可直接调用 run_web_batch()，无需模拟控件。

运行：
  streamlit run app.py
"""

import io
import shutil
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

import image_processor as ip

st.set_page_config(page_title="图片批量处理器", page_icon="🖼️", layout="centered")

# ---------------- 会话级临时目录（重新上传自动清空） ----------------
if "work_dir" not in st.session_state:
    st.session_state.work_dir = Path(tempfile.mkdtemp(prefix="imgproc_"))
WORK = st.session_state.work_dir
INPUT_DIR = WORK / "input"
OUTPUT_DIR = WORK / "processed"


def reset_workdir():
    """清空上一次的上传与输出"""
    for d in (INPUT_DIR, OUTPUT_DIR):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)


def safe_extract_zip(zip_bytes: bytes, dest: Path):
    """解压 zip 到 dest，防 Zip Slip：拒绝解压到目标目录之外的路径"""
    dest_resolved = str(dest.resolve())
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.namelist():
            target = str((dest / member).resolve())
            if not (target == dest_resolved or target.startswith(dest_resolved + "\\")
                    or target.startswith(dest_resolved + "/")):
                raise ValueError(f"压缩包内包含非法路径: {member}")
        zf.extractall(dest)


def zip_dir_to_bytes(dir_path: Path) -> bytes:
    """把整个目录打包为 zip 字节流（保持相对路径）"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(dir_path.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(dir_path).as_posix())
    return buf.getvalue()


def run_web_batch(uploaded_files, *, width=800, fmt="webp", quality=80,
                  no_upscale=False, recursive=False, prefix="", start=1,
                  keep_name=False, replace_text="", on_event=None):
    """Web 批处理全流程：解析规则 -> 落盘/解压 -> 处理 -> 打包。
    uploaded_files: 类文件对象列表，需有 .name 与 .getvalue()
    返回 (stats, rows, zip_bytes, notes)；无图片时 zip_bytes 为 None。
    替换规则格式错误或恶意 zip 会抛出 ValueError。"""
    rules = [ln.strip() for ln in (replace_text or "").splitlines() if ln.strip()]
    pairs = ip.parse_replace_rules(rules)  # 格式错误抛 ValueError

    reset_workdir()
    notes, ignored, zip_count = [], [], 0
    for f in uploaded_files:
        name = Path(f.name).name  # 防御性处理：只取 basename
        if name.lower().endswith(".zip"):
            safe_extract_zip(f.getvalue(), INPUT_DIR)  # 恶意 zip 抛 ValueError
            zip_count += 1
        elif Path(name).suffix.lower() in ip.SUPPORTED_EXTS:
            (INPUT_DIR / name).write_bytes(f.getvalue())
        else:
            ignored.append(name)
    if zip_count:
        notes.append(f"本次解压了 {zip_count} 个 zip 压缩包")
    if ignored:
        notes.append(f"已忽略 {len(ignored)} 个非图片文件：{', '.join(ignored[:5])}"
                     + (" ..." if len(ignored) > 5 else ""))

    files = ip.collect_files(INPUT_DIR, OUTPUT_DIR, recursive)
    if not files:
        return {"total": 0, "success": 0, "failed": 0, "skipped_scale": 0,
                "total_in": 0, "total_out": 0, "failures": [], "rows": []}, [], None, notes

    stats = ip.process_batch(
        INPUT_DIR, OUTPUT_DIR, width=width, fmt=fmt, quality=quality,
        no_upscale=no_upscale, recursive=recursive, prefix=prefix,
        start=start, keep_name=keep_name, replace_pairs=pairs,
        on_event=on_event)
    zip_bytes = zip_dir_to_bytes(OUTPUT_DIR) if stats["success"] else None
    return stats, stats["rows"], zip_bytes, notes


# ---------------- 页面 ----------------
st.title("🖼️ 图片批量处理器")
st.caption("批量缩放 · 格式转换压缩 · 批量重命名 —— 上传后一键处理，打包下载")

with st.expander("📖 使用说明（首次使用请展开）", expanded=False):
    st.markdown("""
**怎么传一整个文件夹？** 先把文件夹打成 zip 再上传，目录结构会保留（配合“递归子文件夹”效果最佳）。
也可以直接多选图片上传（平铺模式，不保留目录）。

**处理选项和命令行完全一致**：小图不放大 = `--no-upscale`，递归子文件夹 = `--recursive`。

**隐私**：所有处理都在本机临时目录完成，刷新或重新上传后自动清理，不上传任何数据到第三方。

**上传大小**：默认单文件上限 200MB。需要更大可在本目录放一个 `.streamlit/config.toml`（本项目已附带，上限 2GB）。
""")

# ① 上传
uploaded = st.file_uploader(
    "① 上传图片或 zip 压缩包（整个文件夹请打成 zip 上传，可保留目录结构）",
    accept_multiple_files=True,
    key="uploader",
)

# ② 参数
st.subheader("② 处理参数")
col1, col2, col3 = st.columns(3)
with col1:
    width = st.number_input("目标宽度(px)", min_value=1, max_value=10000,
                            value=800, step=50)
with col2:
    fmt = st.radio("输出格式", ["webp", "jpg"], index=0, horizontal=True)
with col3:
    quality = st.slider("压缩质量", min_value=1, max_value=95, value=80)

col4, col5 = st.columns(2)
with col4:
    no_upscale = st.checkbox("小图不放大（--no-upscale）", value=True)
with col5:
    recursive = st.checkbox("递归子文件夹（--recursive）", value=True)

# ③ 重命名
with st.expander("③ 批量重命名（可选）", expanded=False):
    rename_on = st.checkbox("启用重命名")
    prefix = st.text_input("文件名前缀", value="product-", disabled=not rename_on,
                           help="最终文件名 = 前缀 + 序号，如 product-001.webp")
    c1, c2 = st.columns(2)
    with c1:
        start = st.number_input("序号起始值", min_value=0, value=1,
                                disabled=not rename_on)
    with c2:
        keep_name = st.checkbox("保留原名", value=False, disabled=not rename_on,
                                help="如 product-001_红色长裙.webp")
    replace_text = st.text_area(
        "字符替换（每行一条 旧=新）",
        value=" =_\n（=(\n）=)",
        disabled=not rename_on,
        help="对原文件名主干做字符替换，例如空格转下划线、中文括号转半角",
    )

# ④ 开始处理
if st.button("④ 开始处理", type="primary", use_container_width=True):
    if not uploaded:
        st.warning("请先上传图片或 zip 文件")
        st.stop()

    progress = st.progress(0.0, text="开始处理...")

    def on_event(row, stats):
        done = stats["success"] + stats["failed"]
        progress.progress(done / stats["total"],
                          text=f"处理中 {done}/{stats['total']}...")

    try:
        stats, rows, zip_bytes, notes = run_web_batch(
            uploaded, width=width, fmt=fmt, quality=quality,
            no_upscale=no_upscale, recursive=recursive,
            prefix=prefix if rename_on else "", start=start,
            keep_name=keep_name,
            replace_text=replace_text if rename_on else "",
            on_event=on_event)
    except ValueError as exc:
        st.error(f"处理失败：{exc}")
        st.stop()

    progress.progress(1.0, text="处理完成")
    for note in notes:
        st.info(note)

    if stats["total"] == 0:
        st.warning("没有找到可处理的图片"
                   "（支持 jpg / jpeg / png / webp / bmp / gif / tif / tiff）")
        st.stop()

    # 结果存入会话，刷新页面后仍可下载
    st.session_state["result_rows"] = rows
    st.session_state["result_stats"] = stats
    st.session_state["result_zip"] = zip_bytes

# ---------------- 结果区（从会话恢复，刷新不丢失） ----------------
if "result_zip" in st.session_state:
    stats = st.session_state["result_stats"]
    rows = st.session_state["result_rows"]

    st.subheader("⑤ 处理结果")
    m1, m2, m3 = st.columns(3)
    m1.metric("成功", f"{stats['success']} 张")
    m2.metric("失败", f"{stats['failed']} 张")
    if stats["skipped_scale"]:
        m3.metric("未放大", f"{stats['skipped_scale']} 张")
    else:
        m3.metric("输出格式", fmt)

    if stats["success"]:
        diff = stats["total_in"] - stats["total_out"]
        label = "节省" if diff >= 0 else "增加"
        st.metric(
            label="总体积",
            value=f"{ip.human_size(stats['total_out'])}",
            delta=f"{label} {ip.human_size(abs(diff))}"
                  f"（{abs(diff) / stats['total_in'] * 100:.1f}%）",
            delta_color="off" if diff < 0 else "normal",
        )

    # 明细表
    data = []
    for r in rows:
        if r["error"]:
            data.append([r["rel"], "—", ip.human_size(r["src_size"]), "—", "—",
                         f"失败: {r['error']}"])
        else:
            d = r["src_size"] - r["dst_size"]
            pct = f"-{d / r['src_size'] * 100:.1f}%" if r["src_size"] else "—"
            note = "未放大，保持原尺寸" if not r["resized"] else ""
            data.append([r["rel"], r["dst"], ip.human_size(r["src_size"]),
                         ip.human_size(r["dst_size"]), pct, note])
    df = pd.DataFrame(data, columns=["原文件", "输出文件", "原大小", "新大小",
                                     "体积变化", "备注"])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.download_button(
        "📦 下载 processed.zip",
        data=st.session_state["result_zip"],
        file_name="processed.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True,
    )

st.caption("所有处理均在本地临时目录完成 · 与命令行工具 image_processor.py 同一套处理逻辑")
