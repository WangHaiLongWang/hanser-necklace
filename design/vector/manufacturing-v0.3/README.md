# HN-PENDANT result_02 制造矢量草案 v0.3

生成日期：2026-10-13

## 输入审计

- `result_02.png` SHA-256：`39CDEFD9762710FB95CFF87931111C2631BCB5A4BE8BB404C7D2F1CCCB78773D`。
- `result_02.psd` SHA-256：`C62405866B2052A2042E771AC75BEDE3CCB2218A325B72A992281706B53DD9AC`。
- PSD 为 0 图层的完全扁平合成文件，其合成像素与 PNG 完全一致；本版属于重新分区重建，不是原图层无损提取。

## 输出

- `HN-PENDANT-RESULT02-v0.3.svg`：后续人工细化母版。
- `HN-PENDANT-RESULT02-v0.3.dxf`：毫米单位分层封闭轮廓。
- `HN-PENDANT-RESULT02-PREVIEW-v0.3.png`：从同一几何分区渲染的五色预览。
- `HN-PENDANT-RESULT02-COMPARISON-v0.3.png`：源图与简化结果对照。

## 几何与最小特征

- 名义图案尺寸：高 `40.00 mm`，宽 `28.36 mm`，不含吊环。
- 目标金属分隔宽度：约 `0.35 mm`。
- 目标最小保留特征：约 `0.50 mm`。
- 小于阈值的发丝、高光、鞋带缝、衣褶和指缝已合并或删除。
- 原粉色毛怪爱心已归入蓝色层；所有灰色眼睛、五官和结构线归入凸起金属层。

## 色层统计

| 图层 | 闭合轮廓数 | 面积估算 mm² |
|---|---:|---:|
| FILL_SKIN | 8 | 41.07 |
| FILL_WHITE | 22 | 183.49 |
| FILL_HAIR | 3 | 132.56 |
| FILL_BLUE | 12 | 44.97 |
| RAISED_METAL | 46 | 252.45 |

## 后续修改流程

1. 复制 SVG 并升版，不覆盖 v0.3。
2. 在矢量软件中按 `FILL_*` / `RAISED_METAL_DETAILS` 图层调整节点。
3. 保持所有色块闭合、无自交、无重叠，相邻颜色间保留连续金属网。
4. 在 1:1 的 40 mm 视图检查手指、眼睛、鞋子和毛怪表情。
5. 执行 `python scripts/svg_layers_to_dxf.py 输入.svg 输出.dxf` 重新生成 DXF。
6. CAD 中确认单位为 mm、轮廓全部闭合后再交工厂 DFM。

本文件仍缺吊环、背面、厚度、凹槽深度、毛怪连接和公差，不可直接开模。
