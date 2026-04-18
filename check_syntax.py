import json
import ast

with open('c:/AIwork/ImageGeneration/Runpod/Runpod_ComfyUI/runpod_setup.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Find Cell 5
cell5_source = ""
for cell in nb['cells']:
    if cell['cell_type'] == 'markdown' and "Cell 5" in "".join(cell['source']):
        found = True
    elif cell['cell_type'] == 'code' and "def build_workflow(" in "".join(cell['source']):
        cell5_source = "".join(cell['source'])
        break

with open('c:/AIwork/ImageGeneration/Runpod/Runpod_ComfyUI/cell5_check.py', 'w', encoding='utf-8') as f:
    f.write(cell5_source)

try:
    ast.parse(cell5_source)
    print("Syntax is OK.")
except SyntaxError as e:
    print(f"SyntaxError: {e}")
    import traceback
    traceback.print_exc()

