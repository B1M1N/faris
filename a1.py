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
import time

if sys.platform.startswith('win'):
    os.add_dll_directory(r"C:\Program Files\VideoLAN\VLC")  # في حال الحاجة إلى مسار VLC على ويندوز

import vlc

# ثبّت قيم مفاتيح الـAPI حسب حاجتك
openai.api_key = "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"  
ELEVENLABS_API_KEY = "sk_274b05820004e924913b674d3c4181aae2b89df0f66a2806"

ASSISTANT_ID = "asst_FDuUSbtE6aPgnDdUYV1lKgyE"

# ===================
# المتغيرات العامة
# ===================
recording = False  # حالة التسجيل
audio_frames = []
fs = 16000  # معدّل أخذ العينات
audio_filename = "input_audio.wav"
output_audio_filename = "output_audio.mp3"

gif_stop_event = None  # للتحكم في إيقاف رسم الـGIF على الشاشة
root = None
gif_label = None
status_label = None
record_button = None
stop_button = None

# ===================
# دوال رئيسية
# ===================

def start_recording():
    """
    بدء التسجيل الصوتي
    """
    global recording, audio_frames

    recording = True
    audio_frames = []
    status_label.config(text="Recording...")
    record_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.NORMAL)

    # بدء التسجيل في خيط منفصل
    threading.Thread(target=record).start()


def stop_recording():
    """
    إيقاف التسجيل وبدء عملية المعالجة (التحويل إلى نصّ، ثم الرد الصوتي...)
    """
    global recording
    recording = False
    status_label.config(text="Processing...")
    record_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.DISABLED)

    threading.Thread(target=process_audio).start()


def record():
    """
    الدالة التي تتولّى استقبال البيانات الصوتية من الميكروفون.
    """
    with sd.InputStream(samplerate=fs, channels=1, callback=audio_callback):
        while recording:
            sd.sleep(100)  # انتظار بسيط حتى لا يُشغل المعالج


def audio_callback(indata, frames, time_, status):
    """
    تجميع البيانات الصوتية في مصفوفة عامة.
    """
    audio_frames.append(indata.copy())


def process_audio():
    """
    المعالجة الكاملة للصوت: الحفظ، التفريغ النصّي، طلب الرد من ChatGPT،
    تحويل الرد إلى صوت، ثم تشغيله مع عرض GIF المناسب.
    """
    try:
        # عرض GIF التفكير
        start_gif_animation("gifs/thinking.gif")

        # حفظ الصوت المُسجّل
        status_label.config(text="Saving Audio...")
        audio_data = np.concatenate(audio_frames, axis=0)
        wavio.write(audio_filename, audio_data, fs, sampwidth=2)

        # التفريغ النصي بواسطة Whisper
        status_label.config(text="Transcribing...")
        transcribed_text = transcribe_audio(audio_filename)
        print("Transcribed Text:", transcribed_text)

        # استدعاء ChatGPT بالمدخل
        status_label.config(text="Generating Response...")
        response_text = chat_with_gpt(transcribed_text)
        print("ChatGPT Response:", response_text)

        # تحويل الرد إلى صوت عبر ElevenLabs
        status_label.config(text="Converting Text to Speech...")
        text_to_speech(response_text, output_audio_filename)

        # إيقاف GIF التفكير
        stop_gif_animation()

        # تشغيل الصوت الناتج
        play_audio(output_audio_filename)

        # تشغيل GIF الشرح (يمكنك استبدال المسار بصورة أخرى إن أحببت)
        start_gif_animation("gifs/explaining.gif")

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n\n{e}")
    finally:
        # عند الانتهاء إعادة الواجهة إلى وضع الاستعداد
        status_label.config(text="Ready")
        record_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)


def transcribe_audio(filename):
    """
    استخدام واجهة OpenAI (Whisper) لتفريغ الملف الصوتي إلى نص.
    """
    try:
        with open(filename, "rb") as audio_file:
            response = openai.Audio.transcribe(
                model="whisper-1",
                file=audio_file,
                language="ar"  # يمكن حذفها أو تغييرها حسب اللغة المرادة
            )
        return response["text"]
    except Exception as e:
        messagebox.showerror("Error", f"Transcription failed:\n\n{e}")
        return ""


def chat_with_gpt(transcribed_text):
    """
    إرسال النص لواجهة ChatGPT واستقبال الرد بالعربية.
    """
    if not transcribed_text:
        return "لم يتم الحصول على نص من التسجيل."
    try:
        # إنشاء ثريد جديد في OpenAI
        thread = openai.beta.threads.create()
        thread_id = thread.id

        # إرسال رسالة المستخدم
        openai.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=transcribed_text,
        )

        # تشغيل المساعد
        run = openai.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
        )

        # الانتظار لحين اكتمال الرد
        while run.status not in ["completed", "failed"]:
            time.sleep(1)
            run = openai.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id,
            )

        # جلب الرد
        messages = openai.beta.threads.messages.list(thread_id=thread_id)
        for message in reversed(messages.data):
            if message.role == "assistant":
                reply = "\n".join(block.text.value for block in message.content if hasattr(block, "text")) + ""
                return reply

    except Exception as e:
        return f"❌ حدث خطأ أثناء الحصول على الاستجابة: {e}"


def text_to_speech(text, output_filename):
    """
    تحويل النص إلى صوت عبر ElevenLabs.
    """
    try:
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

        voice_settings = VoiceSettings(
            stability=0.75,
            similarity_boost=0.6,
            style=0.3,
            speed=0.1
        )

        with open(output_filename, "wb") as file:
            audio_stream = client.text_to_speech.convert_as_stream(
                voice_id="egFWq5W0j5U7Q3RFFA8g",  # يمكنك وضع الهوية الخاصة بصوتك من ElevenLabs
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


def play_audio(filename):
    """
    تشغيل ملف صوتي باستخدام Pygame.
    """
    try:
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
    except Exception as e:
        messagebox.showerror("Error", f"Audio playback failed:\n\n{e}")


# ===================
# دوال GIF
# ===================

def display_gif(gif_path, stop_event):
    """
    عرض GIF بشكل مستمر حتى وصول إشارة التوقف stop_event.
    """
    try:
        gif = Image.open(gif_path)
        frames = [ImageTk.PhotoImage(frame.copy()) for frame in ImageSequence.Iterator(gif)]
        frame_count = len(frames)

        def animate(index):
            if not stop_event.is_set():
                frame = frames[index]
                root.after(0, update_frame, frame)
                next_index = (index + 1) % frame_count
                # يتحكم في سرعة تناوب الإطارات حسب مدة كل إطار في GIF
                root.after(int(gif.info.get('duration', 100)), animate, next_index)
            else:
                # عند الإيقاف
                root.after(0, clear_frame)

        def update_frame(frame):
            gif_label.config(image=frame)
            gif_label.image = frame  # ضرورة الاحتفاظ بالمرجع

        def clear_frame():
            gif_label.config(image='')
            gif_label.image = None

        animate(0)

    except Exception as e:
        messagebox.showerror("Error", f"Error displaying GIF:\n\n{e}")


def start_gif_animation(gif_path):
    """
    بدء تشغيل الـGIF.
    """
    global gif_stop_event
    if gif_stop_event:
        gif_stop_event.set()

    gif_stop_event = threading.Event()
    threading.Thread(target=display_gif, args=(gif_path, gif_stop_event)).start()


def stop_gif_animation():
    """
    إيقاف عرض الـGIF.
    """
    global gif_stop_event
    if gif_stop_event:
        gif_stop_event.set()


# ===================
# دوال واجهة المستخدم
# ===================

def on_space_pressed(event):
    """
    عند ضغط زر المسافة: البدء/الإيقاف للتسجيل.
    """
    toggle_recording()


def toggle_recording():
    """
    إذا كنا في وضع التسجيل فأوقفه، وإن لم نكن فابدأ التسجيل.
    """
    if not recording:
        start_recording()
    else:
        stop_recording()


def init_gui():
    """
    تهيئة واجهة المستخدم الرسومية (Tkinter).
    """
    global root, record_button, stop_button, status_label, gif_label
    root = tk.Tk()
    root.title("Arabic Speech Assistant")

    # حجم النافذة وموقعها
    window_width = 800
    window_height = 800
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_coord = int((screen_width / 2) - (window_width / 2))
    y_coord = int((screen_height / 2) - (window_height / 2))
    root.geometry(f"{window_width}x{window_height}+{x_coord}+{y_coord}")
    root.configure(bg="#000000")

    # إضافة اختصار زر المسافة
    root.bind("<space>", on_space_pressed)

    # مكان الـGIF
    gif_label = tk.Label(root)
    gif_x = 200
    gif_y = 200
    gif_label.place(x=gif_x, y=gif_y)

    # زر تسجيل
    record_button = tk.Button(root, text="Record (Space)", command=start_recording, width=15, height=2,
                              bg="#4CAF50", fg="white")
    record_button.pack(pady=10)

    # زر إيقاف
   

    # تهيئة مشغّل الصوت Pygame
    pygame.mixer.init()

    # بدء الحلقة الرئيسية
    root.mainloop()


def main():
    # يمكن وضع تعيين لمفاتيح الـAPI هنا أيضًا (أو استخدام المتغيرات العالمية)
    # openai.api_key = os.getenv("OPENAI_API_KEY", "default_key")
    # ...
    # بدء تشغيل GIF البداية
    start_gif_animation("gifs/bw.gif")

    # تهيئة الواجهة
    init_gui()


if __name__ == "__main__":
    main()
