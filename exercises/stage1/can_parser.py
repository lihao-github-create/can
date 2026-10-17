from collections import Counter, defaultdict
import can

blf_path = "data/Logging_22026-10-16_13-37-18.blf"

channel_counts = Counter()
id_counts = defaultdict(Counter)

with can.BLFReader(blf_path) as log:
    for msg in log:
        # 错误帧不是普通的数据报文，本次统计先跳过。
        if msg.is_error_frame:
            continue

        channel = msg.channel

        # 标准帧和扩展帧即使 ID 数值相同，也分别统计。
        key = (msg.arbitration_id, msg.is_extended_id)

        channel_counts[channel] += 1
        id_counts[channel][key] += 1

print(f"总报文数：{sum(channel_counts.values())}")
print(f"通道数量：{len(channel_counts)}")

for channel, count in sorted(channel_counts.items()):
    print(f"\n通道 {channel}：")
    print(f"  报文数：{count}")
    print(f"  不同 ID 数量：{len(id_counts[channel])}")
    print("  各 ID 的报文数：")

    for (can_id, is_extended), number in sorted(id_counts[channel].items()):
        frame_type = "扩展帧" if is_extended else "标准帧"
        print(f"    0x{can_id:03X}  {frame_type}  {number} 条")