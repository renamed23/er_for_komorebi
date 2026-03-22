#!/usr/bin/env python3

import os
from pathlib import Path

from utils_tools.libs import translate_lib

config = {
    "WINDOW_TITLE": "斑驳树影间，摇曳的灵魂之声",
    "REDIRECTION_SRC_PATH": "GR.052",
    "REDIRECTION_TARGET_PATH": "KOMOREBI_CHS.PAK",
}

hook_lists = {
    "enable": [],
    "disable": [],
}

features = [
    "default_impl",
    "enable_iat_hook",
    "bind_window_title_overrider",
    "enable_window_title_override",
    "bind_path_redirector"
]

PACKER = "python packer.py"
ASMER = "python ops.py"

ER = [
    (
        "python er.py extract --path raw --output raw.json",
        "python er.py replace --path raw --text generated/translated.json",
    )
]


def extract():
    print("执行提取...")
    translate_lib.system(
        f"{PACKER} unpack -i GR.052 -o raw")
    translate_lib.extract_and_concat(ER)
    translate_lib.json_process("e", "raw.json")
    # 需要删除一些不需要修的图
    # translate_lib.system("python er_img.py extract")


def replace():
    print("执行替换...")
    Path("generated/dist").mkdir(parents=True, exist_ok=True)

    # 你的 replace 逻辑
    translate_lib.generate_json(config, "config.json")
    translate_lib.generate_json(hook_lists, "hook_lists.json")
    translate_lib.copy_path(
        "translated.json", "generated/translated.json", overwrite=True
    )
    translate_lib.copy_path("raw.json", "generated/raw.json", overwrite=True)
    translate_lib.json_check()
    translate_lib.json_process("r", "generated/translated.json")
    translate_lib.ascii_to_fullwidth()
    # cp932,shift_jis,gbk
    translate_lib.replace("cp932", filter_rare=False)

    translate_lib.split_and_replace(ER)

    translate_lib.system("python generate_name_img.py")
    translate_lib.system("python er_img.py replace")
    translate_lib.system("python generate_bitmap_font.py")

    translate_lib.copy_path(
        "translated", "generated/translated", overwrite=True)

    translate_lib.system(
        f"{PACKER} pack -i generated/translated -o generated/dist/KOMOREBI_CHS.PAK"
    )

    translate_lib.merge_directories(
        "assets/dist_pass", "generated/dist", overwrite=True
    )

    translate_lib.TextHookBuilder(os.environ["TEXT_HOOK_PROJECT_PATH"]).build(
        features, panic="immediate-abort"
    )


def main():
    translate_lib.create_cli(extract, replace)()


if __name__ == "__main__":
    main()
