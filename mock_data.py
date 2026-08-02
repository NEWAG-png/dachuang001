import sqlite3
import numpy as np
import os

DB_NAME = 'spectrum_data.db'

def generate_mock_data():
    if not os.path.exists(DB_NAME):
        print("❌ 没找到数据库文件，请先运行 init_db.py")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 准备 3 条假数据
    mock_samples = [
        ("PET_塑料_样本1", "transmittance"),
        ("PE_塑料_样本2", "absorbance"),
        ("PP_塑料_样本3", "transmittance")
    ]

    print("🚀 开始生成模拟光谱数据...")

    for name, mode in mock_samples:
        # 模拟红外光谱：波数从 400 到 4000，每隔 2 取一个点
        wavenumbers = np.arange(400, 4001, 2)
        
        # 模拟强度：生成一些带噪点的随机数据（假装是光谱曲线）
        intensities = np.random.rand(len(wavenumbers)) * 0.5 + 0.2
        
        # 把 numpy 数组转成 Python 列表，再转成字符串存起来
        import json
        data_json = json.dumps({
            "wavenumbers": wavenumbers.tolist(),
            "intensities": intensities.tolist()
        })

        cursor.execute(
            "INSERT INTO spectra (file_name, material_name, spectrum_type, data_json) VALUES (?, ?, ?, ?)",
            (f"{name}.csv", name, mode, data_json)
        )
        print(f"  ✅ 已生成模拟数据: {name} ({len(wavenumbers)} 个数据点)")

    conn.commit()
    conn.close()
    print("\n🎉 模拟数据生成完毕！你现在可以开始写查询和界面代码了。")

if __name__ == "__main__":
    generate_mock_data()