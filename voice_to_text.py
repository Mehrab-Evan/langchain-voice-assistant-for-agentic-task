
import sounddevice as sd
from scipy.io.wavfile import write
from groq import Groq
import os
from import_credential import groq_api_key
# Configuration
API_KEY = groq_api_key
FILENAME = "recording.wav"
SAMPLE_RATE = 16000
CHANNELS = 1

client = Groq(api_key=API_KEY)

# Step 1: Record microphone input
def record_audio():
    input("Press ENTER to start recording...")

    print("Recording... Speak now!")
    print("Press ENTER to stop recording.")

    recording = []

    def callback(indata, frames, time, status):
        if status:
            print(status)
        recording.append(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        callback=callback
    ):
        input()

    print("Recording stopped.")

    # Step 2: Save audio file
    audio_data = b"".join(
        chunk.tobytes() for chunk in recording
    )

    import numpy as np
    audio_array = np.frombuffer(audio_data, dtype=np.int16)

    write(FILENAME, SAMPLE_RATE, audio_array)

    print(f"Audio saved: {FILENAME}")


# Step 3: Send audio file to Groq
def transcribe_audio():
    print("Sending audio to Groq...")

    with open(FILENAME, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(FILENAME, audio_file.read()),
            model="whisper-large-v3-turbo",
            response_format="text"
        )

    print("\n========== TRANSCRIPTION ==========\n")
    print(transcription)
    print("\n===================================")
    return str(transcription)

if __name__ == "__main__":
    record_audio()
    transcribe_audio()
