# 第四阶段总结：解析真实 BLF 并导出 CSV

本阶段把 `python-can` 读取 BLF 与 `cantools` 解码 DBC 连接起来，完成目标报文筛选、信号状态统计和 CSV 导出。

返回：[学习指南](../learn_guide.md) · 上一阶段：[阅读 DBC 并验证解码](stage3_summary.md)

**本次解析的前提：假设通道 1 的 `0x325` 适用 BKPCANFD DBC。由于没有采集配置或接线说明，这个对应关系尚未得到确认。**

## 1. 通道、网络和 DBC 的关系

| 概念 | 含义 | 作用 |
|---|---|---|
| CAN 网络 | 一组节点通信的 CAN 总线 | 确定消息所属的通信网络 |
| 采集通道 | 采集设备或记录工具中的接口编号 | 区分报文的采集入口 |
| DBC | 匹配网络、车型和版本的报文定义文件 | 把 ID 和原始字节解释成信号 |

以下是教学拓扑，不是当前车辆已确认的接线：

```text
车身 ECU ── 车身 CAN ── 网关接口 A
                         │
动力 ECU ── 动力 CAN ── 网关接口 B
                         │
雷达 ECU ── ADAS CAN ── 网关接口 C

采集连接示例：
车身 CAN ── 采集通道 1 ──┐
动力 CAN ── 采集通道 2 ──┼── 同一份 BLF
ADAS CAN ── 采集通道 3 ──┘
```

这个示例中，通道 1 使用车身网络 DBC，通道 2 使用动力网络 DBC，通道 3 使用 ADAS 网络 DBC。实际映射取决于接线和采集配置，通道编号本身没有固定的网络含义。

DBC 通常也不直接说明自己对应 BLF 中的哪个通道。正确的解析链路是：

```text
BLF 通道 → 确认对应网络 → 选择匹配版本的 DBC → 查找 ID → 解码信号
```

不同网络可以独立使用相同 CAN ID，含义可能不同。网关也可能按配置转发相同 ID 和数据，或重新打包信息。因此，两个通道出现相同 ID，甚至首条数据相同，都不能单独证明它们属于同一网络或存在转发。

## 2. 检查真实日志中的目标报文

脚本：[check_message.py](../exercises/stage4/check_message.py)

输入日志：`data/Logging_22026-10-16_13-37-18.blf`。

在项目根目录运行：

```bash
python3 exercises/stage4/check_message.py
```

脚本跳过错误帧、远程帧，只保留标准帧 `0x325`，按以下组合分组计数：

```python
key = (msg.channel, len(msg.data), msg.is_fd)
```

本次结果：

| 通道 | ID | 数据长度 | CAN FD | 数量 |
|---|---|---:|---|---:|
| 1 | `0x325` | 24 字节 | 是 | 175 |
| 2 | `0x325` | 24 字节 | 是 | 175 |

两个通道的首条数据相同：

```text
ff 8f 00 00 00 f8 00 00 03 00 00 00 08 ff 00 1f 3f ff ff ff ff ff ff ff
```

这与 BKPCANFD DBC 中 `0x325` 的 24 字节长度一致。但长度匹配只是一条线索，不能确认网络和版本匹配，也不能由首条相同推断全部 175 条相同。

首条数据的 Byte 16 是 `0x3F = 00111111`。如果使用当前 DBC，则目标信号 `PEBSwReq` 取 2 bit，原始值为 0，表示无请求。

## 3. 没有采集配置时，如何寻找候选 DBC

本次检查了同目录下的 `BKPCANFD_split.ini`，内容是 `View_...`、`COLUMNWIDTHS` 等视图设置，未发现通道与网络的对应配置。

随后对比各通道记录和五份 DBC，匹配条件为：

```text
CAN ID 相同 + 标准/扩展格式相同 + 数据长度相同
```

对错误帧和远程帧进行排除后，按不同 `(ID, 帧格式, 数据长度)` 组合统计，结果为：

| DBC | 通道 1：167 种 | 通道 2：74 种 | 通道 3：90 种 |
|---|---:|---:|---:|
| BKPCANFD | 130 | 31 | 21 |
| CHCANFD | 20 | 34 | 13 |
| PTCANFD | 15 | 15 | 17 |
| SFCANFD | 4 | 3 | 10 |
| ADAS_Local_CANFD3 | 0 | 0 | 1 |

表中数字是匹配的不同组合数量，不是报文出现次数，也不是匹配正确的概率。同一组合可能出现在多份 DBC 中，因此不能直接将各行相加。

通道 1 与 BKPCANFD 的匹配最突出，因而本次选择它作为教学候选。通道 2、3 的网络映射仍未确认，不能仅按表中最大数字就认定接线关系。

这项对比是在学习过程中临时运行的分析，不是 `check_message.py` 当前包含的功能。

## 4. 用 DBC 解码真实 BLF

脚本：[decode_peb.py](../exercises/stage4/decode_peb.py)

目标配置：

| 项目 | 本次取值 |
|---|---|
| 通道 | 1 |
| CAN ID | `0x325`，十进制 805 |
| 帧格式 | 标准 ID |
| DBC | BKPCANFD_split.dbc |
| 定义的数据长度 | 24 字节 |
| 目标信号 | `PEBSwReq` |

处理流程：

```text
加载 DBC，找到报文 0x325
    ↓
逐条读取 BLF
    ↓
跳过错误帧、远程帧
    ↓
筛选通道、CAN ID 和标准/扩展格式
    ↓
检查实际字节数与 DBC 定义一致
    ↓
解码并读取 PEBSwReq
    ↓
统计每种状态，保存每条结果
    ↓
首次状态或状态变化时打印
```

核心解码代码：

```python
decoded = message.decode(msg.data, decode_choices=False)
value = decoded["PEBSwReq"]
```

`decode_choices=False` 关闭枚举文字转换，但保留系数和偏移换算。本信号 factor = 1、offset = 0，因此数值 0/1/2/3 与原始值一致。

脚本对长度不匹配的目标报文计数后跳过。这个计数不包含其他类型的解码错误；当前教学脚本若遇到其他解码异常，会直接报错，而不是静默跳过。

## 5. 本次解码结果及解释

在项目根目录运行：

```bash
python3 exercises/stage4/decode_peb.py
```

本次输出：

```text
教学假设：通道 1 的 0x325 按 BKPCANFD DBC 解释
时间=0.000000s  Byte16=0x3F  PEBSwReq=0  无请求
时间=7.155476s  Byte16=0x7F  PEBSwReq=1  开启请求
时间=7.470235s  Byte16=0x3F  PEBSwReq=0  无请求

成功解析条数：175
No_Request条数：166
ON条数：9
长度不匹配条数：0
```

这表示：按上述假设解释，175 条成功解析的目标报文中，`PEBSwReq` 有 166 条为 0（无请求），9 条为 1（开启请求）。

- 只打印首次状态和状态变化，是因为程序按状态变化打印；不是只解析了这些条目。
- 目标信号不变，不代表报文中其他信号或字节不变。
- 166 条无请求和 9 条开启请求是报文观测次数，不是独立事件次数。
- 没有观察到请求，不等于能排除采样记录之外发生过请求。
- 解码成功不等于已经确认网络、版本和信号语义完全匹配。
- 请求状态本身也不能证明对应动作已经执行。

## 6. 导出每条解析结果为 CSV

输出文件：[peb_channel1.csv](../output/stage4/peb_channel1.csv)

同时生成状态曲线：[peb_channel1.png](../output/stage4/peb_channel1.png)。横轴是相对第一条目标报文的时间，纵轴是 `PEBSwReq` 原始枚举值；脚本使用阶梯线表示离散状态变化，并保留 0/1/2/3 的完整枚举刻度。绘图使用 Pillow 直接生成 PNG，不依赖 Matplotlib。

脚本对每条成功解析的报文执行 `rows.append(...)`，这一步位于状态变化判断之外，因此 CSV 包含所有成功解析结果，而不仅是变化点。

| CSV 列 | 含义 |
|---|---|
| `timestamp` | 原始 Unix 时间戳，以六位小数格式写入 |
| `elapsed_s` | 距第一条成功解析的目标报文的秒数 |
| `channel` | 采集通道，本次为 1 |
| `can_id` | 十六进制 ID，本次为 `0x325` |
| `PEBSwReq` | 解码后的数值，本次为 0 或 1 |
| `state` | 状态文字，本次为 `No_Request` 或 `ON` |

实际文件前几行：

```csv
timestamp,elapsed_s,channel,can_id,PEBSwReq,state
1792129038.334223,0.000000,1,0x325,0,No_Request
1792129038.434213,0.099991,1,0x325,0,No_Request
1792129038.534290,0.200067,1,0x325,0,No_Request
```

相对时间零点是第一条成功解析的目标报文，不是整个 BLF 的起点。时间戳和相对时间分别格式化，小数末位可能因舍入产生差异。

导出代码使用：

```python
output_path.parent.mkdir(parents=True, exist_ok=True)

with output_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=...)
    writer.writeheader()
    writer.writerows(rows)
```

其中 `fieldnames=...` 是说明性占位，完整可运行代码见脚本。

- `mkdir` 自动创建输出目录。
- `DictWriter` 按指定列名写入字典数据。
- `writeheader()` 写表头，`writerows(rows)` 写数据。
- `newline=""` 由 CSV 模块处理换行。
- `"w"` 模式会覆盖已有同名文件。
- 当前先把结果保存在列表里，适合这个小练习；大日志可以改为逐条解码、逐条写入。

本次导出 175 行数据，另加一行表头，与成功解析条数一致。CSV 本身没有保存 DBC 路径和映射假设，使用或分享结果时应同时保留本章中的解析前提。

## 7. 阶段完成情况

四个阶段已经走通：

```text
读取原始报文 → 理解字节和位 → 阅读 DBC
    → 解码真实日志 → 统计状态 → 导出 CSV
```

后续可以在确认通道映射的基础上，扩展多个信号、其他 DBC、时间对齐和曲线绘制。本次完成的是单通道、单报文中的单个目标信号分析，不代表全部车辆信号已验证。
