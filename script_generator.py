import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "goldfish-models/amh_ethi_100mb"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

def generate_story_script(topic, character_name, output_json="script.json"):
    prompt = f"""
ርዕስ: {topic}
ገጸ ባህሪ: {character_name}
ተረት በአማርኛ በሚከተለው JSON ቅርጸት ፃፍ፡
{{
  "title": "...",
  "scenes": [
    {{
      "setting": "...",
      "narration": "...",
      "dialogues": [
        {{"character": "...", "line": "..."}}
      ]
    }}
  ]
}}
"""
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        outputs = model.generate(
            inputs.input_ids,
            max_new_tokens=1024,
            temperature=0.8,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Extract JSON
    start = generated_text.find('{')
    end = generated_text.rfind('}') + 1
    if start != -1 and end != 0:
        json_str = generated_text[start:end]
        script = json.loads(json_str)
    else:
        # fallback: create a simple structure
        script = {
            "title": topic,
            "scenes": [{"setting": "ጫካ", "narration": generated_text, "dialogues": []}]
        }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    return script
