import os
import json
import time
from script_generator import generate_story_script
from tts_multi_voice import synthesize_multi_voice
from background_gen import generate_all_backgrounds
from video_assembler import create_video_from_script
from audio_mixer import AudioMixer
from utils import upload_to_s3

def run_pipeline(topic, character_name, user_id=None, output_dir="output"):
    os.makedirs(output_dir, exist_ok=True)

    # 1. Generate script
    script_path = os.path.join(output_dir, "script.json")
    script = generate_story_script(topic, character_name, script_path)

    # 2. Generate backgrounds
    scenes = script["scenes"]
    bg_dir = os.path.join(output_dir, "backgrounds")
    generate_all_backgrounds(scenes, bg_dir)

    # Save updated script with background paths
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    # 3. Synthesize audio with multi‑voice
    audio_path = os.path.join(output_dir, "narration.mp3")
    srt_path = os.path.join(output_dir, "subtitles.srt")
    synthesize_multi_voice(script, audio_path, srt_path)

    # 4. Mix audio (music & SFX)
    mixer = AudioMixer("audio_assets")
    sfx_map = {"ወፍ": "bird_chirp.mp3", "ነፋስ": "wind.mp3", "ጥንቆላ": "magic_sparkle.mp3"}
    mood = "magical" if "ወርቅ" in script["title"] else "happy"
    mixed_audio_path = os.path.join(output_dir, "mixed_narration.mp3")
    mixer.mix_audio(audio_path, script, mixed_audio_path, mood=mood, sfx_map=sfx_map)

    # 5. Assemble video
    character_img = "characters/azeb.png"  # default character image (optional)
    video_path = os.path.join(output_dir, "final_video.mp4")
    create_video_from_script(script_path, mixed_audio_path, srt_path, character_img, video_path)

    # 6. Upload to S3 if user_id provided
    s3_url = None
    if user_id:
        s3_key = f"users/{user_id}/{int(time.time())}_final.mp4"
        s3_url = upload_to_s3(video_path, "amharic-fairy-tale-videos", s3_key)

    return video_path, s3_url
