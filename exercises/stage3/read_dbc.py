import cantools

dbc_path = (
    "dbc/20260612-lb1-AS5PM-IPD_V5.0_DBC/"
    "20260612-lb1-AS5PM-IPD_V5.0_BKPCANFD_split.dbc"
)

db = cantools.database.load_file(dbc_path)

message = db.get_message_by_frame_id(0x325)
signal = message.get_signal_by_name("PEBSwReq")

print("报文名称：", message.name)
print(f"CAN ID：0x{message.frame_id:X}")
print("报文长度：", message.length, "字节")

print("信号名称：", signal.name)
print("起始位：", signal.start)
print("位长度：", signal.length)
print("字节序：", signal.byte_order)
print("是否有符号：", signal.is_signed)
print("系数：", signal.scale)
print("偏移：", signal.offset)
print("枚举定义：", signal.choices)


# 构造与 DBC 长度一致的 24 字节教学数据。
data = bytearray(message.length)

for value in (0x00, 0x40, 0x80, 0x85):
    data[16] = value

    # 保留数值形式，便于检查计算结果。
    numeric = message.decode(data, decode_choices=False)

    # 使用默认的枚举转换，得到状态名称。
    named = message.decode(data, decode_choices=True)

    print(
        f"Byte 16=0x{value:02X}  "
        f"数值={numeric['PEBSwReq']}  "
        f"状态={named['PEBSwReq']}"
    )