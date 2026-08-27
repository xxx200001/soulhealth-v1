with open('scratch/original_knowledge_utf8.py', encoding='utf-8') as f:
    text = f.read()

import re
assignments = re.findall(r'^([A-Z_]+)\s*:\s*', text, flags=re.MULTILINE)
print("Assignments found:", assignments)
