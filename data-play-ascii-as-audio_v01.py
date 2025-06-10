import pyaudio
import numpy as np

# Parameters
duration = 0.1  # seconds per character
sample_rate = 44100  # Hz

# Open the log file
with open('./research_records/log-2025-04-30T14:05:55.txt', 'r') as f:
    lines = f.readlines()

# Initialize PyAudio
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paFloat32,
                channels=1,
                rate=sample_rate,
                output=True)

# Function to generate a tone for a given character
def char_to_freq(c):
    # Simple mapping: ASCII value scaled to audible range
    return 200 + (ord(c) % 80) * 10  # frequencies between 200Hz and 1000Hz

def generate_tone(freq, duration):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = np.sin(freq * t * 2 * np.pi)
    return tone.astype(np.float32)

# Play each character as a tone
for line in lines:
    for char in line:
        freq = char_to_freq(char)
        tone = generate_tone(freq, duration)
        stream.write(tone.tobytes())

stream.stop_stream()
stream.close()
p.terminate()
