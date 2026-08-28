import os
import sys
import time
from datetime import datetime

EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "ref_filesofgood",
    "soulhealth-v1.1-fixes",
}

EXCLUDE_EXTS = {
    ".exe",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".pyc",
    ".log",
}

EXCLUDE_FILES = {
    "cloudflared.exe",
    "soulhealth.db",
    "soulhealth.db-wal",
    "soulhealth.db-shm",
    "package-lock.json",
    "soulhealth_v1_code_dump.txt",
    "project_code_dump.txt",
    "code_dump_latest.txt",
    "export_code_dump.py",
}

def scan_files(root_dir):
    file_list = []
    for root, dirs, files in os.walk(root_dir):
        # 过滤排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        
        for file in files:
            if file in EXCLUDE_FILES or file.startswith(".git"):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in EXCLUDE_EXTS:
                continue
                
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, root_dir)
            size_kb = os.path.getsize(full_path) / 1024.0
            file_list.append((rel_path, full_path, size_kb))
            
    file_list.sort(key=lambda x: x[0])
    return file_list

def generate_dump(root_dir, output_file):
    files = scan_files(root_dir)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("=" * 80 + "\n")
        out.write("PROJECT CODE DUMP - SoulHealth V1 (Production)\n")
        out.write(f"Generated: {now_str}\n")
        out.write(f"Total files: {len(files)}\n")
        out.write("=" * 80 + "\n\n")
        
        out.write("EXCLUDED (not needed for code review / AI prompts):\n")
        out.write("  - __pycache__/, .git/, node_modules/, dist/, ref_filesofgood/\n")
        out.write("  - *.db, *.sqlite, *.exe, *.png, *.jpg, package-lock.json\n\n")
        
        out.write("PROJECT STRUCTURE:\n")
        out.write("-" * 80 + "\n")
        for rel_path, _, size_kb in files:
            out.write(f"  {rel_path} ({size_kb:.1f} KB)\n")
        out.write("-" * 80 + "\n\n")
        
        for rel_path, full_path, size_kb in files:
            out.write("\n" + "=" * 80 + "\n")
            out.write(f"FILE: {rel_path} ({size_kb:.1f} KB)\n")
            out.write("=" * 80 + "\n")
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                    out.write(content)
                    if not content.endswith("\n"):
                        out.write("\n")
            except Exception as e:
                out.write(f"[ERROR READING FILE: {e}]\n")
                
    print(f"[SUCCESS] Code dump generated at: {output_file}")
    print(f"Total files dumped: {len(files)}")
    print(f"Total size: {os.path.getsize(output_file) / 1024 / 1024:.2f} MB")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_output = os.path.join(base_dir, "soulhealth_v1_code_dump.txt")
    generate_dump(base_dir, target_output)
