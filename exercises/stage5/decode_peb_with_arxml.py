import csv
import logging
from collections import Counter
from pathlib import Path

import can
import cantools
from PIL import Image, ImageDraw, ImageFont


BLF_PATH = Path("data/Logging_22026-10-16_13-37-18.blf")
ARXML_PATH = Path(
    "dbc/20260825-lb1-AS5PR&AS5PM&AS5PR X1&大通小VAN-IPD_V6.1.arxml"
)
TARGET_CHANNEL = 1
TARGET_FRAME_ID = 0x325
SIGNAL_NAME = "IPEBSwReq"
OUTPUT_DIR = Path("output/stage5")


# ARXML 中包含多个网络，部分 CAN ID 重复。cantools 会保留最后一个同 ID
# 报文，因此关闭严格重复检查，并在加载后打印实际选中的报文名称。
logging.getLogger("cantools.database.can.database").setLevel(logging.ERROR)
db = cantools.database.load_file(
    ARXML_PATH,
    database_format="arxml",
    strict=False,
)
message = db.get_message_by_frame_id(TARGET_FRAME_ID)
signal = message.get_signal_by_name(SIGNAL_NAME)

state_names = {
    int(value): str(name)
    for value, name in (signal.choices or {}).items()
}
state_labels = {
    0: "无请求",
    1: "开启请求",
    2: "关闭请求",
    3: "保留值",
}
plot_state_names = {
    value: name.split("_", 2)[-1]
    for value, name in state_names.items()
}

print(f"ARXML：{ARXML_PATH}")
print(f"选中报文：{message.name}，CAN ID=0x{message.frame_id:X}")
print(f"信号：{signal.name}，起始位={signal.start}，长度={signal.length} bit")
print(f"教学假设：通道 {TARGET_CHANNEL} 的 0x{TARGET_FRAME_ID:X} 使用上述 ARXML 定义")

first_time = None
previous_value = None
counts = Counter()
length_errors = 0
rows = []
plot_times = []
plot_values = []

with can.BLFReader(BLF_PATH) as log:
    for msg in log:
        if msg.is_error_frame or msg.is_remote_frame:
            continue
        if msg.channel != TARGET_CHANNEL:
            continue
        if (
            msg.arbitration_id != message.frame_id
            or msg.is_extended_id != message.is_extended_frame
        ):
            continue
        if len(msg.data) != message.length:
            length_errors += 1
            continue

        decoded = message.decode(msg.data, decode_choices=False)
        value = decoded[SIGNAL_NAME]
        counts[value] += 1

        if first_time is None:
            first_time = msg.timestamp
        elapsed = msg.timestamp - first_time
        state = state_names.get(value, f"Unknown({value})")
        rows.append({
            "timestamp": f"{msg.timestamp:.6f}",
            "elapsed_s": f"{elapsed:.6f}",
            "channel": msg.channel,
            "can_id": f"0x{msg.arbitration_id:X}",
            SIGNAL_NAME: value,
            "state": state,
        })
        plot_times.append(elapsed)
        plot_values.append(value)

        if previous_value is None or value != previous_value:
            print(
                f"时间={elapsed:.6f}s  "
                f"Byte16=0x{msg.data[16]:02X}  "
                f"{SIGNAL_NAME}={value}  "
                f"{state_labels.get(value, f'未知值({value})')}"
            )
        previous_value = value

print("\n成功解析条数：", sum(counts.values()))
for value in sorted(counts):
    print(f"{state_names.get(value, f'未知值({value})')}条数：", counts[value])
print("长度不匹配条数：", length_errors)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
csv_path = OUTPUT_DIR / "peb_channel1_arxml.csv"
with csv_path.open("w", newline="", encoding="utf-8") as output:
    writer = csv.DictWriter(
        output,
        lineterminator="\n",
        fieldnames=[
            "timestamp", "elapsed_s", "channel",
            "can_id", SIGNAL_NAME, "state",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
print(f"已导出：{csv_path}，共 {len(rows)} 行数据")


plot_path = OUTPUT_DIR / "peb_channel1_arxml.png"
width, height = 1500, 720
left, right, top, bottom = 210, 30, 55, 85
plot_width = width - left - right
plot_height = height - top - bottom
image = Image.new("RGB", (width, height), "white")
draw = ImageDraw.Draw(image)

font_candidates = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
)
font_path = next((path for path in font_candidates if Path(path).exists()), None)
font = ImageFont.truetype(font_path, 20) if font_path else ImageFont.load_default()
small_font = ImageFont.truetype(font_path, 16) if font_path else ImageFont.load_default()
title_font = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()

start_time = plot_times[0]
end_time = plot_times[-1] or 1.0


def x_pixel(value):
    return left + (value - start_time) / max(end_time - start_time, 1e-9) * plot_width


def y_pixel(value):
    return top + (3.2 - value) / 3.4 * plot_height


draw.text((width // 2 - 170, 15), "IPEBSwReq from ARXML", fill="black", font=title_font)
draw.text((width // 2 - 105, height - 42), "Elapsed time (s)", fill="black", font=font)
draw.text((25, height // 2 - 50), SIGNAL_NAME, fill="black", font=font)

for value in sorted(state_names):
    y = y_pixel(value)
    draw.line((left, y, width - right, y), fill="#d9d9d9", width=1)
    draw.text(
        (left - 190, y - 12),
        f"{value}: {plot_state_names[value]}",
        fill="black",
        font=font,
    )

for tick in range(0, 21, 5):
    x = x_pixel(min(tick, end_time))
    draw.line((x, top, x, height - bottom), fill="#eeeeee", width=1)
    draw.text((x - 12, height - bottom + 12), str(tick), fill="black", font=small_font)

draw.line((left, top, left, height - bottom), fill="black", width=2)
draw.line((left, height - bottom, width - right, height - bottom), fill="black", width=2)

points = [(x_pixel(time), y_pixel(value)) for time, value in zip(plot_times, plot_values)]
step_points = [points[0]]
for previous, current in zip(points, points[1:]):
    step_points.extend([(current[0], previous[1]), current])
draw.line(step_points, fill="#1769aa", width=3)
image.save(plot_path)
print(f"已绘制：{plot_path}")
