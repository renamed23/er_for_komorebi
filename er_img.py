#!/usr/bin/env python3

"""BP 块 <-> PNG bytes 转换（仅处理以 b'BP' 开头的未压缩块）。

根据逆向结果，BP 头布局为：
    0x00: 2 bytes magic, 固定 b"BP"
    0x02: 2 bytes 保留字段（未使用）
    0x04: uint32 little-endian, width
    0x08: uint32 little-endian, height
    0x0C: uint32 little-endian, channels (1/3/4)
    0x10: 像素数据

像素通道在 BP 中可按 RGB / RGBA / L 解释；
"""

import argparse
import io
import json
from pathlib import Path
import struct
from typing import Tuple

from PIL import Image


_HEADER_SIZE = 16


def _parse_bp_header(bpic_bytes: bytes) -> Tuple[bytes, int, int, int]:
    if len(bpic_bytes) < _HEADER_SIZE:
        raise ValueError("BPIC 数据太短，至少需要 16 字节头")

    magic = bpic_bytes[:4]
    if magic != b"BPIC":
        raise ValueError(f"不是 BPIC 块，magic={magic!r}")

    width = struct.unpack_from("<I", bpic_bytes, 4)[0]
    height = struct.unpack_from("<I", bpic_bytes, 8)[0]
    channels = struct.unpack_from("<I", bpic_bytes, 12)[0]

    if width <= 0 or height <= 0:
        raise ValueError(f"非法尺寸: {width}x{height}")
    if channels not in (1, 3, 4):
        raise ValueError(f"不支持的通道数: {channels}（仅支持 1/3/4）")

    return bpic_bytes[2:4], width, height, channels


def bpic_bp_to_png_bytes(bpic_bytes: bytes) -> bytes:
    """将 BP 块 bytes 转为 PNG bytes。"""
    _reserved, width, height, channels = _parse_bp_header(bpic_bytes)

    pixel_size = width * height * channels
    payload = bpic_bytes[_HEADER_SIZE:]
    if len(payload) < pixel_size:
        raise ValueError(
            f"像素数据不足: 需要 {pixel_size} 字节，实际 {len(payload)} 字节"
        )
    payload = payload[:pixel_size]

    mode = {1: "L", 3: "RGB", 4: "RGBA"}[channels]

    img = Image.frombytes(mode, (width, height), payload)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def png_bytes_to_bpic_bp(png_bytes: bytes) -> bytes:
    """将 PNG bytes 转为 BP 块 bytes。"""
    if not png_bytes:
        raise ValueError("png_bytes 为空")

    with Image.open(io.BytesIO(png_bytes)) as img:
        # 保持通道转换逻辑不变
        if "A" in img.getbands():
            img = img.convert("RGBA")
            channels = 4
            mode = "RGBA"
        else:
            img = img.convert("RGB")
            channels = 3
            mode = "RGB"

        width, height = img.size

        payload = img.tobytes("raw", mode)

    header = bytearray(_HEADER_SIZE)
    header[0:4] = b"BPIC"
    struct.pack_into("<I", header, 4, width)
    struct.pack_into("<I", header, 8, height)
    struct.pack_into("<I", header, 12, channels)

    return bytes(header) + payload


def _load_blocks_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"未找到文件: {path}")
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError(f"{path} 中缺少有效的 blocks 列表")
    return payload


def extract_bp_images(blocks_json_path: Path, out_dir: Path) -> None:
    """从 blocks.json 中提取可识别 BP 块并导出为 PNG。"""
    payload = _load_blocks_json(blocks_json_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    total_data_blocks = 0
    exported = 0
    skipped = 0

    for block in payload["blocks"]:
        if "data" not in block:
            continue

        total_data_blocks += 1
        block_index = block.get("block_index")
        hex_data = block.get("data")

        if not isinstance(hex_data, str) or not hex_data:
            skipped += 1
            continue

        try:
            block_bytes = bytes.fromhex(hex_data)
            png_bytes = bpic_bp_to_png_bytes(block_bytes)
        except Exception:
            # 不是 BP 图像块或数据损坏，按需求跳过
            skipped += 1
            continue

        out_path = out_dir / f"{block_index}.png"
        with open(out_path, "wb") as f:
            f.write(png_bytes)
        exported += 1

    print(f"扫描 data 块: {total_data_blocks}")
    print(f"导出 PNG: {exported}")
    print(f"跳过(非BP或异常): {skipped}")
    print(f"输出目录: {out_dir}")


def replace_bp_images(blocks_json_path: Path, translated_img_dir: Path) -> None:
    """将 translated_img 中的 PNG 覆盖写回 translated/blocks.json 的 data 字段。"""
    payload = _load_blocks_json(blocks_json_path)

    blocks = payload["blocks"]
    block_map = {}
    for block in blocks:
        if "block_index" in block:
            block_map[int(block["block_index"])] = block

    replaced = 0
    ignored = 0
    missing_block = 0

    if not translated_img_dir.exists():
        raise FileNotFoundError(f"未找到图片目录: {translated_img_dir}")

    for png_path in sorted(translated_img_dir.glob("*.png")):
        stem = png_path.stem
        if not stem.isdigit():
            ignored += 1
            continue

        block_index = int(stem)
        target_block = block_map.get(block_index)
        if target_block is None:
            missing_block += 1
            continue

        with open(png_path, "rb") as f:
            png_bytes = f.read()

        bp_bytes = png_bytes_to_bpic_bp(png_bytes)
        target_block["data"] = bp_bytes.hex()
        replaced += 1

    with open(blocks_json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"替换完成: {blocks_json_path}")
    print(f"已替换图片: {replaced}")
    print(f"忽略文件名非数字: {ignored}")

    if missing_block != 0:
        raise ValueError(f"有{missing_block}个图片指向的块不存在")


def main() -> None:
    parser = argparse.ArgumentParser(description="BP 图片块提取/回填工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ep = sub.add_parser("extract", help="从 blocks.json 提取 BP 图片到 PNG")
    ep.add_argument(
        "--blocks-json",
        default="raw/blocks.json",
        help="输入 blocks.json 路径（默认: raw/blocks.json）",
    )
    ep.add_argument(
        "--out-dir",
        default="raw_img",
        help="PNG 输出目录（默认: raw_img）",
    )

    rp = sub.add_parser(
        "replace", help="将 translated_img 的 PNG 回填到 blocks.json")
    rp.add_argument(
        "--blocks-json",
        default="translated/blocks.json",
        help="待回填的 blocks.json 路径（默认: translated/blocks.json）",
    )
    rp.add_argument(
        "--img-dir",
        default="translated_img",
        help="PNG 图片目录（默认: translated_img）",
    )

    args = parser.parse_args()
    if args.cmd == "extract":
        extract_bp_images(Path(args.blocks_json), Path(args.out_dir))
    elif args.cmd == "replace":
        replace_bp_images(Path(args.blocks_json), Path(args.img_dir))


if __name__ == "__main__":
    main()
