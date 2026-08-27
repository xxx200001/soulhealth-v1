import sys
import os
sys.path.insert(0, os.path.abspath('.'))

with open('scratch/original_knowledge_utf8.py', encoding='utf-8') as f:
    code = f.read()

env = {}
exec(code, env)

print("GOALS keys:", list(env['GOALS'].keys()))
print("FOOD_POOLS keys:", list(env['FOOD_POOLS'].keys()))
print("RECIPES keys:", list(env['RECIPES'].keys()))
print("TEA_FORMULAS keys:", list(env['TEA_FORMULAS'].keys()))
print("TEA_INGREDIENT_RULES count:", len(env['TEA_INGREDIENT_RULES']))
