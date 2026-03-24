import azure.cognitiveservices.speech as speechsdk
import os

VOICE_MAP = {
    "አዜብ": "am-ET-MekdesNeural",
    "አባት": "am-ET-AmehaNeural",
    "ወርቃማዋ ወፍ": "am-ET-MekdesNeural",
    "ቀናት": "am-ET-MekdesNeural",
    "ክፉ እባብ": "am-ET-AmehaNeural",
    "narrator": "am-ET-MekdesNeural"
}

def format_time(ms):
    hours = int(ms // 3600000)
    minutes = int((ms % 3600000) // 60000)
    seconds = (ms % 60000) / 1000.0
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace('.', ',')

def synthesize_multi_voice(script_data, output_audio="output.mp3", output_srt="subtitles.srt"):
    # Build SSML
    ssml_parts = ['<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="am-ET">']
    for scene in script_data["scenes"]:
        # Narration
        narrator_voice = VOICE_MAP.get("narrator", "am-ET-MekdesNeural")
        ssml_parts.append(f'<voice name="{narrator_voice}">{scene["narration"]}</voice>')
        # Dialogues
        for dialogue in scene.get("dialogues", []):
            char = dialogue["character"]
            line = dialogue["line"]
            voice = VOICE_MAP.get(char, narrator_voice)
            ssml_parts.append(f'<voice name="{voice}">{line}</voice>')
    ssml_parts.append('</speak>')
    ssml = "\n".join(ssml_parts)

    # Azure config
    speech_key = os.environ.get('AZURE_SPEECH_KEY')
    region = os.environ.get('AZURE_SPEECH_REGION')
    if not speech_key or not region:
        raise Exception("Missing Azure TTS credentials")

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=region)
    speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_audio)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    boundaries = []
    def word_boundary_handler(evt):
        ticks_per_second = 10000000
        offset_ms = evt.audio_offset / ticks_per_second * 1000
        duration_ms = evt.duration / ticks_per_second * 1000
        boundaries.append({
            "word": evt.text,
            "start_ms": offset_ms,
            "end_ms": offset_ms + duration_ms
        })

    synthesizer.synthesis_word_boundary.connect(word_boundary_handler)

    result = synthesizer.speak_ssml_async(ssml).get()
    if result.reason != speechsdk.ResultReason.SynthesizingSpeechCompleted:
        raise Exception(f"Synthesis failed: {result.cancellation_details.error_details}")

    # Write SRT
    with open(output_srt, "w", encoding="utf-8") as f:
        for idx, wb in enumerate(boundaries, start=1):
            start = format_time(wb["start_ms"])
            end = format_time(wb["end_ms"])
            f.write(f"{idx}\n{start} --> {end}\n{wb['word']}\n\n")

    return output_audio, output_srt
