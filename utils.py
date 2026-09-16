import numpy as np
from scipy import interpolate
import cv2

# ==========================================
# 1. 核心清洗函数 (主程序启动依赖这个，千万别删)
# ==========================================

def clean_and_parse_data(raw_data):
    """解析并清洗光谱数据，统一为 1000 个点以便计算"""
    w_list, i_list = [], []

    if isinstance(raw_data, dict):
        raw_w = raw_data.get('wavenumbers', [])
        raw_i = raw_data.get('intensities', [])
        for w, i in zip(raw_w, raw_i):
            try:
                w_list.append(float(w))
                i_list.append(float(i))
            except ValueError:
                continue
    elif isinstance(raw_data, list):
        for item in raw_data:
            if len(item) >= 2:
                try:
                    w_list.append(float(item[0]))
                    i_list.append(float(item[1]))
                except ValueError:
                    continue

    if not w_list:
        return None, None

    # 排序（防止波数乱序）
    sorted_pairs = sorted(zip(w_list, i_list))
    w_sorted, i_sorted = zip(*sorted_pairs)

    # 插值对齐到 1000 个点
    num_points = 1000
    x_new = np.linspace(min(w_sorted), max(w_sorted), num_points)
    f = interpolate.interp1d(w_sorted, i_sorted, kind='linear', fill_value="extrapolate")
    y_new = f(x_new)

    return x_new, y_new


# ==========================================
# 2. 核心工具函数 (完全保留你原有的逻辑)
# ==========================================

def extract_spectrum_master(image_path):
    """
    V6.0 终极手术刀版：专治带坐标轴的标准图
    1. 自动定位并切除坐标轴。
    2. 逐列扫描提取曲线中心线。
    3. 兼容原有主程序的返回值格式。
    """
    img = cv2.imread(image_path)
    if img is None:
        return None, None, "❌ 无法读取图片"

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # ==========================================
    # 第一步：自动寻找并切除坐标轴
    # ==========================================
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # 找 Y轴 (左侧垂直长线)
    col_sum = np.sum(binary, axis=0)
    search_range_w = int(w * 0.2)
    y_axis_x = np.argmax(col_sum[:search_range_w])
    
    # 找 X轴 (底部水平长线)
    row_sum = np.sum(binary, axis=1)
    search_range_h = int(h * 0.8) 
    x_axis_y = np.argmax(row_sum[search_range_h:]) + search_range_h

    # 安全校验
    if y_axis_x > w * 0.3: y_axis_x = int(w * 0.05)
    if x_axis_y < h * 0.5: x_axis_y = int(h * 0.95)

    # 裁剪出纯净的绘图区 (ROI)
    padding = 5 
    roi_x_start = y_axis_x + padding
    roi_y_end = x_axis_y - padding
    
    if roi_x_start >= w or roi_y_end <= 0:
        return None, None, "❌ 坐标轴检测异常"

    roi_gray = gray[0:roi_y_end, roi_x_start:w]
    _, roi_bin = cv2.threshold(roi_gray, 180, 255, cv2.THRESH_BINARY_INV)
    
    # ==========================================
    # 第二步：逐列扫描提取曲线 (核心降维打击)
    # ==========================================
    r_h, r_w = roi_gray.shape
    pixel_x_list = []
    pixel_y_list = []
    
    for x in range(r_w):
        col_data = roi_bin[:, x]
        black_indices = np.where(col_data > 0)[0]
        
        # 过滤噪点：一列至少要有3个黑点才认为是曲线
        if len(black_indices) >= 3:
            y_pos = np.mean(black_indices)
            # 还原为原图坐标
            pixel_x_list.append(x + roi_x_start)
            pixel_y_list.append(y_pos)
            
    if not pixel_x_list:
        return None, None, "❌ 未检测到有效曲线"

    pixel_x = np.array(pixel_x_list)
    pixel_y = np.array(pixel_y_list)

    return pixel_x, pixel_y, "✅ 像素提取成功(已去坐标轴)"


def pixels_to_real_data(pixel_x, pixel_y, 
                        real_x_range=(0, 4000),  # 【修改点】改为从左到右递增，适配你的图
                        real_y_range=None):
    """
    【核心修复版】解决深峰触底和直线问题
    强制规范 Y 轴映射逻辑，防止因基线过平导致的数值坍塌
    """
    if len(pixel_x) == 0:
        return None, None, "❌ 没有提取到有效像素点"

    min_px = min(pixel_x)
    max_px = max(pixel_x)
    
    # 防止除以零
    if max_px == min_px:
        return None, None, "❌ X轴提取范围异常"
        
    # 1. X轴映射 
    # 现在的逻辑：pixel_x 越小(左边) -> 对应 real_x_range[0] (0)
    #           pixel_x 越大(右边) -> 对应 real_x_range[1] (4000)
    # 这样就和你的图片（左0右4000）完美对应了！
    real_x = real_x_range[0] + (pixel_x - min_px) / (max_px - min_px) * (real_x_range[1] - real_x_range[0])

    # 2. Y轴映射 (保持不变，逻辑是正确的)
    min_py = min(pixel_y)
    max_py = max(pixel_y)
    
    if (max_py - min_py) < 10: 
        return None, None, "⚠️ 提取到的曲线过于平直"

    if real_y_range is None:
        y_top_val = 100.0 
        y_bot_val = 0.0
    else:
        y_top_val = real_y_range[0] 
        y_bot_val = real_y_range[1] 

    real_y = y_top_val - (pixel_y - min_py) / (max_py - min_py) * (y_top_val - y_bot_val)
    
    # 3. 打包数据
    raw_dict = {
        'wavenumbers': real_x.tolist(),
        'intensities': real_y.tolist()
    }
    
    final_w, final_i = clean_and_parse_data(raw_dict)
    
    if final_w is not None:
        return final_w, final_i, "✅ 数据转换成功"
    else:
        return None, None, "❌ 数据清洗失败"