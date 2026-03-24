import os
import json
from moviepy.editor import *

def create_video_from_script(script_path, audio_path, srt_path, character_img=None, output_video="final.mp4"):
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    scenes = script["scenes"]
    total_duration = AudioFileClip(audio_path).duration

    # Parse SRT subtitles
    subs = []
    with open(srt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().isdigit():
            i += 1
            time_line = lines[i].strip()
            start_end = time_line.split(" --> ")
            start_time = start_end[0].replace(',', '.')
            end_time = start_end[1].replace(',', '.')
            text = lines[i+1].strip()
            i += 3
            txt = TextClip(text, fontsize=28, color='white', font='Arial', stroke_color='black', stroke_width=1, method='caption')
            txt = txt.set_position(('center', 'bottom')).set_start(start_time).set_duration(float(end_time)-float(start_time))
            subs.append(txt)
        else:
            i += 1

    # Build scene clips
    scene_clips = []
    total_chars = sum(len(scene["narration"]) for scene in scenes)
    if total_chars == 0:
        durations = [total_duration / len(scenes)] * len(scenes)
    else:
        durations = [(len(scene["narration"]) / total_chars) * total_duration for scene in scenes]

    for i, scene in enumerate(scenes):
        bg_path = scene.get("background_path", None)
        if not bg_path or not os.path.exists(bg_path):
            bg_path = "backgrounds/default.jpg"
        bg = ImageClip(bg_path).set_duration(durations[i]).resize(height=1080)
        if character_img and os.path.exists(character_img):
            char = ImageClip(character_img, transparent=True).resize(height=150).set_position(('left', 'bottom')).set_duration(durations[i])
            bg = CompositeVideoClip([bg, char])
        scene_clips.append(bg)

    video = concatenate_videoclips(scene_clips, method="compose")
    if video.duration > total_duration:
        video = video.subclip(0, total_duration)
    elif video.duration < total_duration:
        black = ColorClip(size=(1920,1080), color=(0,0,0), duration=total_duration - video.duration)
        video = concatenate_videoclips([video, black])

    final = CompositeVideoClip([video] + subs)
    final = final.set_audio(AudioFileClip(audio_path))
    final.write_videofile(output_video, fps=24, codec='libx264', audio_codec='aac')
    return output_video
