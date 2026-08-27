import sys

with open('scratch/original_knowledge_utf8.py', encoding='utf-8') as f:
    text = f.read()

import ast
tree = ast.parse(text)
for node in tree.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                sys.stdout.buffer.write(f'Top-level assignment: {target.id}\n'.encode('utf-8'))
