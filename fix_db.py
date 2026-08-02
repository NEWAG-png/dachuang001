import sqlite3
import json

DB_NAME = 'spectrum_data.db'

def clean_spectra_data():
    print(f"🔧 正在修复数据库: {DB_NAME} ...")
    
    # 1. 连接数据库
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 2. 获取所有数据 (ID 和 data_json)
    cursor.execute("SELECT id, data_json FROM spectra")
    rows = cursor.fetchall()
    
    fixed_count = 0
    
    for row_id, raw_json_str in rows:
        try:
            # 解析 JSON 字符串
            data_obj = json.loads(raw_json_str)
            
            # 检查是否有 wavenumbers 和 intensities
            if 'wavenumbers' in data_obj and 'intensities' in data_obj:
                w_list = data_obj['wavenumbers']
                i_list = data_obj['intensities']
                
                new_w = []
                new_i = []
                
                # 核心清洗逻辑：只保留能转成数字的项
                # 使用 zip 确保波数和强度一一对应
                for w, i in zip(w_list, i_list):
                    try:
                        # 尝试转浮点数，如果失败说明是表头文字
                        float(w) 
                        float(i)
                        new_w.append(w) # 保留原始字符串格式的数字，或者转float看你需求
                        new_i.append(i)
                    except (ValueError, TypeError):
                        # 遇到 "Wavenumber [cm-1]" 这种就会跳过
                        continue
                
                # 只有当数据被清洗过（长度变短了），才更新数据库
                if len(new_w) < len(w_list):
                    data_obj['wavenumbers'] = new_w
                    data_obj['intensities'] = new_i
                    
                    # 更新回数据库
                    new_json_str = json.dumps(data_obj)
                    cursor.execute("UPDATE spectra SET data_json = ? WHERE id = ?", (new_json_str, row_id))
                    fixed_count += 1
                    
        except Exception as e:
            print(f"⚠️ ID {row_id} 处理出错: {e}")

    # 3. 提交更改并关闭
    conn.commit()
    conn.close()
    
    print(f"✅ 修复完成！共清洗了 {fixed_count} 条含有脏数据的记录。")
    print("现在可以重新运行你的 app.py 了！")

if __name__ == "__main__":
    clean_spectra_data()