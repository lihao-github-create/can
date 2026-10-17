import can

blf_path = "data/Logging_22026-10-16_13-37-18.blf"

target_channel = 1
target_id = 0x0B4

first_time = None
previous_time = None
count = 0

with can.BLFReader(blf_path) as log:
    for msg in log:
        if msg.is_error_frame or msg.is_remote_frame:
            continue

        if msg.channel != target_channel:
            continue

        if msg.arbitration_id != target_id or msg.is_extended_id:
            continue

        if first_time is None:
            first_time = msg.timestamp

        elapsed = msg.timestamp - first_time

        if previous_time is None:
            interval = "首次"
        else:
            interval = f"{(msg.timestamp - previous_time) * 1000:.3f}ms"

        print(
            f"时间={elapsed:.6f}s  "
            f"间隔={interval:>10}  "
            f"数据={msg.data.hex(' ')}"
        )

        previous_time = msg.timestamp
        count += 1

        if count >= 20:
            break