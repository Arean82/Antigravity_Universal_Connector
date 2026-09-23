import os
import json
import sqlite3
from collections import defaultdict

ref_dir = r"E:\GitHub\Antigravity-Manager"
db_path = r"e:\GitHub\Antigravity_Universal_Connector\reference_repo_analysis.db"
analysis_dir = r"e:\GitHub\Antigravity_Universal_Connector\analysis"

os.makedirs(analysis_dir, exist_ok=True)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS all_repo_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relative_path TEXT UNIQUE,
    extension TEXT,
    size_bytes INTEGER,
    line_count INTEGER,
    category TEXT,
    summary TEXT
)
""")

file_categories = {
    "src-tauri/src/modules": "Backend Module",
    "src-tauri/src/proxy": "Proxy Engine",
    "src-tauri/src/models": "Data Model",
    "src-tauri/src/utils": "Utility / Codec",
    "src-tauri/src/commands": "Tauri IPC Command",
    "src/": "Frontend UI (Vue/TS)",
    "docs/": "Documentation",
    "docker/": "Deployment / Container",
    "deploy/": "Package Build Scripts",
    "": "Root Configuration / Meta"
}

total_files = 0
total_lines = 0
total_bytes = 0

rows = []

for root, dirs, files in os.walk(ref_dir):
    for f in files:
        full_path = os.path.join(root, f)
        rel_path = os.path.relpath(full_path, ref_dir).replace("\\", "/")
        ext = os.path.splitext(f)[1].lower()
        sz = os.path.getsize(full_path)
        
        lines = 0
        summary = ""
        
        # Read text files to count lines and derive summary
        is_text = ext in [".rs", ".ts", ".vue", ".json", ".md", ".toml", ".py", ".sh", ".html", ".css", ".js", ".yml", ".yaml"]
        if is_text:
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.readlines()
                    lines = len(content)
                    if lines > 0:
                        first_non_empty = [l.strip() for l in content[:15] if l.strip() and not l.strip().startswith("//") and not l.strip().startswith("#")]
                        if first_non_empty:
                            summary = first_non_empty[0][:150]
            except Exception as e:
                summary = f"Error reading: {e}"
        else:
            summary = "Binary / Asset file"
            
        category = "Other"
        for prefix, cat in file_categories.items():
            if rel_path.startswith(prefix):
                category = cat
                break
                
        rows.append((rel_path, ext, sz, lines, category, summary))
        total_files += 1
        total_lines += lines
        total_bytes += sz

cur.executemany("""
INSERT OR REPLACE INTO all_repo_files 
(relative_path, extension, size_bytes, line_count, category, summary)
VALUES (?, ?, ?, ?, ?, ?)
""", rows)

conn.commit()
conn.close()

print(f"Cataloged {total_files} files, {total_lines} lines of code, {total_bytes} bytes into all_repo_files table.")
