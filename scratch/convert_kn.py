with open('scratch/original_knowledge.py', encoding='utf-16') as f:
    text = f.read()

with open('scratch/original_knowledge_utf8.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Converted original_knowledge.py to UTF-8 successfully, length:", len(text))
