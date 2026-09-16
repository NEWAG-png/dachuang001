import os
import json
import sqlite3
import pandas as pd
import numpy as np
from utils import clean_and_parse_data, extract_spectrum_master, pixels_to_real_data

DB_NAME = 'spectrum_data.db'
CSV_FOLDER = 'standard_csv'       # 存放标准 CSV 的文件夹
IMAGE_FOLDER = 'standard_images'  # 存放标准图片的文件夹

def save_standard_to_db(file_name, material_name, spectrum_type, wavenumbers, intensities):
    """将标准数据存入数据库，强制打上 'Standard' 标签"""
    try:
        data_dict = {'wavenumbers': wavenumbers.tolist(), 'intensities': intensities.tolist()}
        data_json = json.dumps(data_dict)
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO spectra (file_name, material_name, spectrum_type, data_json, source_tag)
            VALUES (?, ?, ?, ?, 'Standard')
        ''', (file_name, material_name, spectrum_type, data_json))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ 存入数据库失败 ({file_name}): {str(e)}")
        return False

def build_database():
    # 1. 自动创建文件夹（如果不存在）
    os.makedirs(CSV_FOLDER, exist_ok=True)
    os.makedirs(IMAGE_FOLDER, exist_ok=True)
    
    success_count = 0
    
    # 2. 批量导入 CSV
    print("📂 正在扫描标准 CSV 文件...")
    for file_name in os.listdir(CSV_FOLDER):
        if file_name.endswith('.csv'):
            file_path = os.path.join(CSV_FOLDER, file_name)
            try:
                df = pd.read_csv(file_path)
                if len(df.columns) >= 2:
                    w = df.iloc[:, 0].values.astype(float)
                    i = df.iloc[:, 1].values.astype(float)
                    
                    # 清洗并对齐到 1000 个点
                    final_w, final_i = clean_and_parse_data({'wavenumbers': w, 'intensities': i})
                    if final_w is not None:
                        material = os.path.splitext(file_name)[0]
                        save_standard_to_db(file_name, material, "透射率", final_w, final_i)
                        success_count += 1
                        print(f"  ✅ CSV 导入成功: {material}")
            except Exception as e:
                print(f"  ❌ CSV 解析失败 ({file_name}): {e}")

    # 3. 批量导入图片
    print("📸 正在扫描标准图片文件...")
    for file_name in os.listdir(IMAGE_FOLDER):
        if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
            file_path = os.path.join(IMAGE_FOLDER, file_name)
            
            # 提取像素
            pixel_x, pixel_y, msg = extract_spectrum_master(file_path)
            if pixel_x is not None:
                # 像素转真实数据
                final_w, final_i, msg2 = pixels_to_real_data(pixel_x, pixel_y)
                if final_w is not None:
                    material = os.path.splitext(file_name)[0]
                    save_standard_to_db(file_name, material, "吸光度", final_w, final_i)
                    success_count += 1
                    print(f"  ✅ 图片导入成功: {material}")
                else:
                    print(f"  ❌ 图片坐标转换失败 ({file_name}): {msg2}")
            else:
                print(f"  ❌ 图片曲线提取失败 ({file_name}): {msg}")

    print(f"\n🎉 标准库构建完成！共成功导入 {success_count} 条标准数据！")

if __name__ == '__main__':
    build_database()