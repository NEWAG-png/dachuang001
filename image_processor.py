import cv2
import numpy as np
import matplotlib.pyplot as plt

def extract_spectrum_master(image_path):
    """
    终极完全体：全色自适应 + 抗刻度干扰 + 多重防呆
    兼容任意颜色曲线，且能处理带网格、带刻度的复杂图表
    """
    # 1. 读取图片
    img = cv2.imread(image_path)
    if img is None:
        return None, None, "❌ 无法读取图片，请检查路径"

    h, w = img.shape[:2]
    
    # === 防御层 1：安全裁剪 (抗刻度/边框干扰) ===
    # 无论什么颜色，坐标轴刻度通常都在边缘。
    # 切除 5% 边缘，物理消灭 99% 的刻度线和轴标题干扰。
    margin_y = int(h * 0.05)
    margin_x = int(w * 0.05)
    
    # 防止图片太小切没了
    if margin_y >= h//2 or margin_x >= w//2:
        roi = img
    else:
        roi = img[margin_y:h-margin_y, margin_x:w-margin_x]

    # === 核心层：全色自适应提取 ===
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    # 创建掩膜：排除黑白灰（低饱和度）和纯黑纯白（极低/极高亮度）
    # S > 40 保证是彩色，V > 40 排除太暗的噪点
    mask_color = cv2.inRange(hsv_roi, 
                             np.array([0, 40, 40]), 
                             np.array([180, 255, 255]))

    # === 防御层 2：连通域清洗 (抗网格/噪点) ===
    # 无论什么颜色，曲线通常是图中面积最大的色块。
    # 网格线、文字噪点面积小，直接过滤掉。
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_color, connectivity=8)
    
    if num_labels <= 1:
        return None, None, "❌ 未检测到有效彩色曲线（可能是黑白图或背景太杂）"

    # 找到面积最大的那个组件（排除背景 label=0）
    # stats[:, cv2.CC_STAT_AREA] 获取所有组件面积
    areas = stats[1:, cv2.CC_STAT_AREA] 
    if len(areas) == 0:
        return None, None, "❌ 图像中无有效内容"
        
    max_label = np.argmax(areas) + 1  # +1 是因为去掉了背景
    curve_mask = (labels == max_label).astype(np.uint8) * 255

    # === 数据提取层：垂直投影找中心线 ===
    # 这一步能把有宽度的线条变成单像素数据线，且自带平滑效果
    ys, xs = np.where(curve_mask > 0)
    if len(xs) == 0:
        return None, None, "❌ 提取失败，未找到连续曲线"

    # 按 X 坐标分组，取每列 Y 的中位数（比平均值更抗噪）
    x_unique = np.unique(xs)
    y_center = np.zeros_like(x_unique, dtype=float)
    
    for i, x_val in enumerate(x_unique):
        col_ys = ys[xs == x_val]
        y_center[i] = np.median(col_ys)

    # 还原到原图坐标系 (加上裁剪掉的 margin)
    y_final = y_center + margin_y
    x_final = x_unique + margin_x

    return x_final, y_final, "✅ 提取成功"

# === 测试代码 ===
if __name__ == "__main__":
    # 这里替换成你的图片路径
    path = "spectrum_test.jpg" 
    
    x_data, y_data, msg = extract_spectrum_master(path)
    print(msg)
    
    if x_data is not None:
        plt.figure(figsize=(10, 6))
        plt.plot(x_data, y_data, 'b-', linewidth=1)
        plt.gca().invert_yaxis() # 光谱图通常 Y 轴向下
        plt.title("Cleaned Spectrum (Auto-Color)")
        plt.grid(True)
        plt.show()