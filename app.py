# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import sounddevice as sd
import numpy as np
from elevenlabs import ElevenLabs, VoiceSettings
import wavio
import openai
import pygame
import os
from PIL import Image, ImageTk, ImageSequence
import subprocess
import sys

if sys.platform.startswith('win'):
    os.add_dll_directory(r"C:\Program Files\VideoLAN\VLC")  # Update the path if necessary
import vlc

# Ensure that the OpenAI Assistant Event Handler is imported
from openai import AssistantEventHandler

# Set the OpenAI API key
openai.api_key = os.getenv('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')
ASSISTANT_ID = "asst_FDuUSbtE6aPgnDdUYV1lKgyE"
conversation_thread_id = None
print("check after:", conversation_thread_id)  # Debug print
conversation_lock = threading.Lock()
animation_id = None

# Global variables for audio and video
recording = False
audio_frames = []
fs = 16000  # Sample rate
audio_filename = "input_audio.wav"
output_audio_filename = "output_audio.mp3"
VIDEO_STOP_SECONDS_BEFORE_END = 0  # To play the entire video

# Control variable for GIF (used in functions to display and stop animations)
gif_stop_event = None


# Functions for displaying and stopping GIF animations - Improved version
def display_gif(gif_path, stop_event, gif_label, root):
    """
    This function displays a GIF file in the specified Label and loops through the frames
    until a stop event is signaled.
    """
    try:
        gif = Image.open(gif_path)
        frames = [ImageTk.PhotoImage(frame.copy()) for frame in ImageSequence.Iterator(gif)]
        frame_count = len(frames)

        def animate(index):
            if not stop_event.is_set():
                frame = frames[index]
                root.after(0, update_frame, frame)
                # Get the frame duration from the GIF info (default is 100 milliseconds)
                duration = gif.info.get('duration', 100)
                next_index = (index + 1) % frame_count
                root.after(int(duration), animate, next_index)
            else:
                root.after(0, clear_frame)

        def update_frame(frame):
            gif_label.config(image=frame)
            gif_label.image = frame  # Important to keep a reference to the image in memory

        def clear_frame():
            gif_label.config(image='')
            gif_label.image = None

        animate(0)

    except Exception as e:
        print(f"Error displaying GIF: {e}")

def start_gif_animation(gif_path, gif_label, root):
    """
    Starts the GIF animation in a separate thread.
    """
    global gif_stop_event
    if gif_stop_event:
        gif_stop_event.set()
    gif_stop_event = threading.Event()
    threading.Thread(target=display_gif, args=(gif_path, gif_stop_event, gif_label, root), daemon=True).start()

def stop_gif_animation():
    """
    Stops the GIF animation by setting the event.
    """
    global gif_stop_event
    if gif_stop_event:
        gif_stop_event.set()


# Definition of the event handler class for streaming responses from the assistant
class ResponseEventHandler(AssistantEventHandler):
    def __init__(self, textbox):
        super().__init__()
        self.textbox = textbox
        self.response = ""  # To accumulate the full response

    def on_text_created(self, text) -> None:
        # When the response begins, insert the response indicator into the display box
        self.textbox.insert(tk.END, "\nFaris: ", "bold")
        self.textbox.yview(tk.END)

    def on_text_delta(self, delta, snapshot):
        # Update the response incrementally in the display box
        self.response += delta.value
        self.textbox.insert(tk.END, delta.value)
        self.textbox.yview(tk.END)


# Functions for recording and processing audio
def start_recording():
    global recording, audio_frames
    recording = True
    audio_frames = []
    status_label.config(text="Recording...")
    threading.Thread(target=record, daemon=True).start()

def stop_recording():
    global recording
    recording = False
    status_label.config(text="Processing...")
    threading.Thread(target=process_audio, daemon=True).start()

def record():
    global audio_frames
    with sd.InputStream(samplerate=fs, channels=1, callback=audio_callback):
        while recording:
            sd.sleep(100)

def audio_callback(indata, frames, time_info, status):
    audio_frames.append(indata.copy())


# Audio processing function: saving the recording, transcribing to text,
# calling ChatGPT to convert the text to a response, and generating audio and video
def process_audio():
    global gif_label, root
    try:
        # Start displaying the GIF animation during processing
        start_gif_animation("gifs/thinking.gif", gif_label, root)

        status_label.config(text="Saving Audio...")
        audio_data = np.concatenate(audio_frames, axis=0)
        wavio.write(audio_filename, audio_data, fs, sampwidth=2)

        # Convert audio to text using OpenAI's Whisper API
        status_label.config(text="Transcribing...")
        transcribed_text = transcribe_audio(audio_filename)
        transcribed_textbox.delete(1.0, tk.END)
        transcribed_textbox.insert(tk.END, transcribed_text)
        print("Transcribed Text:", transcribed_text)

        # Get the response from ChatGPT using continuous conversation and streaming the response
        status_label.config(text="Generating Response...")
        response_text = chat_with_gpt(transcribed_text)
        response_textbox.delete(1.0, tk.END)
        response_textbox.insert(tk.END, response_text)
        print("ChatGPT Response:", response_text)

        # Convert the response to speech using ElevenLabs
        status_label.config(text="Converting Text to Speech...")
        text_to_speech(response_text, output_audio_filename)

        # Merge audio and video
        status_label.config(text="Merging Audio and Video...")
        merged_video_path = "./media/videos/merged_output.mp4"
        merge_audio_and_video("./media/videos/arabic_text_animation.mp4", output_audio_filename, merged_video_path)

        # Stop the "thinking" GIF and start the "explaining" GIF
        stop_gif_animation()
        start_gif_animation("gifs/explaining.gif", gif_label, root)

        # Play the merged video using VLC in a separate thread
        status_label.config(text="Playing Video...")
        threading.Thread(target=play_video_with_vlc, args=(merged_video_path,), daemon=True).start()

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n\n{e}")
    finally:
        status_label.config(text="Ready")

def transcribe_audio(filename):
    try:
        # Use the Whisper API to convert audio to text
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


# Function to interact with ChatGPT using continuous conversation and streaming responses
def chat_with_gpt(transcribed_text):

    global conversation_thread_id
    if not transcribed_text:
        return "No text was obtained from the recording."
    try:
        # Create a new conversation if the conversation ID does not exist
        if conversation_thread_id is None:
            thread = openai.beta.threads.create()
            conversation_thread_id = thread.id
            print("Created a new conversation with ID:", conversation_thread_id)
        else:
            print("Reusing the current conversation ID:", conversation_thread_id)
        thread_id = conversation_thread_id

        # Send the user's message to the conversation
        openai.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=transcribed_text,
        )
        print("User message sent:", transcribed_text)

        # Stream the response incrementally from the assistant using ResponseEventHandler
        event_handler = ResponseEventHandler(response_textbox)
        with openai.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
            event_handler=event_handler
        ) as stream:
            stream.until_done()
        print("Final assistant response:", event_handler.response)
        return event_handler.response

    except Exception as e:
        print("Error in chat_with_gpt:", e)
        return f"Error: {e}"


# Function to convert text to speech using ElevenLabs
def text_to_speech(text, output_filename):
    try:
        client = ElevenLabs(api_key="sk_274b05820004e924913b674d3c4181aae2b89df0f66a2806")

        voice_settings = VoiceSettings(
            stability=0.75,        # Voice stability
            similarity_boost=0.6,  # Similarity boost
            style=0.3,             # Speech style
            speed=0.1              # Speech speed
        )
        with open(output_filename, "wb") as file:
            audio_stream = client.text_to_speech.convert_as_stream(
                voice_id="egFWq5W0j5U7Q3RFFA8g",
                text=text,
                model_id="eleven_multilingual_v2",
                voice_settings=voice_settings
            )

            for chunk in audio_stream:
                file.write(chunk)

        if os.path.exists(output_filename):
            print(f"Audio file saved successfully as {output_filename}")
        else:
            raise Exception("Failed to save audio file.")

    except Exception as e:
        messagebox.showerror("Error", f"Text-to-Speech conversion failed: {e}")


# Functions to play audio and video, and merge them using ffmpeg and VLC
def play_audio(filename):
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
    except Exception as e:
        messagebox.showerror("Error", f"Audio playback failed:\n\n{e}")

def merge_audio_and_video(video_input, audio_input, output_path):
    try:
        command = [
            'ffmpeg',
            '-y',  # Overwrite existing files without asking
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

def play_video_with_vlc(video_path):
    global gif_label, root
    try:
        Instance = vlc.Instance()
        player = Instance.media_player_new()
        Media = Instance.media_new(video_path)
        Media.get_mrl()
        player.set_media(Media)

        # Set the video output to the Tkinter window
        if os.name == 'nt':  # For Windows systems
            player.set_hwnd(video_label.winfo_id())
        else:
            player.set_xwindow(video_label.winfo_id())

        # Start playback
        player.play()

        # Wait until playback finishes
        events = player.event_manager()
        event = threading.Event()

        def end_callback(event_type):
            event.set()

        events.event_attach(vlc.EventType.MediaPlayerEndReached, end_callback)
        event.wait()
        player.stop()

        # After the video ends, change the GIF to a static image or a different animation
        stop_gif_animation()
        start_gif_animation("gifs/bw.gif", gif_label, root)

    except Exception as e:
        messagebox.showerror("Error", f"Error playing video:\n\n{e}")


# Function to toggle recording state when the spacebar is pressed
def toggle_recording(event):
    global recording
    if not recording:
        start_recording()
    else:
        stop_recording()


# Main user interface using Tkinter
def init_gui():
    global root, status_label, transcribed_textbox, response_textbox, video_label, gif_label
    # Create the main window
    root = tk.Tk()
    root.title("Arabic Speech Assistant")
    # Set the window to full screen
    root.attributes("-fullscreen", True)
    # Set the window background color to black
    root.configure(bg="black")

    # Create a video frame (can be used if video display is needed)
    video_frame = tk.Frame(root, width=800, height=400, bg="black")
    video_frame.pack(pady=10)
    video_label = tk.Label(video_frame, bg="black")
    video_label.pack()

    # Create a Label to display GIF animations in the center of the window
    gif_label = tk.Label(root, bg="black")
    gif_label.place(relx=0.5, rely=1.0, anchor=tk.S)

    # Create text display boxes
    transcribed_label = tk.Label(root, text="Transcribed Text:", font=("Helvetica", 0), bg="black", fg="white")
    # transcribed_label.pack(pady=5)
    transcribed_textbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=0, height=0,
                                                     font=("Helvetica", 0), bg="#1f1f1f", fg="white")
    # transcribed_textbox.pack(pady=5)

    response_label = tk.Label(root, text="Faris Response:", font=("Helvetica", 0), bg="black", fg="white")
    # response_label.pack(pady=5)
    response_textbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=0, height=0,
                                                  font=("Helvetica", 0), bg="#1f1f1f", fg="white")
    # response_textbox.pack(pady=5)

    # Status label
    status_label = tk.Label(root, text="Ready", font=("Helvetica", 0), bg="black", fg="white")
    # status_label.pack(pady=0)

    # Start the initial GIF animation (e.g., bw image)
    start_gif_animation("gifs/bw.gif", gif_label, root)

    # Bind the spacebar to toggle the recording state
    root.bind("<space>", toggle_recording)
    # Allow exiting full screen mode by pressing the ESC key
    def exit_fullscreen(event):
        root.attributes("-fullscreen", False)
        root.destroy()  # Close the window
    root.bind("<Escape>", exit_fullscreen)

    root.mainloop()


# Main function
def main():
    # Set the OpenAI API key (you can use environment variables)
    openai.api_key = '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'
            
    # Initialize the audio player (Pygame)
    pygame.mixer.init()

    # Start the user interface
    init_gui()

if __name__ == "__main__":
    main()
