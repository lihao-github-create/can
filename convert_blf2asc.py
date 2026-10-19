import can

src = r"data/Logging_22026-10-16_13-37-18.blf"
dst = r"data/test.asc"

with can.BLFReader(src) as reader:
    with can.ASCWriter(dst) as writer:
        for msg in reader:
            writer.on_message_received(msg)

print("转换成功:", dst)