import urllib.request, json, base64, time
from pathlib import Path

sample_path = Path('data/uploads/972936fa_eda492d63643ee2dfbb320e316949436.jpg')
raw = sample_path.read_bytes()
b64 = base64.b64encode(raw).decode('ascii')

enhanced_prompt = """你是医疗单据高精度结构化抽取引擎。
【最高准则：表格行列严格横向对齐，严禁错行/串行/错位】
1. 双栏/多栏排版识别：国内化验单多采用左右两栏排版（左栏指标1~15，右栏指标16~30）。请逐栏、逐行严格识别，严禁横向跨栏混淆左右两边的项目与结果！
2. 指标名称与测试值严格同一行绑定：
   - 每行项目的「中文名/英文简称」「测定值」「单位」「参考区间」「提示(↑/↓)」必须严格来自同一行！
   - 测定值填入 value_num（如 4.07, 94.0, 59.0, 1.8, 5.14, 5.54, 56.0, 4.79, 330.0 等实际测量值）；
   - 参考区间的数值（如 3.9-6.1）分别填入 ref_low 和 ref_high，绝不可把参考区间上下限当成测试值！
3. 比值指标（白球比、AST/ALT比值）：测定结果通常为 0.5~2.5 之间的小数（如 1.8、0.63），绝不可与下方转氨酶等大整数搞混！
4. 严格输出符合 schema 的 JSON 对象。"""

url = 'https://api.openasi.bitmiracle.cn/v1/messages'
headers = {
    'x-api-key': 'openasi-Nh2R5vLXgtlXC0dy1stQ7H5zoAUJkcVU0ol0Hw1gQNE',
    'anthropic-version': '2023-06-01',
    'content-type': 'application/json'
}
data = {
    'model': 'claude-sonnet-4-6',
    'max_tokens': 3000,
    'system': enhanced_prompt,
    'messages': [{
        'role': 'user',
        'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64}},
            {'type': 'text', 'text': '请逐行提取这张化验单中的所有项目、测定值、单位和参考区间。输出严格JSON。'}
        ]
    }]
}

req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
with urllib.request.urlopen(req, timeout=40) as resp:
    res = json.loads(resp.read().decode('utf-8'))
    txt = res['content'][0]['text']
    print('RAW TEXT OUTPUT:\n', txt[:500])
    s = txt[txt.find('{'):txt.rfind('}')+1]
    parsed = json.loads(s)
    obs = parsed.get('observations', [])
    print(f'Enhanced Extraction Extracted {len(obs)} items:')
    for item in obs:
        name = item.get('display') or item.get('code') or item.get('name')
        val = item.get('value_num') if item.get('value_num') is not None else item.get('value_text')
        u = item.get('unit') or ''
        low, high = item.get('ref_low'), item.get('ref_high')
        flag = item.get('abnormal_flag') or ''
        print(f' - {name:<18}: {val} {u:<8} [{low} - {high}] {flag}')
