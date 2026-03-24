import os
import replicate
import requests

def generate_background(prompt, output_path):
    client = replicate.Client(api_token=os.environ.get('REPLICATE_API_TOKEN'))
    model = "stability-ai/stable-diffusion:db21e45d3f7023abc2a46ee38a23973f6dce16bb082a930b0c49861f96d1e5bf"
    input_params = {
        "prompt": prompt,
        "negative_prompt": "text, watermark, ugly, deformed, distorted",
        "width": 1024,
        "height": 576,
        "num_outputs": 1,
        "num_inference_steps": 30,
        "guidance_scale": 7.5,
    }
    output = client.run(model, input=input_params)
    image_url = output[0]
    response = requests.get(image_url)
    with open(output_path, "wb") as f:
        f.write(response.content)
    return output_path

def generate_all_backgrounds(scenes, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for idx, scene in enumerate(scenes):
        setting = scene.get("setting", "forest")
        prompt = f"A beautiful Ethiopian fairy tale illustration, {setting}, vibrant colors, storybook style"
        out_path = os.path.join(output_dir, f"scene_{idx}.png")
        generate_background(prompt, out_path)
        scene["background_path"] = out_path
    return scenes
