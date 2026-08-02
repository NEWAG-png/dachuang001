# utils.py
import numpy as np
from scipy import interpolate

def clean_and_parse_data(raw_data):
    """
    解析并清洗光谱数据，统一为 1000 个点以便计算
    """
    w_list = []
    i_list = []

    # 兼容字典格式 {'wavenumbers': [], 'intensities': []}
    if isinstance(raw_data, dict):
        raw_w = raw_data.get('wavenumbers', [])
        raw_i = raw_data.get('intensities', [])
        for w, i in zip(raw_w, raw_i):
            try:
                w_list.append(float(w))
                i_list.append(float(i))
            except ValueError:
                continue
    
    # 兼容列表格式 [[w, i], [w, i]]
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

    # 插值对齐到 1000 个点 (这是为了统一长度)
    num_points = 1000
    x_new = np.linspace(min(w_sorted), max(w_sorted), num_points)
    
    # 使用线性插值
    f = interpolate.interp1d(w_sorted, i_sorted, kind='linear', fill_value="extrapolate")
    y_new = f(x_new)

    return x_new, y_new

def calculate_euclidean_distance(vec1, vec2):
    """
    计算欧氏距离 (数值越小越相似)
    vec1, vec2: 强度数组 (numpy array)
    """
    # 简单的欧氏距离公式: sqrt(sum((a-b)^2))
    # 这里我们不做归一化，保留原始强度的差异敏感性
    diff = vec1 - vec2
    distance = np.sqrt(np.sum(diff ** 2))
    return distance