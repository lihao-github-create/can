from collections import Counter
import can

blf_path = "data/Logging_22026-10-16_13-37-18.blf"
target_id = 0x325

counts = Counter()
first_samples = {}

with can.BLFReader(blf_path) as log:
    for msg in log:
        if msg.is_error_frame or msg.is_remote_frame:
            continue

        if msg.arbitration_id != target_id or msg.is_extended_id:
            continue

        key = (msg.channel, len(msg.data), msg.is_fd)
        counts[key] += 1

        if key not in first_samples:
            first_samples[key] = bytes(msg.data)

if not counts:
    print("没有找到目标报文")
else:
    for key, count in sorted(counts.items()):
        channel, length, is_fd = key
        print(
            f"通道={channel}  ID=0x{target_id:X}  "
            f"长度={length}字节  CAN FD={is_fd}  数量={count}"
        )
        print("首条数据：", first_samples[key].hex(" "))