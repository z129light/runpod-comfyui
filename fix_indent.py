import json
with open('c:/AIwork/ImageGeneration/Runpod/Runpod_ComfyUI/runpod_setup.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code' and "def build_workflow(" in "".join(cell['source']):
        new_source = []
        for line in cell['source']:
            # Fix excessive indentation
            if line.startswith("        payload = json.dumps("):
                new_source.append("    payload = json.dumps({'prompt': workflow}).encode('utf-8')\n")
            elif line.startswith("        req = urllib.request.Request("):
                new_source.append("    req = urllib.request.Request(\n")
            elif line.startswith("            f'{COMFY_URL}/prompt',"):
                new_source.append("        f'{COMFY_URL}/prompt',\n")
            elif line.startswith("            data=payload,"):
                new_source.append("        data=payload,\n")
            elif line.startswith("            headers={'Content-Type': 'application/json'},"):
                new_source.append("        headers={'Content-Type': 'application/json'},\n")
            elif line.startswith("            method='POST',"):
                new_source.append("        method='POST',\n")
            elif line.startswith("        )"):
                new_source.append("    )\n")
            elif line.startswith("        with urllib.request.urlopen(req) as resp:"):
                new_source.append("    with urllib.request.urlopen(req) as resp:\n")
            elif line.startswith("            result = json.loads(resp.read())"):
                new_source.append("        result = json.loads(resp.read())\n")
            elif line.startswith("            pid = result['prompt_id']"):
                new_source.append("        pid = result['prompt_id']\n")
            else:
                new_source.append(line)
        cell['source'] = new_source

with open('c:/AIwork/ImageGeneration/Runpod/Runpod_ComfyUI/runpod_setup.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
