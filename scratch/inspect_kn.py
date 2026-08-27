for enc in ['utf-16', 'utf-8', 'gbk']:
    try:
        with open('scratch/original_knowledge.py', encoding=enc) as f:
            code = f.read()
        print(f"Decoded with {enc}")
        break
    except Exception:
        continue

exec_env = {}
exec(code, exec_env)
print("Original GOALS:", list(exec_env.get('GOALS', {}).keys()))
print("Original FOOD_POOLS:", list(exec_env.get('FOOD_POOLS', {}).keys()))
print("Original RECIPES:", list(exec_env.get('RECIPES', {}).keys()))
print("Original TEA_FORMULAS:", list(exec_env.get('TEA_FORMULAS', {}).keys()))
print("Original TEA_INGREDIENT_RULES count:", len(exec_env.get('TEA_INGREDIENT_RULES', {})))
