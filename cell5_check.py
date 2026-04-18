import json
import random
import urllib.request


def build_workflow(prompt_text, negative_prompt, model_name, aspect_ratio, weight_dtype, ksampler_params, lora_config, batch_size=2, seed=None):
    """ComfyUI API形式のワークフローdictを構築する"""
    if seed is None:
        seed = random.randint(0, 2**53)

    model_files = {
        'turbo': 'z_image_turbo_bf16.safetensors',
        'zimage': 'z_image_bf16.safetensors',
    }

    api = {
        '1': {'class_type': 'UNETLoader', 'inputs': {
            'unet_name': model_files[model_name],
            'weight_dtype': weight_dtype,
        }},
        '2': {'class_type': 'VAELoader', 'inputs': {
            'vae_name': 'ae.safetensors',
        }},
        '3': {'class_type': 'CLIPLoader', 'inputs': {
            'clip_name': 'qwen_3_4b.safetensors',
            'type': 'lumina2',
            'device': 'default',
        }},
        '8': {'class_type': 'CR Aspect Ratio Social Media', 'inputs': {
            'width': 1024,
            'height': 1024,
            'aspect_ratio': aspect_ratio,
            'swap_dimensions': 'Off',
            'upscale_factor': 1,
            'prescale_factor': 1,
            'batch_size': batch_size,
        }},
    }

    # LoRAチェーンを構築
    current_model = ['1', 0]
    current_clip = ['3', 0]
    for i, lora in enumerate(lora_config):
        lora_id = f'lora_{i}'
        api[lora_id] = {
            'class_type': 'LoraLoader',
            'inputs': {
                'model': current_model,
                'clip': current_clip,
                'lora_name': lora['name'],
                'strength_model': lora['strength'],
                'strength_clip': lora['strength'],
            }
        }
        current_model = [lora_id, 0]
        current_clip = [lora_id, 1]

    api['5'] = {'class_type': 'ModelSamplingAuraFlow', 'inputs': {
        'model': current_model,
        'shift': 3.0,
    }}
    api['6'] = {'class_type': 'CLIPTextEncode', 'inputs': {
        'clip': current_clip,
        'text': prompt_text,
    }}
    if model_name == 'turbo':
        api['7'] = {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': ['6', 0]}}
    else:
        api['7'] = {'class_type': 'CLIPTextEncode', 'inputs': {'clip': current_clip, 'text': negative_prompt}}
    api['9'] = {'class_type': 'KSampler', 'inputs': {
        'model': ['5', 0],
        'positive': ['6', 0],
        'negative': ['7', 0],
        'latent_image': ['8', 5],
        'seed': seed,
        'steps': ksampler_params['steps'],
        'cfg': ksampler_params['cfg'],
        'sampler_name': ksampler_params['sampler'],
        'scheduler': ksampler_params['scheduler'],
        'denoise': 1.0,
    }}
    api['10'] = {'class_type': 'VAEDecodeTiled', 'inputs': {
        'samples': ['9', 0],
        'vae': ['2', 0],
        'tile_size': 512,
        'overlap': 64,
        'temporal_size': 64,
        'temporal_overlap': 8,
    }}
    api['11'] = {'class_type': 'SaveImage', 'inputs': {
        'images': ['10', 0],
        'filename_prefix': f'RunPod_{model_name}',
    }}
    return api


# プロンプトを読み込む
if PROMPT_FILE and os.path.exists(PROMPT_FILE):
    with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    blocks = [b.strip() for b in content.split('---') if b.strip()]
    prompts = []
    for block in blocks:
        pos = ''
        neg = DEFAULT_NEGATIVE # デフォルトをセット
        for l in block.split('\n'):
            if l.lower().startswith('positive:'):
                pos = l[9:].strip()
            elif l.lower().startswith('negative:'):
                neg = l[9:].strip()
        if pos:
            prompts.append({'positive': pos, 'negative': neg})
    print(f'プロンプトファイル: {PROMPT_FILE} ({len(prompts)}件)')
else:
    prompts = []
    print(f'インラインプロンプト使用 ({len(prompts)}件)')

if not prompts:
    raise ValueError('プロンプトが未設定です (PROMPTS_INLINE または PROMPT_FILE を Cell 1 で設定してください)')

# ワークフローをキューに追加
COMFY_URL = 'http://localhost:8188'
print(f'\nモデル: {MODEL_NAME} | {len(prompts)}件をキューに追加中...')

for i, p_dict in enumerate(prompts):
    if isinstance(p_dict, str): p_dict = {'positive': p_dict, 'negative': DEFAULT_NEGATIVE}
    workflow = build_workflow(
        prompt_text=p_dict['positive'],
        negative_prompt=p_dict['negative'],
        model_name=MODEL_NAME,
        aspect_ratio=ASPECT_RATIO,
        weight_dtype=WEIGHT_DTYPE,
        ksampler_params=KSAMPLER_PARAMS[MODEL_NAME],
        lora_config=LORA_CONFIG,
        batch_size=BATCH_SIZE,
    )
    payload = json.dumps({'prompt': workflow}).encode('utf-8')
    req = urllib.request.Request(
        f'{COMFY_URL}/prompt',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        pid = result['prompt_id']
    print(f'  [{i+1}/{len(prompts)}] batch({BATCH_SIZE}) queued: {pid}')

print(f'\n全 {len(prompts)} 件のワークフローをキューに追加しました。')
print('完了後、Cell 6 の auto_terminator が自動停止します。')
