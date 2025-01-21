# import manim
# import manim.scene


# class scene(manim.Scene):
#     def construct(self):
#         text = manim.Text('noice')
#         self.play(manim.Write(text))



import tkinter as tk
from tkinter import messagebox, scrolledtext
from PIL import Image, ImageTk
import threading
import sounddevice as sd
import numpy as np
import wavio
import openai
from gtts import gTTS
import pygame
import os
import time
# import whisper  # If using local Whisper model


# Global variables
recording = False
audio_frames = []
fs = 16000  # Sampling rate
audio_filename = "input_audio.wav"
output_audio_filename = "output_audio.mp3"

# Function to start recording
def start_recording():
    global recording, audio_frames
    recording = True
    audio_frames = []
    status_label.config(text="Recording...")
    record_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.NORMAL)
    threading.Thread(target=record).start()

# Function to stop recording
def stop_recording():
    global recording
    recording = False
    status_label.config(text="Processing...")
    record_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.DISABLED)
    threading.Thread(target=process_audio).start()

# Recording function
def record():
    global audio_frames
    with sd.InputStream(samplerate=fs, channels=1, callback=audio_callback):
        while recording:
            sd.sleep(100)

# Callback function to collect audio data
def audio_callback(indata, frames, time, status):
    audio_frames.append(indata.copy())

# Function to process the recorded audio
def process_audio():
    # Save the recorded audio to a file
    try:
        status_label.config(text="Saving Audio...")
        audio_data = np.concatenate(audio_frames, axis=0)
        wavio.write(audio_filename, audio_data, fs, sampwidth=2)

        # Transcribe audio to text
        status_label.config(text="Transcribing...")
        transcribed_text = transcribe_audio(audio_filename)
        transcribed_textbox.delete(1.0, tk.END)
        transcribed_textbox.insert(tk.END, transcribed_text)
        print("Transcribed Text:", transcribed_text)

        # Get response from ChatGPT
        status_label.config(text="Generating Response...")
        response_text = chat_with_gpt(transcribed_text)
        response_textbox.delete(1.0, tk.END)
        response_textbox.insert(tk.END, response_text)
        print("ChatGPT Response:", response_text)

        # Convert response to speech
        status_label.config(text="Converting Text to Speech...")
        text_to_speech(response_text, output_audio_filename)

        # Play the audio
        status_label.config(text="Playing Audio...")
        play_audio(output_audio_filename)

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n\n{e}")
    finally:
        # Reset buttons and status label
        status_label.config(text="Ready")
        record_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)

        # Clean up audio files (optional)
        if os.path.exists(audio_filename):
            os.remove(audio_filename)
        if os.path.exists(output_audio_filename):
            os.remove(output_audio_filename)

# Function to transcribe audio using Whisper API or local model
def transcribe_audio(filename):
    try:
        # Using OpenAI Whisper API
        with open(filename, "rb") as audio_file:
            response = openai.Audio.transcribe(
                file=audio_file,
                model="whisper-1",
                language="ar"
            )
        return response["text"]

        # Uncomment below if using local Whisper model
        '''
        status_label.config(text="Loading Whisper Model...")
        model = whisper.load_model("base")
        result = model.transcribe(filename, language="ar")
        return result["text"]
        '''

    except Exception as e:
        messagebox.showerror("Error", f"Transcription failed:\n\n{e}")
        return ""

# Function to interact with ChatGPT API
def chat_with_gpt(transcribed_text):
    if not transcribed_text:
        return "لم يتم الحصول على نص من التسجيل."
    try:
        prompt = "أنت معلم مفيد يشرح المفاهيم بوضوح باللغة العربية."  # Arabic prompt for acting as a teacher
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcribed_text},
        ]
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        reply = response['choices'][0]['message']['content']
        return reply
    except Exception as e:
        messagebox.showerror("Error", f"ChatGPT API call failed:\n\n{e}")
        return "حدث خطأ أثناء الحصول على الاستجابة."

# Function to convert text to speech using gTTS
def text_to_speech(text, output_filename):
    try:
        tts = gTTS(text=text, lang='ar')
        tts.save(output_filename)
        print(f'Audio content written to file "{output_filename}"')
    except Exception as e:
        messagebox.showerror("Error", f"Text-to-Speech conversion failed:\n\n{e}")

# Function to play the audio file using pygame
def play_audio(filename):
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.quit()
    except Exception as e:
        messagebox.showerror("Error", f"Audio playback failed:\n\n{e}")

# Function to initialize the GUI
def init_gui():
    global root, record_button, stop_button, status_label, transcribed_textbox, response_textbox
    root = tk.Tk()
    root.title("Arabic Speech Assistant")

    # Set window size and position
    window_width = 600
    window_height = 600
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_coord = (screen_width/2) - (window_width/2)
    y_coord = (screen_height/2) - (window_height/2)
    root.geometry(f"{window_width}x{window_height}+{int(x_coord)}+{int(y_coord)}")
    root.configure(bg="#2b0311")
    
    
    # Create and place buttons
    record_button = tk.Button(root, text="Record", command=start_recording, width=15, height=2)
    record_button.pack(pady=10)

    stop_button = tk.Button(root, text="Stop", command=stop_recording, width=15, height=2, state=tk.DISABLED)
    stop_button.pack(pady=10)

    # Status label
    status_label = tk.Label(root, text="Ready", font=("Helvetica", 20),bg="#2b0311",fg="white")
    status_label.pack(pady=10)

    # Transcribed text label and textbox
    transcribed_label = tk.Label(root, text="Transcribed Text:", font=("Helvetica", 20),bg="#2b0311",fg="white")
    transcribed_label.pack(pady=5)
    transcribed_textbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=5, font=("Helvetica", 20),bg="#1f1f1f",fg="white")
    transcribed_textbox.pack(pady=5)

    # Response text label and textbox
    response_label = tk.Label(root, text="Faris Response:", font=("Helvetica", 20),bg="#2b0311",fg="white")
    response_label.pack(pady=5)
    response_textbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=10, font=("Helvetica", 20),bg="#1f1f1f",fg="white")
    response_textbox.pack(pady=5)

    # Start the GUI loop
    root.mainloop()

# Main function
def main():
    # Set up OpenAI API key
    openai.api_key = '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'   # Replace with your OpenAI API key

    # Initialize Pygame mixer
    pygame.mixer.init()

    # Initialize the GUI
    init_gui()

if __name__ == "__main__":
    main()
