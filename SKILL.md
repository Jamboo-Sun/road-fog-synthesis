---
name: road-fog-synthesis
description: 为道路 RGB 图像合成可控浓度的雾，用于坑洼检测数据增强或合成雾压力测试。适用于加雾、雾化、晴天转雾天和批量生成轻中重雾。
---

# 道路图像雾合成

使用 `scripts/synthesize_fog.py` 对单张或整目录图像生成轻、中、重三档合成雾。脚本在原像素网格上用距离控制透射率 `t = exp(-beta * depth)`，在线性 RGB 中混合原图与均匀大气光，输出 PNG 和 `manifest.json`。依赖 Python 3.10+、NumPy 和 Pillow。

- **米制距离图**：使用 `--depth-dir` 和 `--depth-unit meters`。默认消光系数 0.005、0.01、0.02 m⁻¹，参考 [Foggy Cityscapes 的 IJCV 论文](https://doi.org/10.1007/s11263-018-1072-8)及其[数据参数说明](https://people.ee.ethz.ch/~csakarid/SFSU_synthetic/)。此脚本独立实现散射公式，直接读取调用者提供的距离图。
- **相对深度图**：使用 `--depth-unit relative`。先将深度按有记录的规则转换到 [0,1]，近为 0，远为 1。逆深度需反向。默认强度为 0.25、0.5、1.0，均无量纲。记录估计器和归一化方法。
- **只有 RGB**：使用 `--row-proxy` 快速预览。它假设上方偏远、下方偏近，输出会标记为预览。定量实验优先提供深度图。

在技能目录运行：

```text
python scripts/synthesize_fog.py --images path/to/example.jpg --row-proxy --output path/to/fog_preview
python scripts/synthesize_fog.py --images path/to/images/test --depth-dir path/to/depth/test --depth-unit relative --labels path/to/labels/test --output path/to/fog_test
```

`scene/image.jpg` 对应 `scene/image.npy` 和 `scene/image.txt`，三者使用相同的相对目录和文件名。深度文件是与图像同高同宽的二维数组，值有限且非负。`--labels` 可选，用于逐字节复制 YOLO 标注，空文件表示无目标。输出写入新目录，结构为 `light|medium|heavy/images` 及对应的 `labels`。用 `--levels` 和 `--airlight` 覆盖三档强度和 sRGB 大气光，详见 `--help`。

批量处理前检查样图的近远雾效、坑洼轮廓和目标可见性。框坐标保持不变，浓雾下仍需检查目标是否可辨。做评估时在原测试集上生成配对扰动，固定每档参数并单独汇报各档结果。做训练增强时只处理训练划分。夜间结果表述为“合成雾扰动”。模型采用均匀大气光，真实夜雾和车灯光晕需要独立验证。
