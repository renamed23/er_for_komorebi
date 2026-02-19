#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple


# ===============================
# cp932 槽位计算
# ===============================


def _raw_slot_index(lead: int, trail: int) -> int:
    """直接按字节计算槽位索引（不要求该字节对能解码成有效字符）。"""
    if 0x81 <= lead <= 0x9F:
        return 192 * lead + trail - 24832
    if 0xE0 <= lead <= 0xFC:
        return 192 * lead + trail - 37120
    raise ValueError(f"lead=0x{lead:02X} 不在游戏支持范围")


def list_game_cp932_slots() -> List[Tuple[bytes, int]]:
    """
    按游戏真实 192 列宽枚举槽位。
    不做 decode。
    不过滤非法字节。
    完全按原始字节空间。
    """

    slots: List[Tuple[bytes, int]] = []
    leads = list(range(0x81, 0xA0)) + list(range(0xE0, 0xEA))

    for lead in leads:
        for trail in range(0x40, 0x100):  # 192 个
            idx = _raw_slot_index(lead, trail)
            raw = bytes((lead, trail))
            slots.append((raw, idx))

    # 按 index 排序
    slots.sort(key=lambda x: x[1])

    print("min idx:", slots[0][1])
    print("max idx:", slots[-1][1])
    print("total:", len(slots))

    return slots


# ===============================
# 24x24 4bpp 渲染
# ===============================

def rasterize_24x24_4bpp(
    ch: str,
    *,
    font_path: str,
    font_size: int = 24,
) -> bytes:
    """
    渲染单字符为 24x24 4bpp（288字节）
    按字体自然基线对齐
    """
    from PIL import Image, ImageDraw, ImageFont

    if len(ch) != 1:
        raise ValueError("只接受单个字符")

    font = ImageFont.truetype(font_path, size=font_size)

    if not font.getmask(ch):
        raise ValueError(f"字体缺字: {ch}")

    img = Image.new("L", (24, 24), 0)
    draw = ImageDraw.Draw(img)

    # 按字体基线自然对齐
    ascent, descent = font.getmetrics()
    y = (24 - ascent - descent) // 2
    draw.text((0, y), ch, fill=255, font=font)

    data = img.tobytes()
    out = bytearray(24 * 12)

    for y in range(24):
        for x in range(0, 24, 2):
            idx = y * 24 + x
            left = data[idx] // 16
            right = data[idx + 1] // 16
            out[y * 12 + (x // 2)] = (left << 4) | right

    return bytes(out)


# ===============================
# 主流程
# ===============================

def generate_full_cp932_font(
    *,
    font_path: str,
    font_size: int,
    mapping_json_path: str,
    output_path: str,
):
    """
    生成完整字形 cp932 字库，并根据 mapping.json 替换字形。
    镂空槽位保留为 288 字节全 0。
    """

    print("枚举 cp932 槽位（包含洞位）...")
    slots = list_game_cp932_slots()

    print("读取映射...")
    raw = json.loads(Path(mapping_json_path).read_text(encoding="utf-8"))
    mapping: Dict[str, str] = raw["mapping"]

    print(f"映射数量: {len(mapping)}")

    print("构建字库字符集合...")

    valid_chars = set()

    for raw_bytes, _ in slots:
        try:
            ch = raw_bytes.decode("cp932")
            valid_chars.add(ch)
        except:
            pass  # 非法字节对跳过

    print(f"字库实际可解码字符数: {len(valid_chars)}")

    # 检查 mapping 是否包含非法 key
    missing = [k for k in mapping.keys() if k not in valid_chars]

    if missing:
        print("以下 mapping key 不存在于字库槽位中：")
        for m in missing[:20]:
            print("  ", repr(m))
        if len(missing) > 20:
            print(f"... 还有 {len(missing) - 20} 个")

        raise ValueError(
            f"mapping 中有 {len(missing)} 个字符不在游戏字库范围内"
        )

    blob = bytearray()

    print("开始渲染字形...")

    for raw, idx in slots:
        try:
            ch = raw.decode("cp932")
            real_char = mapping.get(ch, ch)
            g = rasterize_24x24_4bpp(
                real_char,
                font_path=font_path,
                font_size=font_size,
            )
        except:
            # 非法字符直接空白
            g = b"\x00" * 288
        blob.extend(g)

    Path(output_path).write_bytes(bytes(blob))

    payload = json.loads(Path("translated/blocks.json").read_text("utf-8"))
    payload["blocks"][1538]["data"] = blob.hex()
    Path("translated/blocks.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("完成")
    print(f"总字节: {len(blob)}")


# ===============================
# 入口
# ===============================

if __name__ == "__main__":
    generate_full_cp932_font(
        font_path="simsun.ttc",
        font_size=24,
        mapping_json_path="generated/mapping.json",
        output_path="generated/cp932_full.bin",
    )
