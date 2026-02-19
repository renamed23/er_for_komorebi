import os
from PIL import Image, ImageDraw, ImageFont


def generate_left_aligned_image():
    # 1. 配置信息
    # 在这里填入你的名字列表
    # names = ["スイ",
    #          "アヤナ",
    #          "コハル",
    #          "ツバキ",
    #          "マオ",
    #          "アキノ",
    #          "トウア",
    #          "ナツキ",
    #          "トウア・アキノ",
    #          "麻宮",
    #          "牧師",
    #          "女性",
    #          "車掌",
    #          "村人",
    #          "老夫",
    #          "夫人",
    #          "少女",
    #          "研究員",
    #          "研究員Ｂ",
    #          "研究員Ｃ",
    #          "？？？"]

    names = ["翠",
             "绫奈",
             "小春",
             "椿",
             "真央",
             "秋乃",
             "冬亚",
             "夏希",
             "冬亚·秋乃",
             "麻宫",
             "牧师",
             "女性",
             "列车员",
             "村民",
             "老者",
             "夫人",
             "少女",
             "研究员",
             "研究员B",
             "研究员C",
             "？？？"]

    item_width = 170
    item_height = 30
    left_padding = 12
    output_path = "translated_img/8.png"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 2. 字体选择
    font_size = 24
    font = None
    candidate_fonts = ["simsun.ttc"]

    for f in candidate_fonts:
        try:
            font = ImageFont.truetype(f, font_size)
            break
        except:
            continue

    if not font:
        font = ImageFont.load_default()

    # 3. 创建画布 (高度 = 名字数量 * 30)
    total_height = item_height * len(names)
    # 使用透明背景 (0,0,0,0)，如果需要白底可以改最后一位为 255
    canvas = Image.new("RGBA", (item_width, total_height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(canvas)

    Y_OFFSET = 2

    # 4. 循环生成
    for i, name in enumerate(names):
        # 计算当前行的起始 Y 坐标
        y_top = i * item_height

        # 获取文字高度以实现垂直居中
        bbox = draw.textbbox((0, 0), name, font=font)
        text_height = bbox[3] - bbox[1]

        # 计算垂直居中的起始 Y 值
        # 公式: 当前行顶部 + (格高 - 字高) / 2
        y_pos = y_top + (item_height - text_height) // 2 - 1 - Y_OFFSET

        # 绘制文字：x 固定为 12
        # draw.text(
        #     (left_padding, y_pos),
        #     name,
        #     fill=(255, 255, 255, 255),        # 白字
        #     font=font,
        #     stroke_width=1,                  # 描边粗细
        #     stroke_fill=(0, 0, 0, 255)       # 黑色描边
        # )
        draw.text(
            (left_padding + 1, y_pos + 1),
            name,
            fill=(0, 0, 0, 255),
            font=font
        )

        # 再画白字
        draw.text(
            (left_padding, y_pos),
            name,
            fill=(255, 255, 255, 255),
            font=font
        )

    # 5. 输出
    canvas.save(output_path)
    print(f"已生成拼接图片至: {output_path}，共 {len(names)} 行。")


if __name__ == "__main__":
    generate_left_aligned_image()
