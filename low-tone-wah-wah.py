# low_tone_wah_wah.py
import board, synthio, audiobusio, adafruit_vl53l1x, array, math, time, neopixel
from adafruit_led_animation.color import RED, YELLOW, ORANGE, GREEN, TEAL, CYAN, BLUE, PURPLE, MAGENTA, GOLD, PINK, AQUA, JADE, AMBER, OLD_LACE, WHITE, BLACK
INDIGO = (63, 0, 255)
VIOLET = (127 ,0, 255)

colors = [RED, ORANGE, YELLOW, GREEN, CYAN, BLUE, INDIGO, VIOLET, PINK, WHITE]

# the "blob_size" refers to how many lights light up
blob_size = 30
num_of_lights = 336
strip = neopixel.NeoPixel(board.GP6, num_of_lights, brightness=0.5, auto_write=False)
strip.fill(BLACK)
strip.show()

# --- Setup Audio Output ---
audio = audiobusio.I2SOut(bit_clock=board.GP10,
                          word_select=board.GP9,
                          data=board.GP11)
synth = synthio.Synthesizer(sample_rate=22050)
audio.play(synth)

# --- Sine waveform for smooth resonance ---
def make_sine_wave(samples=256):
    return array.array("h", [int(30000 * math.sin(2 * math.pi * i / samples)) for i in range(samples)])

waveform = make_sine_wave()

# --- Setup Distance Sensor ---
i2c = board.STEMMA_I2C()
distance_sensor = adafruit_vl53l1x.VL53L1X(i2c)
distance_sensor.timing_budget = 100
distance_sensor.start_ranging()

# --- Envelope with sustain for gentle wah effect ---
amp_env = synthio.Envelope(attack_time=0.6, decay_time=0.4, sustain_level=0.7, release_time=1.2)

# --- Tuning values ---
min_cm = 10
max_cm = 90
min_freq = 27.5     # A0
max_freq = 220.0    # A3
min_amp = 0.2
max_amp = 0.5

num_oscillators = 4
max_detune = 0.008

print("🌊 Deep Swell Blob (Low Tone + Light) running!")

active_notes = []
is_playing = False
last_amp = 0
fade_counter = 0

def update_lights(norm, amp, fade=False):
    blob_height = int(norm * num_of_lights)
    blob_color = colors[int(norm * (len(colors) - 1))]

    for i in range(num_of_lights):
        distance_from_blob_center = abs(i - blob_height)
        if amp < 0.12:
            strip[i] = (0, 0, 0)
        elif distance_from_blob_center < blob_size:
            fluctuation = 0.5 + 0.3 * math.sin(time.monotonic() * 3 + i / 4)
            brightness = (1 - (distance_from_blob_center / blob_size)) * fluctuation * amp
            brightness = min(brightness, 1.0)
            color = tuple(int(c * brightness) for c in blob_color)
            strip[i] = color
        else:
            if fade:
                faded = tuple(int(c * 0.7) for c in strip[i])
                strip[i] = faded if max(faded) > 5 else (0, 0, 0)
            else:
                strip[i] = (0, 0, 0)
    strip.show()

while True:
    if distance_sensor.data_ready:
        cm = distance_sensor.distance or 999
        distance_sensor.clear_interrupt()

        if cm > max_cm:
            if is_playing:
                synth.release(active_notes)
                active_notes.clear()
                is_playing = False
                fade_counter = 24  # trigger light fade
        else:
            norm = 1 - (min(max(cm, min_cm), max_cm) - min_cm) / (max_cm - min_cm)
            freq = min_freq * (max_freq / min_freq) ** norm
            amp = min_amp + norm * (max_amp - min_amp)

            if not is_playing:
                print(f"Triggering at {cm:.1f} cm → {freq:.1f} Hz @ {amp:.2f}")
                for i in range(num_oscillators):
                    detune = 1 + ((i - num_oscillators // 2) * max_detune)
                    f = freq * detune
                    note = synthio.Note(frequency=f, amplitude=amp,
                                        waveform=waveform, envelope=amp_env)
                    synth.press(note)
                    active_notes.append(note)
                is_playing = True
            else:
                for i, note in enumerate(active_notes):
                    detune = 1 + ((i - num_oscillators // 2) * max_detune)
                    note.frequency = freq * detune
                    note.amplitude = amp

            update_lights(norm, amp)
            last_amp = amp
        time.sleep(0.05)

    elif fade_counter > 0:
        update_lights(0.0, last_amp, fade=True)
        fade_counter -= 1
        time.sleep(0.05)
