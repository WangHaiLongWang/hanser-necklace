# HN-PENDANT result_02 加工矢量 v0.8-80mm-engineering

生成日期：2026-10-13

## 源文件审计

- `result_02.svg` SHA-256：`0CB52004A8921431491DF6E040F0847416DA639573C74DE14EA2F2AEECC0DDB2`。
- `result_02.psd` SHA-256：`FE1D7F78D31334F9CF3D66970175A407F28D2D628721886CE040FD5BB560EB69`。
- SVG 画布：`1023 × 1538`，包含 5 个嵌入式 PNG 图层，包含 0 条 SVG path。
- SVG 的 5 个嵌入图与 PSD 子图层逐一对应；按顺序合成后与 PSD 合成像素完全一致。
- 因源 SVG 仍是位图容器，本版使用各层 Alpha 和颜色语义重建闭合路径；不是对现有 path 的直接转换。

## 加工输出

- `HN-PENDANT-RESULT02-v0.8-80mm-engineering.svg`：毫米尺寸、分层闭合路径的加工母版。
- `HN-PENDANT-RESULT02-v0.8-80mm-engineering.dxf`：R2010、毫米单位、分层闭合 LWPOLYLINE。
- `HN-PENDANT-RESULT02-PREVIEW-v0.8-80mm-engineering.png`：由加工几何渲染的工艺分色预览。
- `HN-PENDANT-RESULT02-COMPARISON-v0.8-80mm-engineering.png`：源合成图与加工结果对照。
- `HN-PENDANT-RESULT02-SOURCE-LAYERS-v0.8-80mm-engineering.png`：5 个源图层的可视化审计。
- `HN-PENDANT-RESULT02-LAYERS-v0.8-80mm-engineering.csv`：加工图层、参考色和闭合轮廓数量。
- `layers/*.dxf`：每个加工层单独导出的毫米 DXF。

## 几何规则

- 名义图案高度：`80.00 mm`，宽度：`56.72 mm`，不含吊环。
- 目标金属分隔宽度：约 `0.30 mm`。
- 外轮廓金属边名义宽度：`0.60 mm`。
- 本版关闭最小特征删除，保留源图层中的全部可识别细节；工厂需在 DFM 中标注不能加工的区域。
- 肤色、蓝色、爱心和头发由各自源图层 Alpha 提取；白色从人物轮廓内的中性浅色恢复。
- 爱心独立为 `FILL_HEART`，参考色 `#EA6278`；灰色描边、人物眼眉和毛怪五官归入凸起金属层。
- 全细节模式不执行形态开闭、最小面积过滤或色块侵蚀；发丝、鞋带、衣褶和指缝按源图层保留。

## 图层统计

| 图层 | 闭合轮廓数 | 面积估算 mm² |
|---|---:|---:|
| FILL_SKIN | 20 | 204.68 |
| FILL_WHITE | 51 | 729.71 |
| FILL_HAIR | 3 | 618.78 |
| FILL_BLUE | 20 | 247.48 |
| FILL_HEART | 1 | 4.53 |
| RAISED_METAL | 107 | 813.03 |

## 下单前仍需完成

- 工厂确认最小金属隔断、填色区、凹槽深度和允许圆角后，重新偏置最终路径。
- 增加吊环、背面、厚度、重心、毛怪连接/转轴和公差图。
- 1:1 打印并确认 80 mm 下手指、眼睛、鞋子和毛怪五官可读。
- 当前文件可用于 DFM 与询价，不可未经工厂回签直接开模。

## v0.8 冻结截面参数

- 总厚度：1.90 mm。
- 正面凹刻/填色槽深度：0.30 mm。
- 凹刻后剩余基底厚度：1.60 mm。
- 内部凸起金属分隔线：名义 0.30 mm。
- 外轮廓金属边：名义 0.60 mm，允许范围 0.50-0.70 mm。
- `HN-PENDANT-SECTION-v0.8.svg/dxf` 为示意截面，工程方需转成正式带公差图纸并回签。
