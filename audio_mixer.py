import os
from pydub import AudioSegment
from pydub.effects import normalize

class AudioMixer:
    def __init__(self, assets_folder="audio_assets"):
        self.assets_folder = assets_folder
        self.music_dir = os.path.join(assets_folder, "music")
        self.sfx_dir = os.path.join(assets_folder, "sfx")

    def load_audio(self, path):
        if not os.path.exists(path):
            return None
        if path.endswith('.mp3'):
            return AudioSegment.from_mp3(path)
        elif path.endswith('.wav'):
            return AudioSegment.from_wav(path)
        return None

    def add_background_music(self, narration_audio, mood="happy", volume=-20):
        music_file = os.path.join(self.music_dir, f"{mood}.mp3")
        if not os.path.exists(music_file):
            return narration_audio
        music = self.load_audio(music_file)
        if music is None:
            return narration_audio
        if len(music) < len(narration_audio):
            loops = len(narration_audio) // len(music) + 1
            music = music * loops
        music = music[:len(narration_audio)]
        music = music - volume
        return narration_audio.overlay(music)

    def mix_audio(self, narration_audio_path, script_data, output_path, mood="happy", sfx_map=None):
        if narration_audio_path.endswith('.mp3'):
            audio = AudioSegment.from_mp3(narration_audio_path)
        else:
            audio = AudioSegment.from_wav(narration_audio_path)

        audio = self.add_background_music(audio, mood=mood)

        if sfx_map:
            total_duration = len(audio) / 1000.0
            total_chars = sum(len(scene["narration"]) for scene in script_data["scenes"])
            if total_chars == 0:
                per_scene_duration = total_duration / len(script_data["scenes"])
                scene_starts = [i * per_scene_duration for i in range(len(script_data["scenes"]))]
            else:
                scene_starts = []
                cumulative = 0
                for scene in script_data["scenes"]:
                    cumulative += len(scene["narration"]) / total_chars * total_duration
                    scene_starts.append(cumulative)
                scene_starts = [0] + scene_starts[:-1]

            for idx, scene in enumerate(script_data["scenes"]):
                start_time = scene_starts[idx]
                for keyword, sfx_file in sfx_map.items():
                    if keyword in scene["narration"].lower():
                        sfx_path = os.path.join(self.sfx_dir, sfx_file)
                        sfx = self.load_audio(sfx_path)
                        if sfx:
                            audio = audio.overlay(sfx, position=int(start_time * 1000))
                        break

        audio = normalize(audio)
        if output_path.endswith('.mp3'):
            audio.export(output_path, format="mp3")
        else:
            audio.export(output_path, format="wav")
        return output_path
