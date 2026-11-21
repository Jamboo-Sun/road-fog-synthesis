# Road Fog Synthesis · 道路图像雾合成

为道路 RGB 图像批量生成轻雾、中雾和浓雾。这个 Codex skill 也可以作为独立的 Python 命令行工具使用。输出保持原图尺寸和像素坐标，支持复制 YOLO 标注，适合道路坑洼检测的合成雾压力测试和训练数据增强。

A Codex skill and Python CLI for generating three levels of synthetic fog from road images. It preserves the pixel grid, optionally copies paired YOLO labels, and records rendering parameters in a manifest.

## 安装

需要 Python 3.10 或更新版本。从本仓库根目录运行：

```sh
python -m pip install -r requirements.txt
```

作为 Codex skill 使用时，将仓库克隆或解压到 `~/.codex/skills/road-fog-synthesis`，确保 `SKILL.md` 位于该目录根部。用 `$road-fog-synthesis` 调用，例如“给这批道路图片合成轻、中、浓三档雾，保留 YOLO 标注”。[技能说明](SKILL.md)

## 快速开始

只有 RGB 时，可以先按图像行位置近似远近，生成预览：

```sh
python scripts/synthesize_fog.py --images road.jpg --row-proxy --output fog-preview
```

有相对深度图时，批量合成并复制标注：

```sh
python scripts/synthesize_fog.py --images data/images/test --depth-dir data/depth/test --depth-unit relative --labels data/labels/test --output data/fog-test
```

输入 `images/test/scene/road.jpg` 对应 `depth/test/scene/road.npy` 和 `labels/test/scene/road.txt`。深度图是与图像同高同宽的二维 NumPy 数组。相对深度需归一化到 `[0, 1]`，近为 0，远为 1。输入是以米表示的距离时，改用 `--depth-unit meters`。使用 `python scripts/synthesize_fog.py --help` 查看强度和大气光参数。

```text
fog-test/
├── light/       # images/ 和可选的 labels/
├── medium/
├── heavy/
└── manifest.json
```

图像输出为 PNG。指定标注目录时，每张图片需有对应的 `.txt`，无目标样本可用空文件。输出目录必须是新目录。不同雾级的坐标一致，浓雾下仍建议检查坑洼是否可辨。

## 方法与适用范围

脚本以 `t = exp(-β × d)` 计算单像素透射率，在线性 RGB 中合成 `I_fog = I_clear × t + A × (1 - t)`。米制距离模式默认 β 为 0.005、0.01、0.02 m⁻¹。相对深度和预览模式使用无量纲强度，默认 0.25、0.5、1.0。

这是对基本大气散射公式的独立实现。深度图需由调用方提供。只有 RGB 时的行位置近似适合预览。均匀大气光假设适用于合成扰动，实际夜间灯光散射和真实雾天表现需要实拍数据验证。

实验建议固定原始样本、划分和各档参数，记录深度来源及归一化规则。雾化测试报告中注明合成雾，并单独报告各档结果。发布运行产物时，请留意 `manifest.json` 会记录本机输入目录。

## 验证

```sh
python -m unittest discover -s tests -v
```

测试使用程序生成的样图和标注，验证三档输出、尺寸、标注文件和深度不匹配时的处理。

## 参考与许可

- Sakaridis, C., Dai, D., & Van Gool, L. (2018). *Semantic Foggy Scene Understanding with Synthetic Data*. International Journal of Computer Vision. [出版页面](https://doi.org/10.1007/s11263-018-1072-8) · [Foggy Cityscapes 参数说明](https://people.ee.ethz.ch/~csakarid/SFSU_synthetic/)

本仓库的技能和 Python 实现采用 [MIT 许可证](LICENSE)。引用对应论文可说明雾合成模型和参数的来源。
