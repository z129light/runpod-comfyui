import os
import random

# ベースとなるプロンプトの構成要素
subjects = [
    "A hyper-realistic, high-fashion studio portrait of a 28-year-old male K-pop idol with an exceptionally pale complexion",
    "A cinematic, close-up portrait of a handsome male idol with sharp jawline and flawless skin",
    "An editorial fashion shot of a young male model with striking features and intense gaze",
    "A moody, dramatic portrait of a male K-pop star with perfectly styled hair"
]

outfits = [
    "dressed in a tailored, oversized blazer in a textured, heather grey fabric worn open",
    "wearing a sleek black turtleneck sweater layered with a silver chain",
    "styled in a trendy streetwear outfit featuring an oversized graphic tee and silver accessories",
    "wearing a crisp white dress shirt unbuttoned slightly at the collar",
    "dressed in a distressed denim jacket layered over a basic white t-shirt",
    "wearing a custom-tailored silk suit with a subtle floral pattern"
]

backgrounds = [
    "The background is a solid, neutral, light grey, providing a clean, distraction-free canvas.",
    "Set against a dimly lit background with a soft neon blue rim light.",
    "The background features a subtle, out-of-focus studio setup with soft box lights visible.",
    "A pure white seamless background for a minimalist and modern aesthetic."
]

lighting_styles = [
    "The lighting is soft and even, minimizing harsh shadows while highlighting the texture of his skin and hair.",
    "Dramatic chiaroscuro lighting creates strong contrast and deep shadows, adding mystery.",
    "Soft, diffused natural window light illuminates the face, giving a very natural and gentle feel.",
    "High-contrast ring light illumination creates a perfect circular catchlight in the eyes."
]

negative_prompt = "nsfw, nude, bad quality, worst quality, low res, extra limbs, bad anatomy, bad hands, missing fingers, blurry, ugly, distorted, jpeg artifacts, watermark, signature, mutated, deformed"

def generate_prompt_file(output_path, num_prompts=100):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for i in range(num_prompts):
            subject = random.choice(subjects)
            outfit = random.choice(outfits)
            bg = random.choice(backgrounds)
            light = random.choice(lighting_styles)
            
            # 構成を組み立てる
            pos_prompt = f"**COMPOSITION:** Medium shot, centered placement, eye-level camera angle. {subject}. {outfit}. {bg} {light} Every detail is rendered with cinematic precision."
            
            # Inspire Packの仕様： positive: と negative: を指定
            f.write(f"positive: {pos_prompt}\n")
            f.write(f"negative: {negative_prompt}\n")
            f.write("\n") # 区切り

    print(f"[Done] {num_prompts}枚分のプロンプトを {output_path} に生成しました。")

if __name__ == "__main__":
    # 出力パス (ローカルでのテスト用)
    output_file = os.path.join(os.path.dirname(__file__), "..", "prompts", "runpod_prompts.txt")
    
    # ここで生成したい枚数を指定します
    generate_prompt_file(output_file, num_prompts=200)
