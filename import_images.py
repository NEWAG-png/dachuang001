import os
import sqlite3
import json
import sys
import re
import numpy as np
from utils import extract_spectrum_master, pixels_to_real_data

DB_PATH = 'spectrum_data.db'
IMAGE_FOLDER = 'FTIR_standard_images'

def clean_filename(filename):
    """
    智能提取物质名称并清洗格式
    例如：'Beeswax(natural)_FTIR.png' -> 'Beeswax (natural)'
    """
    base_name = os.path.splitext(filename)[0]
    # 1. 强制替换所有下划线和括号前的空格为空格
    base_name = base_name.replace('_', ' ')
    # 2. 智能处理括号前的空格，确保格式统一（如：Casein_FTIR -> Casein）
    # 去掉文件名末尾残留的 '_FTIR' 等后缀
    base_name = re.sub(r'_FTIR$', '', base_name, flags=re.IGNORECASE).strip()
    # 3. 把 (natural) 这种紧挨着的括号前面加个空格，美化一下
    base_name = re.sub(r'(\w)\(', r'\1 (', base_name)
    return base_name

def import_single_image(cursor, img_path, img_name):
    """
    安全提取单张图片数据并入库
    """
    print(f"  [提取] 正在分析图片: {img_name} ...")
    
    # 1. 提取像素曲线
    pixel_x, pixel_y, msg = extract_spectrum_master(img_path)
    if pixel_x is None:
        print(f"    ⚠️ 警告: {msg}，跳过此图片。")
        return False

    # 2. 像素转换为物理数据（波数, 强度）
    # 这里使用了通用的 FTIR 范围 (0 - 4000)，如果有特殊范围可修改
    real_w, real_i, msg2 = pixels_to_real_data(pixel_x, pixel_y, real_x_range=(0, 4000))
    
    if real_w is None:
        print(f"    ⚠️ 警告: {msg2}，跳过此图片。")
        return False

    # 3. 格式化数据为字符串
    material_name = clean_filename(img_name)
    wavenumbers_json = json.dumps(real_w.tolist())
    intensities_json = json.dumps(real_i.tolist())

    # 4. 插入数据库 (带防重复保护: IGNORE)
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO spectra 
            (spectrum_name, spectrum_type, source_tag, wavenumbers, intensities) 
            VALUES (?, ?, ?, ?, ?)
        """, (material_name, 'FTIR', 'IMAGE_IMPORT', wavenumbers_json, intensities_json))
        print(f"    ✅ 成功: 物质【{material_name}】已成功入库！")
        return True
    except Exception as e:
        print(f"    ❌ 失败: 数据库插入报错 -> {e}")
        return False

def run_import(test_mode=True):
    """
    主导入逻辑
    test_mode=True: 只导入前3张图做测试 (推荐先跑这个)
    test_mode=False: 导入文件夹内所有图片
    """
    if not os.path.exists(DB_PATH):
        print(f"❌ 错误: 找不到数据库文件 {DB_PATH}")
        return

    if not os.path.exists(IMAGE_FOLDER):
        print(f"❌ 错误: 找不到图片文件夹 {IMAGE_FOLDER}")
        return

    png_files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith('.png')]
    
    if not png_files:
        print("⚠️ 文件夹里没有 .png 格式的图片！")
        return

    # 如果是测试模式，只取前 3 张图
    if test_mode:
        print(f"🚀 进入【测试模式】，将只导入前 3 张图片进行验证...")
        png_files = png_files[:3]
    else:
        print(f"🚀 进入【全量模式】，共找到 {len(png_files)} 张图片，开始批量导入...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    success_count = 0
    for f in png_files:
        img_path = os.path.join(IMAGE_FOLDER, f)
        if import_single_image(cursor, img_path, f):
            success_count += 1

    conn.commit()
    conn.close()

    print("\n" + "="*50)
    if test_mode:
        print(f"🏁 测试完毕！测试导入数量: {success_count} / {len(png_files)}")
        print("👉 检查完结果确认无误后，请修改代码 `run_import(test_mode=True)` 为 `False` 再跑一次！")
    else:
        print(f"🏁 导入结束！共成功导入 {success_count} 张图片数据。")
    print("="*50)

if __name__ == "__main__":
    # ==========================================
    # ⚠️ 注意：初次测试请保持 True，确认没问题后改为 False
    # ==========================================
    run_import(test_mode=False) 