import sqlite3
import os

# 定义数据库文件名
DB_NAME = 'spectrum_data.db'

def init_database():
    # 如果数据库已存在，先删除（为了演示方便，正式跑通后可以注释掉这行）
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 创建光谱数据表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS spectra (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT NOT NULL,          -- 原始文件名
        material_name TEXT,               -- 材料名称（如果CSV里有）
        spectrum_type TEXT NOT NULL,      -- 关键：记录是 '透射率' 还是 '吸光度'
        data_json TEXT NOT NULL,          -- 关键：存波数和强度的JSON字符串
        source_tag TEXT DEFAULT 'Unknown',-- 【新增】标记数据来源：'Standard'(标准库) 或 'Unknown'(待测)
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建索引，加快按类型搜索的速度
    cursor.execute('CREATE INDEX idx_spectrum_type ON spectra (spectrum_type)')
    # 【新增】为 source_tag 创建索引，加快筛选标准库的速度
    cursor.execute('CREATE INDEX idx_source_tag ON spectra (source_tag)')
    
    conn.commit()
    conn.close()
    print(f"✅ 数据库 '{DB_NAME}' 初始化成功！表结构已建立。")

if __name__ == '__main__':
    init_database()