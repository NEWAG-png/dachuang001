import cv2
import numpy as np
from scipy.interpolate import interp1d
# 1.核心清洗函数
def clean_and_parse_data(raw_data):
    """兼容两种输入格式：
      - dict: {'wavenumbers': [...], 'intensities': [...]}
      - list: [[x1, y1], [x2, y2], ...]
    """
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
    #排序
    sorted_pairs = sorted(zip(w_list, i_list))
    w_sorted, i_sorted = zip(*sorted_pairs)
    #去重
    unique_w, unique_i = [], []
    if len(w_sorted) > 0:
        cur_w = w_sorted[0]
        cur_i_sum = i_sorted[0]
        cur_i_cnt = 1
        for j in range(1, len(w_sorted)):
            if w_sorted[j] - cur_w > 1e-6:
                unique_w.append(cur_w)
                unique_i.append(cur_i_sum / cur_i_cnt)
                cur_w = w_sorted[j]
                cur_i_sum = i_sorted[j]
                cur_i_cnt = 1
            else:
                cur_i_sum += i_sorted[j]
                cur_i_cnt += 1
        unique_w.append(cur_w)
        unique_i.append(cur_i_sum / cur_i_cnt)
    #插值对齐到1000个点
    num_points = 1000
    x_new = np.linspace(min(unique_w), max(unique_w), num_points)
    f = interp1d(unique_w, unique_i, kind='linear', fill_value="extrapolate")
    y_new = f(x_new)
    return x_new, y_new
#2.像素坐标清洗函数
def clean_pixel_data(pixel_x, pixel_y):
    """像素坐标数据去噪、去重、排序
    输入：原始像素坐标数组
    输出：清洗后的 (x, y) 数组
    """
    pixel_x = np.asarray(pixel_x, dtype=float)
    pixel_y = np.asarray(pixel_y, dtype=float)
    #按x排序
    sort_idx = np.argsort(pixel_x)
    pixel_x = pixel_x[sort_idx]
    pixel_y = pixel_y[sort_idx]
    #去除重复x值,取平均y,避免曲线粗细导致同一x有多个y
    unique_x = []
    unique_y = []
    if len(pixel_x) > 0:
        current_x = pixel_x[0]
        current_y_sum = pixel_y[0]
        current_y_count = 1
        for i in range(1, len(pixel_x)):
            if abs(pixel_x[i] - current_x) > 0.5:
                unique_x.append(current_x)
                unique_y.append(current_y_sum / current_y_count)
                current_x = pixel_x[i]
                current_y_sum = pixel_y[i]
                current_y_count = 1
            else:
                current_y_sum += pixel_y[i]
                current_y_count += 1
        unique_x.append(current_x)
        unique_y.append(current_y_sum / current_y_count)
    return np.array(unique_x), np.array(unique_y)
#3.光谱图片曲线提取
def extract_spectrum_master(image_path):
    """
    V7.0 融合版：专治带坐标轴的标准光谱图
    融合改进点：
      旧版：自动定位并切除坐标轴
      本版：Otsu自适应阈值 + 形态学开运算去噪
      旧版：每列至少3个黑点才认为是曲线
      本版：全像素中心线提取 + 边缘区域过滤
    返回：(pixel_x, pixel_y, message)
    """
    img = cv2.imread(image_path)
    if img is None:
        return None, None, "无法读取图片"
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    #找Y轴
    col_sum = np.sum(binary, axis=0)
    search_range_w = int(w * 0.2)
    y_axis_x = np.argmax(col_sum[:search_range_w])
    #找X轴
    row_sum = np.sum(binary, axis=1)
    search_range_h = int(h * 0.8)
    x_axis_y = np.argmax(row_sum[search_range_h:]) + search_range_h
    #安全校验
    if y_axis_x > w * 0.3:
        y_axis_x = int(w * 0.05)
    if x_axis_y < h * 0.5:
        x_axis_y = int(h * 0.95)
    #裁剪出纯净的绘图区
    padding = 5
    roi_x_start = y_axis_x + padding
    roi_y_end = x_axis_y - padding
    if roi_x_start >= w or roi_y_end <= 0:
        return None, None, "❌ 坐标轴检测异常，请确保图片包含完整坐标轴"
    roi_gray = gray[0:roi_y_end, roi_x_start:w]
    r_h, r_w = roi_gray.shape
    _, roi_bin = cv2.threshold(roi_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    roi_bin = cv2.morphologyEx(roi_bin, cv2.MORPH_OPEN, kernel, iterations=1)
    pixel_x_list = []
    pixel_y_list = []
    for x in range(r_w):
        col_data = roi_bin[:, x]
        black_indices = np.where(col_data > 0)[0]

        #过滤噪点
        if len(black_indices) >= 3:
            y_pos = np.mean(black_indices)
            # 还原为原图坐标
            pixel_x_list.append(x + roi_x_start)
            pixel_y_list.append(y_pos)
    if not pixel_x_list:
        return None, None, "未检测到有效曲线，请确保图片中曲线清晰可见"
    pixel_x = np.array(pixel_x_list)
    pixel_y = np.array(pixel_y_list)
    margin_x = int(w * 0.03)
    margin_y = int(h * 0.03)
    mask = (
        (pixel_x >= margin_x) & (pixel_x <= w - margin_x) &
        (pixel_y >= margin_y) & (pixel_y <= roi_y_end - margin_y)
    )
    pixel_x = pixel_x[mask]
    pixel_y = pixel_y[mask]
    if len(pixel_x) < 50:
        return None, None, "❌ 提取到的有效像素点太少，请确保图片中曲线区域清晰"
    return pixel_x, pixel_y, "✅ 像素提取成功"
def pixels_to_real_data(pixel_x, pixel_y,
                        real_x_range=(0, 4000),
                        real_y_range=None):
    """
    将像素坐标转换为真实光谱数据
    参数：
        pixel_x: X轴像素坐标数组
        pixel_y: Y轴像素坐标数组
        real_x_range: (x_min, x_max) 真实X轴范围，默认 (0, 4000) 适配FTIR
        real_y_range: (y_top, y_bottom) 真实Y轴范围，默认 None 自动推断
    返回：
        (wavenumbers, intensities, message)
    """
    if len(pixel_x) == 0:
        return None, None, "❌ 没有提取到有效像素点"
    #1.清洗数据
    clean_x, clean_y = clean_pixel_data(pixel_x, pixel_y)
    if clean_x is None or len(clean_x) < 10:
        return None, None, "❌ 有效数据点不足，无法完成转换"
    #2.X轴映射
    min_px = np.min(clean_x)
    max_px = np.max(clean_x)
    if max_px == min_px:
        return None, None, "X轴提取范围异常"
    real_x = real_x_range[0] + (clean_x - min_px) / (max_px - min_px) * (real_x_range[1] - real_x_range[0])
    #3.Y轴映射
    min_py = np.min(clean_y)
    max_py = np.max(clean_y)
    if (max_py - min_py) < 10:
        return None, None, "⚠️ 提取到的曲线过于平直"
    if real_y_range is None:
        y_top_val = 100.0
        y_bot_val = 0.0
    else:
        y_top_val = real_y_range[0]
        y_bot_val = real_y_range[1]
    #（翻转）
    real_y = y_top_val - (clean_y - min_py) / (max_py - min_py) * (y_top_val - y_bot_val)
    # 4. 打包数据，统一清洗
    raw_dict = {
        'wavenumbers': real_x.tolist(),
        'intensities': real_y.tolist()
    }
    final_w, final_i = clean_and_parse_data(raw_dict)
    if final_w is not None:
        return final_w, final_i, "✅ 数据转换成功"
    else:
        return None, None, "❌ 数据清洗失败"