**先学会“看 BLF 里的 CAN 原始报文”**，再学 **“结合 DBC 把原始字节解析成车速、方向盘角度、档位这类信号”**。你第一次接触 CAN 和 BLF，不需要一开始就啃协议细节。

你可以先建立这个最小认识：

- **CAN**：车上很多 ECU 之间通信的一种总线协议。
- 一条 CAN 报文最核心的是：
  - 时间戳
  - CAN ID，例如 `0x123`
  - DLC/Length，例如 8 字节
  - Data，例如 `01 7F 20 00 00 00 12 A5`
- **BLF**：Vector 的二进制日志格式，可以理解成“把实车上采集到的大量 CAN/CAN FD 等总线数据保存下来的日志文件”。
- **DBC**：告诉解析工具“某个 CAN ID 的哪几个 bit 表示什么信号，以及如何换算成物理值”。

所以最重要的关系是：

```text
实车 CAN 总线
    ↓
采集设备
    ↓
BLF 文件
    ↓
看到 CAN ID + 原始字节
    ↓
DBC
    ↓
VehicleSpeed = 42.3 km/h
SteeringAngle = -15.2 deg
Gear = D
```

## 我建议你按 4 个阶段学

### 阶段 1：先直接打开 BLF

本阶段已完成的 Python 实操、字段说明和实车日志观察结果，见 [第一阶段学习总结](doc/stage1_summary.md)。

如果你们公司有 Vector 工具，最常见的是：

- CANalyzer
- CANoe

直接加载 `.blf` 就能看报文。

如果你想用免费/开源方案，后面也可以用 Python：

```bash
pip install python-can
```

Python 读取 BLF：

```python
import can

log = can.BLFReader("test.blf")

for msg in log:
    print(msg)
```

你可能会看到类似：

```text
Timestamp: 1760700000.123456
ID: 0123
S Rx
DL: 8
01 7F 20 00 00 00 12 A5
```

你现在第一步只需要会认：

```text
timestamp
CAN ID
Rx / Tx
DLC
Data
```

---

## 阶段 2：理解一条 CAN 报文

假设你看到：

```text
Time          ID       DLC   Data
12.345678     0x123     8    10 27 00 00 12 34 56 78
```

可以理解为：

```text
0x123
│
└── 这类消息的编号

8
│
└── 数据长度 8 Byte

10 27 00 00 12 34 56 78
│
└── 真正的数据 payload
```

但是：

```text
10 27
```

到底是：

```text
10000 rpm
```

还是：

```text
39.06 km/h
```

光看 BLF 是不知道的。

这就需要 **DBC**。

---

## 阶段 3：学习 DBC

例如 DBC 里面可能定义：

```text
CAN ID 0x123
```

其中：

```text
Byte 0~1 = VehicleSpeed
```

公式：

```text
physical value =
raw value × factor + offset
```

假设：

```text
factor = 0.01
offset = 0
```

原始数据：

```text
10 27
```

如果定义为 Intel/Little Endian：

```text
raw = 0x2710
    = 10000
```

那么：

```text
VehicleSpeed = 10000 × 0.01
             = 100 km/h
```

最终你看到的就不再是：

```text
0x123  10 27 00 00 12 34 56 78
```

而可能是：

```text
VehicleSpeed = 100 km/h
```

这一步是实际项目里最重要的。

---

## 阶段 4：Python 自动解析 BLF + DBC

之后非常推荐学：

```bash
pip install python-can cantools
```

典型代码：

```python
import can
import cantools

db = cantools.database.load_file("vehicle.dbc")

for msg in can.BLFReader("vehicle.blf"):

    try:
        decoded = db.decode_message(
            msg.arbitration_id,
            msg.data
        )

        print(
            msg.timestamp,
            hex(msg.arbitration_id),
            decoded
        )

    except KeyError:
        pass
```

可能输出：

```text
1760700000.123 0x123 {'VehicleSpeed': 42.3}
1760700000.133 0x201 {'SteeringAngle': -12.5}
1760700000.143 0x305 {'GearPosition': 'D'}
```

这基本就是以后做自动化分析的基础。

---

# 你现在最应该关注的 6 个概念

作为入门，我不建议你现在就研究 CAN 控制器、仲裁时序、电气层、位填充这些细节。

先把下面 6 个东西弄懂：

| 概念 | 先理解到什么程度 |
|---|---|
| CAN ID | 类似消息编号 |
| DLC | 数据长度 |
| Data | 原始字节 |
| Timestamp | 报文出现时间 |
| BLF | CAN 日志文件 |
| DBC | CAN 原始数据的解释规则 |

然后再逐渐补：

```text
Standard CAN ID
Extended CAN ID
CAN FD
Intel / Motorola
Start Bit
Bit Length
Factor
Offset
Cycle Time
Multiplex
```

其中最容易踩坑的是：

```text
Intel / Motorola
Start Bit
Factor / Offset
```

以后你解析错误，十有八九都会和这些有关。

---

# 一个很适合你的实际学习路线

你现在手里既然已经有 **实车 BLF**，我建议不要脱离实际数据学。

直接找一份 BLF，然后完成下面几个任务：

```text
第 1 天
BLF 能打开
↓
找到有多少 CAN channel
↓
找到有哪些 CAN ID
↓
观察某个 CAN ID 的数据变化
```

然后：

```text
第 2 天
找对应 DBC
↓
加载 DBC
↓
把 CAN ID 解析成信号
↓
找到 VehicleSpeed
↓
找到 SteeringAngle
```

再然后：

```text
第 3 天
Python 读取 BLF
↓
按 CAN ID 过滤
↓
解析 DBC
↓
导出 CSV
```

比如最终实现：

```text
timestamp,VehicleSpeed,SteeringAngle,Gear
0.000,0.0,0.2,P
0.010,0.0,0.2,P
0.020,1.3,0.1,D
...
```

做到这里，你已经能处理很多实际的实车 CAN 数据分析需求了。
