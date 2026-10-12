# 图像工作区

- `result.png`：`CONCEPT-v0.1` 外观预览基线。
- `result.psd`：对应可编辑工作源文件，不直接发给工厂覆盖修改。
- `openai_*.png`：生成与迭代过程记录，不是生产依据。
- 其他 JPG/PNG：姿势、角色、毛怪和同类项链参考。

任何新修改应另存为 `result-v02.psd/png` 等新文件，并在 `changes/CHANGELOG.md` 登记。不要覆盖已经登记哈希的 `result.png` 和 `result.psd`。

工厂对外发布包应从 PSD 整理成受控 SVG/DXF/PDF，放入 `design/release/<版本>/`；不要让工厂从过程图中自行选择生产版本。

