# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import sounddevice as sd
import numpy as np
from elevenlabs import ElevenLabs,VoiceSettings
import numpy as np
import wavio
import openai
import pygame
import os
from PIL import Image, ImageTk,ImageSequence
import subprocess
import sys
import time
if sys.platform.startswith('win'):
    os.add_dll_directory(r"C:\Program Files\VideoLAN\VLC")  # Update this path if necessary
#ldeGOUQJqLGjlVgYn7YL
import vlc
openai.api_key = os.getenv('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' )
ASSISTANT_ID = "asst_FDuUSbtE6aPgnDdUYV1lKgyE"

# Global variables
recording = False
audio_frames = []
fs = 16000  # Sampling rate
audio_filename = "input_audio.wav"
output_audio_filename = "output_audio.mp3"
VIDEO_STOP_SECONDS_BEFORE_END = 0  # Play the full video
gif_stop_event = None  # Event to control GIF animation
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
    try:
        # Start the Thinking GIF
        start_gif_animation("gifs/thinking.gif")

        status_label.config(text="Saving Audio...")
        audio_data = np.concatenate(audio_frames, axis=0)
        wavio.write(audio_filename, audio_data, fs, sampwidth=2)

        # Transcribe audio to text
        status_label.config(text="Transcribing...")
        transcribed_text = transcribe_audio(audio_filename)
        transcribed_textbox.delete(1.0, tk.END)
        transcribed_textbox.insert(tk.END, transcribed_text)
       # transcribed_text="عرف بنفسك"
        print("Transcribed Text:", transcribed_text)

        # Get response from ChatGPT
        status_label.config(text="Generating Response...")
        response_text = chat_with_gpt(transcribed_text)
        response_textbox.delete(1.0, tk.END)
        response_textbox.insert(tk.END, response_text)
        print("ChatGPT Response:", response_text)

        # Generate Manim animation with the response text
       # status_label.config(text="Generating Animation...")
        #generate_manim_animation(response_text)

        # Convert response to speech
        status_label.config(text="Converting Text to Speech...")
        text_to_speech(response_text, output_audio_filename)

        # Merge audio and video
        status_label.config(text="Merging Audio and Video...")
        merged_video_path = "./media/videos/merged_output.mp4"
        merge_audio_and_video("./media/videos/arabic_text_animation.mp4", output_audio_filename, merged_video_path)

        # Stop the Thinking GIF and start the Explanation GIF
        stop_gif_animation()
        start_gif_animation("gifs/explaining.gif")

        # Play the merged video
        status_label.config(text="Playing Video...")
        threading.Thread(target=play_video_with_vlc, args=(merged_video_path,)).start()

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n\n{e}")
    finally:
        # Reset buttons and status label
        status_label.config(text="Ready")
        record_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)

   

def transcribe_audio(filename):
    try:
        # Using OpenAI Whisper API
        with open(filename, "rb") as audio_file:
            response = openai.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                language="ar"
            )
        return response.text
    except Exception as e:
        messagebox.showerror("Error", f"Transcription failed:\n\n{e}")
        return ""
    
# Function to interact with ChatGPT API
def chat_with_gpt(transcribed_text):
    if not transcribed_text:
        return "لم يتم الحصول على نص من التسجيل."
    try:
        # Create a new thread (optional: can reuse an existing thread)
        thread = openai.beta.threads.create()
        thread_id = thread.id

        # Send the transcribed text to the assistant
        openai.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=transcribed_text,
        )

        # Run the assistant
        run = openai.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
        )

        # Wait for response
        while run.status not in ["completed", "failed"]:
            time.sleep(1)
            run = openai.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id,
            )

        # Fetch assistant's response
        messages = openai.beta.threads.messages.list(thread_id=thread_id)
        for message in reversed(messages.data):
            if message.role == "assistant":
                reply = "\n".join(block.text.value for block in message.content if hasattr(block, "text")) + ""
                return reply

    except Exception as e:
        return f"❌ حدث خطأ أثناء الحصول على الاستجابة: {e}"


# Function to convert text to speech using OpenAI


def text_to_speech(text, output_filename):
    try:
        client = ElevenLabs(api_key="sk_274b05820004e924913b674d3c4181aae2b89df0f66a2806")

        voice_settings = VoiceSettings(
            stability=0.75,        
            similarity_boost=0.6,   
            style=0.3,              
            speed=0.1 
        )
        with open(output_filename, "wb") as file:
            audio_stream = client.text_to_speech.convert_as_stream(
                voice_id="egFWq5W0j5U7Q3RFFA8g",
                text=text,
                model_id="eleven_multilingual_v2",
                voice_settings=voice_settings  # تمرير كائن الإعدادات
            )

            for chunk in audio_stream:
                file.write(chunk)

      
        if os.path.exists(output_filename):
            print(f"Audio file saved successfully as {output_filename}")
        else:
            raise Exception("Failed to save audio file.")

    except Exception as e:
        messagebox.showerror("Error", f"Text-to-Speech conversion failed: {e}")

    
'''def text_to_speech(text, output_filename):
    try:
        response = openai.audio.speech.create(
        model="tts-1",  
        voice="coral",
        input=text
        )

        response.stream_to_file(output_filename)
    except Exception as e:
        messagebox.showerror("Error", f"Text-to-Speech conversion failed: {e}")'''



# Function to play the audio file using pygame
def play_audio(filename):
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        # Do not block; allow playback to continue independently
    except Exception as e:
        messagebox.showerror("Error", f"Audio playback failed:\n\n{e}")



def merge_audio_and_video(video_input, audio_input, output_path):
    try:
        command = [
            'ffmpeg',
            '-y',  # Overwrite output files without asking
            '-i', video_input,
            '-i', audio_input,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-strict', 'experimental',
            output_path
        ]
        subprocess.run(command, check=True)
        print(f"Audio and video merged into {output_path}")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Failed to merge audio and video:\n\n{e}")
# Function to play the video once without looping and keep the last frame
def play_video_with_vlc(video_path):
    try:
        Instance = vlc.Instance()
        player = Instance.media_player_new()
        Media = Instance.media_new(video_path)
        Media.get_mrl()
        player.set_media(Media)

        # Set the video output to the Tkinter window
        if os.name == 'nt':  # For Windows
            player.set_hwnd(video_label.winfo_id())
        else:
            player.set_xwindow(video_label.winfo_id())

        # Start playing
        player.play()

        # Wait until playback is finished
        events = player.event_manager()
        event = threading.Event()

        def end_callback(event_type):
            event.set()

        events.event_attach(vlc.EventType.MediaPlayerEndReached, end_callback)

        # Wait for the playback to finish
        event.wait()

        # Stop the player after playback
        player.stop()

        # Stop the Explanation GIF after playback
        stop_gif_animation()
        start_gif_animation("gifs/bw.gif")

    except Exception as e:
        messagebox.showerror("Error", f"Error playing video:\n\n{e}")


def init_gui():

    global root, record_button, stop_button, status_label, transcribed_textbox, response_textbox, video_label,gif_label
    root = tk.Tk()
    root.title("Arabic Speech Assistant")

    # Set window size and position
    window_width = 800
    window_height = 800
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_coord = int((screen_width / 2) - (window_width / 2))
    y_coord = int((screen_height / 2) - (window_height / 2))
    root.geometry(f"{window_width}x{window_height}+{x_coord}+{y_coord}")
    root.configure(bg="#2b0311")

     # Create a frame to hold the video
    video_frame = tk.Frame(root, width=800, height=400)
    video_frame.pack(pady=10)

    # Create a label to display the video
    video_label = tk.Label(video_frame)
    video_label.pack()

    # Create a label to display the video
    video_label = tk.Label(root)
    video_label.pack(pady=10)

       # Create a label to display the GIF animations
    gif_label = tk.Label(root)

    # Set the desired x and y coordinates for the GIF
    gif_x = 0  # Replace with your desired x coordinate
    gif_y = 0  # Replace with your desired y coordinate

    gif_label.place(x=gif_x, y=gif_y)

    # Initial image or placeholder
    placeholder_image = ImageTk.PhotoImage(Image.new('RGB', (600, 400), color='#2b0311'))
    video_label.config(image=placeholder_image)
    video_label.image = placeholder_image  # Keep a reference

    # Create and place buttons
    record_button = tk.Button(root, text="Record", command=start_recording, width=15, height=2,
                              bg="#4CAF50", fg="white")
    record_button.pack(pady=10)

    stop_button = tk.Button(root, text="Stop", command=stop_recording, width=15, height=2, state=tk.DISABLED,
                            bg="#F44336", fg="white")
    stop_button.pack(pady=10)

    # Status label
    status_label = tk.Label(root, text="Ready", font=("Helvetica", 20), bg="#2b0311", fg="white")
    status_label.pack(pady=10)

    # Transcribed text label and textbox
    transcribed_label = tk.Label(root, text="Transcribed Text:", font=("Helvetica", 20), bg="#2b0311", fg="white")
    transcribed_label.pack(pady=5)
    transcribed_textbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=5,
                                                    font=("Helvetica", 20), bg="#1f1f1f", fg="white")
    transcribed_textbox.pack(pady=5)

    # Response text label and textbox
    response_label = tk.Label(root, text="Faris Response:", font=("Helvetica", 20), bg="#2b0311", fg="white")
    response_label.pack(pady=5)
    response_textbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=10,
                                                 font=("Helvetica", 20), bg="#1f1f1f", fg="white")
    response_textbox.pack(pady=5)

    # Start the GUI loop
    root.mainloop()
def display_gif(gif_path, stop_event):
    try:
        # Load the GIF
        gif = Image.open(gif_path)

        # Get the sequence of frames
        frames = [ImageTk.PhotoImage(frame.copy()) for frame in ImageSequence.Iterator(gif)]
        frame_count = len(frames)

        def animate(index):
            if not stop_event.is_set():
                frame = frames[index]
                # Schedule the frame update on the main thread
                root.after(0, update_frame, frame)
                # Schedule the next frame
                index = (index + 1) % frame_count
                root.after(int(gif.info['duration']), animate, index)
            else:
                # Clear the image when stopping
                root.after(0, clear_frame)

        def update_frame(frame):
            gif_label.config(image=frame)
            gif_label.image = frame  # Keep a reference

        def clear_frame():
            gif_label.config(image='')
            gif_label.image = None

        # Start the animation
        animate(0)

    except Exception as e:
        messagebox.showerror("Error", f"Error displaying GIF:\n\n{e}")

def start_gif_animation(gif_path):
    global gif_stop_event
    # Stop any existing GIF animation
    if gif_stop_event:
        gif_stop_event.set()

    gif_stop_event = threading.Event()
    threading.Thread(target=display_gif, args=(gif_path, gif_stop_event)).start()

def stop_gif_animation():
    global gif_stop_event
    if gif_stop_event:
        gif_stop_event.set()

# Main function
def main():
    # Set up OpenAI API key
    openai.api_key ='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' # Use environment variable for API key
            
    start_gif_animation("gifs/bw.gif")

    # Initialize Pygame mixer
    pygame.mixer.init()

    # Initialize the GUI
    init_gui()

if __name__ == "__main__":
    main()
