import asyncio
import edge_tts
import subprocess

async def generate_ai_voice(text):
    communicate = edge_tts.Communicate(
        text=text,
        voice="en-US-GuyNeural"
    )
    await communicate.save("generated_voice.mp3")
    print("Voice generated!")

def generate_and_play(text):
    asyncio.run(generate_ai_voice(text))

    print("Playing generated voice...")
    subprocess.run(["afplay", "generated_voice.mp3"], check=True)

    print("Playback completed!")