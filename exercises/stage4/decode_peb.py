import csv
from pathlib import Path

from collections import Counter

import can
import cantools

blf_path = "data/Logging_22026-10-16_13-37-18.blf"
dbc_path = (
    "dbc/20260612-lb1-AS5PM-IPD_V5.0_DBC/"
    "20260612-lb1-AS5PM-IPD_V5.0_BKPCANFD_split.dbc"
)

db = cantools.database.load_file(dbc_path)
message = db.get_message_by_frame_id(0x325)

target_channel = 1
signal_name = "PEBSwReq"

first_time = None
previous_value = None
counts = Counter()
length_errors = 0

rows = []


print("教学假设：通道 1 的 0x325 按 BKPCANFD DBC 解释")

with can.BLFReader(blf_path) as log:
    for msg in log:
        if msg.is_error_frame or msg.is_remote_frame:
            continue

        if msg.channel != target_channel:
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
        value = decoded[signal_name]
        counts[value] += 1

        if first_time is None:
            first_time = msg.timestamp

        rows.append({
            "timestamp": f"{msg.timestamp:.6f}",
            "elapsed_s": f"{msg.timestamp - first_time:.6f}",
            "channel": msg.channel,
            "can_id": f"0x{msg.arbitration_id:X}",
            "PEBSwReq": value,
            "state": "Request" if value == 1 else "No_Request",
        })

        # 只打印首次状态和状态发生变化的位置。
        if previous_value is None or value != previous_value:
            elapsed = msg.timestamp - first_time
            state = "有请求" if value == 1 else "无请求"

            print(
                f"时间={elapsed:.6f}s  "
                f"Byte16=0x{msg.data[16]:02X}  "
                f"{signal_name}={value}  {state}"
            )

        previous_value = value

print("\n成功解析条数：", sum(counts.values()))
print("无请求条数：", counts[0])
print("有请求条数：", counts[1])
print("长度不匹配条数：", length_errors)

output_path = Path("output/stage4/peb_channel1.csv")
output_path.parent.mkdir(parents=True, exist_ok=True)

with output_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "timestamp", "elapsed_s", "channel",
            "can_id", "PEBSwReq", "state",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"已导出：{output_path}，共 {len(rows)} 行数据")