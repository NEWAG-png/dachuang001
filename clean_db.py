import sqlite3

def clean_image_records():
    conn = sqlite3.connect('spectrum_data.db')
    cursor = conn.cursor()
    
    try:
        # 1. 先看看数据库里有多少条图片数据
        cursor.execute("SELECT COUNT(*) FROM spectra WHERE source_tag = 'User_Upload'")
        count = cursor.fetchone()[0]
        print(f"🔍 发现 {count} 条图片测试数据。")
        
        if count > 0:
            # 2. 执行删除：只删 source_tag 是 'User_Upload' 的
            cursor.execute("DELETE FROM spectra WHERE source_tag = 'User_Upload'")
            conn.commit()
            print(f"✅ 成功删除 {count} 条图片数据！你的 CSV 标准数据已安全保留。")
        else:
            print("ℹ️ 数据库里目前没有图片数据，无需清理。")
            
    except Exception as e:
        print(f"❌ 出错了: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    clean_image_records()