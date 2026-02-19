#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GR.052 文件解包工具

根据逆向分析结果，GR.052 文件结构：
- 偏移 0x00: 文件头 (16字节)
- 偏移 0x10: 偏移表
- 偏移 0x401C: 数据区

偏移表结构（根据 sub_409DF0 和 sub_40A280 分析）：
- 偏移表从文件偏移 0x10 开始读取
- 每个 DWORD 表示一个数据边界
- 块i 的起始偏移 = offset_table[i]
- 块i 的结束偏移 = offset_table[i+1]
- 块i 的大小 = offset_table[i+1] - offset_table[i]

在 sub_40A280 中：
  sub_40A180(dword_4BBD24, lpBuffer, 
             dword_4A7878[a1] - *(&dword_4A7874 + a1),  // 大小 = offset[i+1] - offset[i]
             *(&dword_4A7874 + a1));                    // 起始 = offset[i]
"""

import argparse
import struct
import json
from pathlib import Path
from typing import List, Tuple, Optional

HEADER_SIZE = 16  # 文件头大小
OFFSET_TABLE_COUNT = 2044
OFFSET_TABLE_SIZE = OFFSET_TABLE_COUNT * 4
DATA_START = HEADER_SIZE + OFFSET_TABLE_SIZE


def should_ignore(s: str) -> bool:
    if s is None:
        return True
    s = s.strip()
    if s == "":
        return True
    if s.isascii():
        return True
    # 检查Unicode私有区域字符和半角日语字符
    for char in s:
        code_point = ord(char)
        # 私有使用区: U+E000 - U+F8FF
        if 0xE000 <= code_point <= 0xF8FF:
            return True
        # 补充私有使用区-A: U+F0000 - U+FFFFF
        if 0xF0000 <= code_point <= 0xFFFFF:
            return True
        # 补充私有使用区-B: U+100000 - U+10FFFF
        if 0x100000 <= code_point <= 0x10FFFF:
            return True
        # 半角日语字符(标点+片假名): U+FF61 - U+FF9F
        if 0xFF61 <= code_point <= 0xFF9F:
            return True

        # 控制字符: C0 (0-31, 127) 和 C1 (128-159)
        if code_point < 32 and char not in ("\n", "\r", "\t"):
            return True
        if code_point == 127 or (128 <= code_point <= 159):
            return True
    return False


def is_text_block(data: bytes) -> bool:
    """判断数据块是否为文本"""
    try:

        return not should_ignore(data.decode("CP932"))
    except:
        return False


def read_u32(data: bytes, offset: int) -> int:
    """读取4字节无符号整数"""
    return struct.unpack_from("<I", data, offset)[0]


def parse_text_block(data: bytes) -> List[str]:
    """
    解析文本块，按换行符分割
    根据 sub_40B830 的逻辑：
    - 文本以换行符(0x0A)分隔
    - 每个换行符被替换为 NULL 终止符
    """

    return data.decode("CP932").split("\r\n")


def analyze_file(data: bytes) -> dict:
    """分析 GR.052 文件结构"""

    # 读取文件头
    header = data[:HEADER_SIZE]

    # 读取偏移表
    offset_table = []
    i = 0
    while True:
        offset = read_u32(data, HEADER_SIZE + i * 4)
        if offset == 0:
            break
        offset_table.append(offset)
        i += 1

    valid_entries = []
    for i, off in enumerate(offset_table):
        valid_entries.append((i, off))

    # 计算数据块信息
    # 每个 entry[i] 和 entry[i+1] 定义一个块
    blocks = []

    for i in range(len(valid_entries) - 1):
        idx, start_offset = valid_entries[i]
        next_idx, end_offset = valid_entries[i + 1]

        size = end_offset - start_offset
        assert size >= 0
        blocks.append({
            "index": idx,
            "offset": start_offset,
            "size": size,
            "end_offset": end_offset
        })

    return {
        "header": header,
        "file_size": len(data),
        "offset_table": offset_table,
        "blocks": blocks
    }


def unpack(input_path: Path, out_dir: Path):
    """解包 GR.052 文件"""
    print(f"正在读取文件: {input_path}")
    with open(input_path, "rb") as f:
        data = f.read()
    print(f"文件大小: {len(data)} 字节")

    # 分析文件结构
    info = analyze_file(data)
    print(f"找到 {len(info['blocks'])} 个数据块")

    # 创建输出目录
    out_dir.mkdir(parents=True, exist_ok=True)

    # 解析并保存每个数据块
    blocks = []

    for block in info["blocks"]:
        idx = block["index"]
        offset = block["offset"]
        size = block["size"]
        block_data = data[offset:offset + size]

        block = {
            "block_index": idx,
            "offset": offset,
            "size": size,
        }
        if is_text_block(block_data):
            # 解析文本块
            block["lines"] = parse_text_block(block_data)

        else:
            # 保存为二进制块
            block["data"] = block_data.hex()

        blocks.append(block)

    # 保存文本块为JSON
    text_json = {
        "file_name": str(input_path.name),
        "header": info["header"].hex(),
        "total_blocks": len(blocks),
        "blocks": blocks
    }
    text_out = out_dir / "blocks.json"
    with open(text_out, "w", encoding="utf-8") as f:
        json.dump(text_json, f, ensure_ascii=False, indent=2)
    print(f"块已保存: {text_out}")

    print(f"\n解包完成！共处理 {len(info['blocks'])} 个数据块")
    print(f" - 块: {len(blocks)}")


def pack(input_dir: Path, out_path: Path):
    """将 unpack 输出目录重新打包为 GR.052 文件"""
    blocks_json_path = input_dir / "blocks.json"
    if not blocks_json_path.exists():
        raise FileNotFoundError(f"未找到 {blocks_json_path}")

    with open(blocks_json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    raw_blocks = payload.get("blocks", [])
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise ValueError("blocks.json 中缺少有效的 blocks 列表")

    # 规范化并按 block_index 排序
    blocks = []
    for item in raw_blocks:
        idx = int(item["block_index"])
        assert 0 <= idx

        if "data" in item:
            block_data = bytes.fromhex(item["data"])
        elif "lines" in item:
            lines = item["lines"] if isinstance(item["lines"], list) else []
            text = "\r\n".join(str(x) for x in lines)
            block_data = bytearray(text.encode("cp932"))
        else:
            # 没有内容字段，按空块处理
            block_data = b""

        blocks.append((idx, block_data))

    if not blocks:
        raise ValueError("没有可打包的数据块")

    blocks.sort(key=lambda x: x[0])

    # 固定大小偏移表：2044 个 DWORD，未使用位置填 0
    offset_table = [0] * OFFSET_TABLE_COUNT

    data_blob = bytearray()
    for idx, block_data in blocks:
        # 记录该块在文件内的绝对偏移
        offset_table[idx] = DATA_START + len(data_blob)
        data_blob.extend(block_data)

    # 为最后一个块写入结束边界（供 offset[i+1]-offset[i] 计算）
    last_idx = blocks[-1][0]
    offset_table[last_idx + 1] = DATA_START + len(data_blob)

    # 16字节头
    header = bytes.fromhex(payload["header"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(header)
        for off in offset_table:
            f.write(struct.pack("<I", off))
        f.write(data_blob)

    print(f"打包完成: {out_path}")
    print(f" - 块数量: {len(blocks)}")
    print(f" - 数据区大小: {len(data_blob)} 字节")


def main():
    ap = argparse.ArgumentParser(description="GR.052 文件解包工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_unpack = sub.add_parser("unpack", help="解包 GR.052 文件")
    ap_unpack.add_argument(
        "-i", "--input", required=True, help="输入 GR.052 文件路径")
    ap_unpack.add_argument("-o", "--out", required=True, help="输出目录")

    ap_pack = sub.add_parser("pack", help="打包 GR.052 文件")
    ap_pack.add_argument("-i", "--input", required=True, help="输入目录")
    ap_pack.add_argument("-o", "--out", required=True, help="输出文件路径")

    args = ap.parse_args()

    if args.cmd == "unpack":
        unpack(Path(args.input), Path(args.out))
    elif args.cmd == "pack":
        pack(Path(args.input), Path(args.out))


if __name__ == "__main__":
    main()
