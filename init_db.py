import sqlite3
import os

DB_NAME = 'spectrum_data.db'

def init_database():
    # ⚠️ 警告：正式跑通后，请务必注释掉下面两行！
    # if os.path.exists(DB_NAME):
    #     os.remove(DB_NAME)
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 创建光谱数据表（兼容 CSV 和图片）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS spectra (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT NOT NULL,          -- 原始文件名或图片名
        material_name TEXT,               -- 材料名称（CSV有，图片默认为'待测样品'）
        spectrum_type TEXT NOT NULL,      -- '透射率' 或 '吸光度'
        data_json TEXT NOT NULL,          -- 核心数据：存波数和强度的JSON字符串
        source_tag TEXT DEFAULT 'Unknown',-- 【新增】'Standard'(标准库) 或 'User_Upload'(用户上传)
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- 【新增】记录上传时间
    )
    ''')
    
    # 创建索引，加快搜索速度
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_spectrum_type ON spectra (spectrum_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_tag ON spectra (source_tag)')
    
    conn.commit()
    conn.close()
    print(f"✅ 数据库 '{DB_NAME}' 初始化/检查完成！")

if __name__ == '__main__':
    init_database()