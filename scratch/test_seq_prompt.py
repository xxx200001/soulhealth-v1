import urllib.request, json, base64, time
from pathlib import Path

sample_path = Path('data/uploads/972936fa_eda492d63643ee2dfbb320e316949436.jpg')
raw = sample_path.read_bytes()
b64 = base64.b64encode(raw).decode('ascii')

enhanced_prompt = """你是医疗化验单高精度视觉数字化引擎。
【最高精度保障：按序号锚定提取（核心防错）】
化验单每行都有明确的编号（1~32）。请严格按照每行的【序号 1~32】顺序逐行抽取，确保每个序号的项目名称、结果值、参考区间 100% 准确对应，绝不允许漏行或串行！

必须严格提取的结构：
- seq: 序号（如 1, 2, ... 32）
- display: 中文项目全称（如 "总胆汁酸", "总胆红素", "直接胆红素", "间接胆红素", "γ-谷氨酰基转移酶", "乳酸脱氢酶", "尿素", "肌酐", "尿酸", "视黄醇结合蛋白" 等）
- code: 缩写（ALT/AST/ALP/GGT/LDH/GLU/UREA/CREA/UA/TC/TG/HDLC/LDLC/TBA/TBIL/DBIL/IBIL/RBP等）
- value_num: 该序号行对应的真实测定结果数值（浮点数）
- unit: 单位
- ref_low: 参考下限（若有）
- ref_high: 参考上限（若有）
- abnormal_flag: 箭头或标记（↑记 "H"，↓记 "L"，正常记 "N"）

【关键检查点】
- 序号 6: 总胆汁酸 -> 2.3
- 序号 7: 总胆红素 -> 10.5
- 序号 8: 直接胆红素 -> 5.4
- 序号 9: 间接胆红素 -> 5.1
- 序号 17: 碱性磷酸酶 -> 103 (↑)
- 序号 18: γ-谷氨酰基转移酶 -> 36
- 序号 19: 乳酸脱氢酶 -> 250
- 序号 20: 葡萄糖 -> 5.14
- 序号 21: 尿素 -> 2.54 (↓)
- 序号 22: 肌酐 -> 56
- 序号 23: 尿酸 -> 330
- 序号 24: 总胆固醇 -> 4.79
- 序号 25: 甘油三酯 -> 2.13 (↑)
- 序号 26: 高密度脂蛋白胆固醇 -> 0.98 (↓)
- 序号 32: 视黄醇结合蛋白 -> 27.8

输出且仅输出一个标准 JSON 对象：{"document_type":"lab_report","exam_date":"2025-10-06","observations":[...]}"""

url = 'https://api.openasi.bitmiracle.cn/v1/messages'
headers = {
    'x-api-key': 'openasi-Nh2R5vLXgtlXC0dy1stQ7H5zoAUJkcVU0ol0Hw1gQNE',
    'anthropic-version': '2023-06-01',
    'content-type': 'application/json'
}
data = {
    'model': 'claude-opus-4-6',
    'max_tokens': 3000,
    'system': enhanced_prompt,
    'messages': [{
        'role': 'user',
        'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64}},
            {'type': 'text', 'text': '请按序号 1~32 逐行抽取化验单中的全部 32 项测定结果与参考区间，输出 JSON。'}
        ]
    }]
}

req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
with urllib.request.urlopen(req, timeout=40) as resp:
    res = json.loads(resp.read().decode('utf-8'))
    txt = res['content'][0]['text']
    s = txt[txt.find('{'):txt.rfind('}')+1]
    parsed = json.loads(s)
    obs = parsed.get('observations', [])
    print(f'SUCCESS! Extracted {len(obs)} items:')
    for item in obs:
        seq = item.get('seq', '')
        name = item.get('display') or item.get('code')
        val = item.get('value_num')
        u = item.get('unit') or ''
        low, high = item.get('ref_low'), item.get('ref_high')
        flag = item.get('abnormal_flag') or ''
        print(f'{seq:>2} | {name:<14}: {val:<6} {u:<8} [{low} - {high}] {flag}')
