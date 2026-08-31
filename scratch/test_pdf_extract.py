"""测试 PDF 体检报告提取"""
import os, sys, json
sys.path.insert(0, r'd:\BaiduNetdiskDownload\soulhealth-v1\soulhealth-v1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'd:\BaiduNetdiskDownload\soulhealth-v1\soulhealth-v1')

from pathlib import Path
from app.ingest.vision_llm import extract_from_file

pdf_path = Path(r'D:\微信文件\xwechat_files\wxid_mviguy0cna1m22_c0e5\msg\file\2026-08\20260811体检报告-李良(1).pdf')

print(f"=== 开始提取: {pdf_path.name} ===")
try:
    result = extract_from_file(pdf_path, None)
    ext = result.to_dict()
    
    print(f"[OK] 提取成功!")
    print(f"  document_type: {ext.get('document_type')}")
    print(f"  exam_date:     {ext.get('exam_date')}")
    print(f"  patient:       {ext.get('patient')}")
    print(f"  engine:        {result.engine}")
    print()
    
    obs = ext.get("observations") or []
    print(f"[指标] 提取到 {len(obs)} 项数值指标:")
    for o in obs[:15]:
        code = o.get("code", "?")
        display = o.get("display", "?")
        val = o.get("value_num", "?")
        unit = o.get("unit", "")
        flag = o.get("abnormal_flag", "")
        print(f"  {code:10s} {display:20s} = {val} {unit}  {flag}")
    if len(obs) > 15:
        print(f"  ... 还有 {len(obs) - 15} 项")
    print()
    
    findings = ext.get("findings") or []
    print(f"[所见] 提取到 {len(findings)} 条影像/检查所见:")
    for f in findings:
        organ = f.get("organ", "?")
        desc = (f.get("description", "") or "")[:80]
        flags = f.get("flags", [])
        flag_str = f"  !! {flags}" if flags else ""
        print(f"  [{organ}] {desc}{flag_str}")
    print()
    
    impressions = ext.get("impressions") or []
    print(f"[诊断] 提取到 {len(impressions)} 条诊断意见:")
    for imp in impressions:
        print(f"  -> {imp[:100]}")
    print()
    
    out_path = Path("scratch/test_pdf_extraction.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ext, f, ensure_ascii=False, indent=2)
    print(f"[保存] 完整结果: {out_path}")
    
except Exception as e:
    print(f"[FAIL] 提取失败: {e}")
    import traceback
    traceback.print_exc()
