from kokoro import KPipeline
import soundfile as sf

pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')  # 'a' = American English
# Available voices: af_heart, af_bella, af_nicole (female), am_adam (male)
generator = pipeline("Haan MJ, kar deti hoon abhi!", voice='af_heart')

for i, (gs, ps, audio) in enumerate(generator):
    sf.write(f'output.wav', audio, 24000)

print("Done! Audio saved to output.wav")
