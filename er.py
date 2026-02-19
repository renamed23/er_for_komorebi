#!/usr/bin/env python3

import argparse
import json
import os
import re
from typing import Dict, List, Optional, Tuple

from utils_tools.libs import translate_lib


def should_ignore(s: str) -> bool:
    if s is None:
        return True
    s = s.strip()
    if s == "":
        return True
    if s.isascii():
        return True

    # 大概是注释？
    if s.startswith("91"):
        return True
    # 特殊OP
    if s.startswith("3"):
        return True
    if "txt" in s:
        return True

    return False


def parse_select_line(s: str) -> List[Dict]:
    results = []

    prefix = ""
    if s.startswith("40"):
        # 提取数字前缀
        m = re.match(r"(40\d)", s)
        if m:
            prefix = m.group(1)
            s = s[len(prefix):]

    # 拆分 message#tail#
    parts = re.findall(r"([^#]+)#([^#]+)#", s)

    for i, (msg, tail) in enumerate(parts):
        results.append({
            "message": msg,
            "tail": f"#{tail}#",
            "is_select": True,
            "following": i != len(parts) - 1,
            **({"prefix": prefix} if i == 0 and prefix else {})
        })

    return results


def parse_normal_line(s: str) -> List[Dict]:
    m = re.match(r"^(.*?)「(.*?」)$", s)
    if m:
        name = m.group(1).strip()
        message = "「" + m.group(2)
        return [{
            "name": name,
            "message": message
        }]

    return [{
        "message": s
    }]


def rebuild_select_group(text: List[Dict], start_index: int) -> Tuple[str, int]:
    prefix = text[start_index].get("prefix", "")
    result = prefix
    i = start_index

    while True:
        item = text[i]
        result += item["message"] + item["tail"]

        if not item.get("following", False):
            i += 1
            break

        i += 1

    return result, i

# --------------------------------------------------------------------


def extract_strings_from_file(file_path: str) -> List[Dict]:
    """
    扫描单文件，提取字符串。
    返回的 results: 每项至少包含 'message'；若该对话有角色名则包含 'name'。
    """
    results: List[Dict] = []
    with open(file_path, "r", encoding="utf-8") as f:
        json_file = json.load(f)

    for block in json_file["blocks"]:
        if "lines" in block:
            for line in block["lines"]:
                if should_ignore(line):
                    continue
                if line.startswith("40"):
                    results.extend(parse_select_line(line))
                else:
                    results.extend(parse_normal_line(line))

    return results


def extract_strings(path: str, output_file: str):
    files = translate_lib.collect_files(path)
    results = []
    for file in files:
        results.extend(extract_strings_from_file(file))

    print(f"提取了 {len(results)} 项")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


# ========== 替换 ==========


def replace_in_file(
    file_path: str,
    text: List[Dict[str, str]],
    output_dir: str,
    trans_index: int,
    base_root: str,
) -> int:
    """
    替换单文件中的字符串。返回更新后的 trans_index。
    text: 全局译文列表（每项至少有 'message'，可能还含 'name'）
    """
    with open(file_path, "r", encoding="utf-8") as f:
        json_file = json.load(f)

    for block in json_file["blocks"]:
        if "lines" in block:
            for i in range(len(block["lines"])):
                line = block["lines"][i]

                if should_ignore(line):
                    continue

                trans_item = text[trans_index]

                # 选项
                if trans_item.get("is_select"):
                    rebuilt, new_index = rebuild_select_group(
                        text, trans_index)
                    block["lines"][i] = rebuilt
                    trans_index = new_index
                else:
                    # 普通
                    if "name" in trans_item:
                        block["lines"][i] = f"{trans_item['name']}{trans_item['message']}"
                    else:
                        block["lines"][i] = trans_item["message"]

                    trans_index += 1

    # ---------- 保存 ----------
    rel = os.path.relpath(file_path, start=base_root)
    out_path = os.path.join(output_dir, rel)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(json_file, f, ensure_ascii=False, indent=2)

    return trans_index


def replace_strings(path: str, text_file: str, output_dir: str):
    with open(text_file, "r", encoding="utf-8") as f:
        text = json.load(f)
    files = translate_lib.collect_files(path)
    trans_index = 0

    for file in files:
        trans_index = replace_in_file(
            file, text, output_dir, trans_index, base_root=path
        )
        print(f"已处理: {file}")
    if trans_index != len(text):
        print(f"错误: 有 {len(text)} 项译文，但只消耗了 {trans_index}。")
        exit(1)


# ---------------- main ----------------


def main():
    parser = argparse.ArgumentParser(description="文件提取和替换工具")
    subparsers = parser.add_subparsers(
        dest="command", help="功能选择", required=True)

    ep = subparsers.add_parser("extract", help="解包文件提取文本")
    ep.add_argument("--path", required=True, help="文件夹路径")
    ep.add_argument("--output", default="raw.json", help="输出JSON文件路径")

    rp = subparsers.add_parser("replace", help="替换解包文件中的文本")
    rp.add_argument("--path", required=True, help="文件夹路径")
    rp.add_argument("--text", default="translated.json", help="译文JSON文件路径")
    rp.add_argument(
        "--output-dir", default="translated", help="输出目录(默认: translated)"
    )

    args = parser.parse_args()
    if args.command == "extract":
        extract_strings(args.path, args.output)
        print(f"提取完成! 结果保存到 {args.output}")
    elif args.command == "replace":
        replace_strings(args.path, args.text, args.output_dir)
        print(f"替换完成! 结果保存到 {args.output_dir} 目录")


if __name__ == "__main__":
    main()
