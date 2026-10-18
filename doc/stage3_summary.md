# 第三阶段总结：阅读 DBC 并验证信号解码

本阶段从真实信号 `PEBSwReq` 出发，学习了 DBC 的报文、信号、枚举与属性定义，练习了 Intel/Motorola 位提取，并用 `cantools` 验证了手工解析结果。

返回：[学习指南](../learn_guide.md) · 上一阶段：[理解 CAN 报文](stage2_summary.md)

## 1. 本阶段使用的文件

- DBC：[BKPCANFD_split.dbc](../dbc/20260612-lb1-AS5PM-IPD_V5.0_DBC/20260612-lb1-AS5PM-IPD_V5.0_BKPCANFD_split.dbc)
- 练习脚本：[read_dbc.py](../exercises/stage3/read_dbc.py)
- 本次安装并验证的 `cantools` 版本：45.0.0。

本阶段的 Python 解码输入是构造的教学数据，尚未完成真实 BLF 的信号解析。

## 2. BO_：报文定义

真实 DBC 中有以下定义：

```text
BO_ 805 ZXD_BKBCANFD_100ms_FrP257: 24 Vector__XXX
```

| 内容 | 含义 |
|---|---|
| `BO_` | 定义一条报文 |
| `805` | 十进制 CAN ID，即十六进制 `0x325` |
| `ZXD_BKBCANFD_100ms_FrP257` | 报文名称 |
| `24` | 数据长度为 24 字节 |
| `Vector__XXX` | 发送节点字段中的占位名，不能据此确定实际 ECU |

本例 DBC 中的十进制 `805` 与日志打印的十六进制 `0x325` 是同一个 ID。

## 3. SG_：信号定义

上述报文中包含以下信号：

```text
 SG_ PEBSwReq : 135|1@0+ (1,0) [0|1] "null" IPD
```

| 内容 | 含义 |
|---|---|
| `SG_` | 定义一个信号 |
| `PEBSwReq` | 信号名称 |
| `135` | 起始位编号 |
| `1` | 信号长度为 1 bit |
| `@0` | Motorola，大端；`@1` 表示 Intel，小端 |
| `+` | 无符号整数；`-` 表示有符号整数 |
| `(1,0)` | factor = 1，offset = 0 |
| `[0\|1]` | 定义的物理值范围为 0～1 |
| `"null"` | 单位字段的字面字符串，不是 Python 的 `None` |
| `IPD` | 接收节点 |

## 4. 定位 PEBSwReq 的起始位

本例使用的 DBC 位编号在每个字节内以最低位为该字节最小编号：

```text
字节位置        从最高位到最低位的 DBC 编号
Byte 0           7   6   5   4   3   2   1   0
Byte 1          15  14  13  12  11  10   9   8
...
Byte 16        135 134 133 132 131 130 129 128
```

对于起始位 135：

```text
字节下标 = 135 // 8 = 16
字节内位号 = 135 % 8 = 7
```

因此信号位于 **Byte 16 的 bit 7，即第 17 个字节的最高位**。它只有 1 bit，可以直接提取：

```python
raw = (data[16] >> 7) & 1
```

| Byte 16 | 二进制 | bit 7 / raw |
|---|---|---:|
| `00` | `00000000` | 0 |
| `40` | `01000000` | 0 |
| `80` | `10000000` | 1 |
| `85` | `10000101` | 1 |
| `7F` | `01111111` | 0 |

不能以整个字节是否非零来判断这个信号；其余位可能属于别的信号。

## 5. Motorola 和 Intel 跨字节练习

本节均为教学定义，与真实 `PEBSwReq` 无关。

### Motorola：7|12@0+

起始位表示信号的最高有效位。在字节内从高位向低位读取，读完 bit 0 后跳到下一个字节的最高位：

```text
DBC 位编号读取顺序：7 → 6 → … → 0 → 15 → 14 → 13 → 12
```

该定义取 Byte 0 的全部 8 位作为信号高位，再取 Byte 1 的高四位作为信号低位。

```text
AB C5 → 10101011 11000101 → 取 10101011 1100 → 0xABC = 2748
12 34 → 00010010 00110100 → 取 00010010 0011 → 0x123 = 291
```

对此特定布局，可以写成：

```python
raw = (data[0] << 4) | (data[1] >> 4)
```

### Intel：0|12@1+

起始位表示信号的最低有效位。此布局取 Byte 0 的全部 8 位作为信号低位，再取 Byte 1 的低四位作为信号高位。

```text
12 34 → 高四位取 4，低八位取 12 → 0x412 = 1042
AB C5 → 高四位取 5，低八位取 AB → 0x5AB = 1451
```

对此特定布局，可以写成：

```python
raw = data[0] | ((data[1] & 0x0F) << 8)
```

`<<` 表示左移，`>>` 表示右移，`&` 用掩码保留目标位，`|` 将不重叠的位段合并。以上表达式针对这两个具体布局，不能直接用于任意起始位和长度的信号。

## 6. 系数、偏移与范围

教学定义：

```text
SG_ ExampleTemp : 0|12@1+ (0.1,-40) [-40|369.5] "degC" IPD
```

收到 `AB C5` 时：

```text
raw = 0x5AB = 1451
温度 = raw × factor + offset
     = 1451 × 0.1 - 40
     = 105.1 °C
```

12 位无符号整数范围为 0～4095，因此这个例子的物理值范围为：

```text
最小值：0 × 0.1 - 40 = -40 °C
最大值：4095 × 0.1 - 40 = 369.5 °C
```

方括号中的范围是定义信息，不是额外的换算步骤，也不代表解码时一定会自动裁剪数值。

## 7. VAL_ 与 BA_：枚举和附加属性

真实枚举定义：

```text
VAL_ 805 PEBSwReq 0 "PEBSwReq_0_No_Request" 1 "PEBSwReq_1_Request";
```

这为报文 805 中的 `PEBSwReq` 定义了数值含义：0 表示无请求，1 表示有请求。**有请求不等于对应动作已经执行。**

真实属性赋值：

```text
BA_ "ISignalName" SG_ 805 PEBSwReq "IPEBSwReq";
```

这表示为报文 805 中的信号 `PEBSwReq` 设置属性 `ISignalName`，其值是字符串 `IPEBSwReq`。

- `PEBSwReq` 是 `SG_` 定义的实际信号名，Python 按名称查找时使用它。
- `IPEBSwReq` 是附加属性的值，不应直接替代实际信号名。

| 关键字 | 作用 |
|---|---|
| `BO_` | 定义报文 |
| `SG_` | 定义信号位置和解释规则 |
| `VAL_` | 定义数值对应的文字含义 |
| `BA_` | 给报文、信号等对象赋予附加属性 |

## 8. Python 查询 DBC 定义

本次先检查环境，发现未安装 `cantools`，随后安装并确认版本为 45.0.0：

```bash
python3 -m pip install cantools
python3 -c "import cantools; print(cantools.__version__)"
```

练习脚本的核心步骤：

```python
db = cantools.database.load_file(dbc_path)
message = db.get_message_by_frame_id(0x325)
signal = message.get_signal_by_name("PEBSwReq")
```

| Python 属性 | 本次结果 | 对应 DBC 内容 |
|---|---|---|
| `message.length` | 24 | 报文字节数 |
| `signal.start` | 135 | 起始位 |
| `signal.length` | 1 | 信号 bit 数 |
| `signal.byte_order` | `big_endian` | `@0` |
| `signal.is_signed` | `False` | `+`，无符号 |
| `signal.scale` | 1 | factor |
| `signal.offset` | 0 | offset |
| `signal.choices` | 0/1 对应的状态名称 | `VAL_` |

运行命令（在项目根目录执行）：

```bash
python3 exercises/stage3/read_dbc.py
```

输出的定义与手工阅读结果一致。`OrderedDict(...)` 中保存的是数值到枚举状态名称的映射。

## 9. 构造数据并验证自动解码

脚本使用以下方式构造教学数据：

```python
data = bytearray(message.length)

for value in (0x00, 0x40, 0x80, 0x85):
    data[16] = value
    numeric = message.decode(data, decode_choices=False)
    named = message.decode(data, decode_choices=True)
    print(numeric["PEBSwReq"], named["PEBSwReq"])
```

`bytearray(24)` 创建 24 个全为零的字节；`data[16]` 修改第 17 个字节。`message.decode(...)` 按整条报文定义解码，并返回以信号名为键的结果。

已运行得到的目标信号结果：

| Byte 16 | 数值 | 状态 |
|---|---:|---|
| `0x00` | 0 | `PEBSwReq_0_No_Request` |
| `0x40` | 0 | `PEBSwReq_0_No_Request` |
| `0x80` | 1 | `PEBSwReq_1_Request` |
| `0x85` | 1 | `PEBSwReq_1_Request` |

`decode_choices=False` 只关闭枚举文字转换，**不会关闭 factor 和 offset 换算**。本例系数为 1、偏移为 0，所以返回数值恰好等于原始值。

这次实验验证了手工提取与 DBC 解码的一致性。构造数据仅用于检查目标信号规则，不代表真实有效的车辆请求。

## 10. 本阶段结论与下一步

已经完成从“读懂 DBC 定义”到“用 Python 查询和验证定义”的过程。下一阶段将把 `python-can` 读取 BLF 与 `cantools` 解码连接起来。

在真实解码前，需要确认 **BLF 通道与 DBC 网络的对应关系**。此前日志中 `0x325` 在通道 1、2 都出现过，仅凭 ID 相同不能确定应使用哪份 DBC。数据长度匹配是辅助线索，也不能单独证明网络匹配正确，应结合采集配置确认。
