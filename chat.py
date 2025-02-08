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
    os.add_dll_directory(r"C:\Program Files\VideoLAN\VLC")  # حدّث المسار إذا لزم الأمر
import vlc

# تأكد من استيراد معالج أحداث المساعد من OpenAI
from openai import AssistantEventHandler

# تعيين مفتاح API الخاص بـ OpenAI
openai.api_key = os.getenv('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')
ASSISTANT_ID = "asst_FDuUSbtE6aPgnDdUYV1lKgyE"
conversation_thread_id = None
print("check after:", conversation_thread_id)  # Debug print
conversation_lock = threading.Lock()

# المتغيرات العامة للصوت والفيديو
recording = False
audio_frames = []
fs = 16000  # معدل العينات
audio_filename = "input_audio.wav"
output_audio_filename = "output_audio.mp3"
VIDEO_STOP_SECONDS_BEFORE_END = 0  # لتشغيل الفيديو بالكامل

# متغير تحكم للـ GIF (يُستخدم في دوال عرض وإيقاف الرسوم المتحركة)
gif_stop_event = None

###############################################
# دوال عرض وإيقاف الرسوم المتحركة (GIF) - النسخة المحسّنة
###############################################
def display_gif(gif_path, stop_event, gif_label, root):
    """
    تعرض هذه الدالة ملف GIF في Label محدد، وتكرّر عرض الإطارات 
    حتى يتم إشعارها بالتوقّف عبر stop_event.
    """
    try:
        gif = Image.open(gif_path)
        frames = [ImageTk.PhotoImage(frame.copy()) for frame in ImageSequence.Iterator(gif)]
        frame_count = len(frames)

        def animate(index):
            if not stop_event.is_set():
                frame = frames[index]
                root.after(0, update_frame, frame)
                # الحصول على مدة الإطار من معلومات الـ GIF (الافتراضي 100 مللي ثانية)
                duration = gif.info.get('duration', 100)
                next_index = (index + 1) % frame_count
                root.after(int(duration), animate, next_index)
            else:
                root.after(0, clear_frame)

        def update_frame(frame):
            gif_label.config(image=frame)
            gif_label.image = frame  # مهم للاحتفاظ بالصورة في الذاكرة

        def clear_frame():
            gif_label.config(image='')
            gif_label.image = None

        animate(0)

    except Exception as e:
        print(f"Error displaying GIF: {e}")

def start_gif_animation(gif_path, gif_label, root):
    """
    بدء تشغيل الرسوم المتحركة (GIF) في خيط (Thread) مستقل.
    """
    global gif_stop_event
    if gif_stop_event:
        gif_stop_event.set()
    gif_stop_event = threading.Event()
    threading.Thread(target=display_gif, args=(gif_path, gif_stop_event, gif_label, root), daemon=True).start()

def stop_gif_animation():
    """
    إيقاف تشغيل الرسوم المتحركة (GIF) بإشارة الـ Event.
    """
    global gif_stop_event
    if gif_stop_event:
        gif_stop_event.set()

###############################################
# تعريف فئة معالج الأحداث لبث الردود من المساعد
###############################################
class ResponseEventHandler(AssistantEventHandler):
    def __init__(self, textbox):
        super().__init__()
        self.textbox = textbox
        self.response = ""  # لتجميع الرد الكامل

    def on_text_created(self, text) -> None:
        # عند بدء الرد، نكتب مؤشر الرد في صندوق العرض
        self.textbox.insert(tk.END, "\nFaris: ", "bold")
        self.textbox.yview(tk.END)

    def on_text_delta(self, delta, snapshot):
        # تحديث الرد تدريجيًا في صندوق العرض
        self.response += delta.value
        self.textbox.insert(tk.END, delta.value)
        self.textbox.yview(tk.END)

###############################################
# دوال تسجيل ومعالجة الصوت
###############################################
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

###############################################
# دالة معالجة الصوت: حفظ التسجيل، النسخ إلى نص،
# استدعاء ChatGPT لتحويل النص إلى رد، التوليد الصوتي والمرئي
###############################################
def process_audio():
    global gif_label, root
    try:
        # بدء عرض الرسوم المتحركة (GIF) أثناء المعالجة
        start_gif_animation("gifs/thinking.gif", gif_label, root)

        status_label.config(text="Saving Audio...")
        audio_data = np.concatenate(audio_frames, axis=0)
        wavio.write(audio_filename, audio_data, fs, sampwidth=2)

        # تحويل الصوت إلى نص باستخدام واجهة Whisper من OpenAI
        status_label.config(text="Transcribing...")
        transcribed_text = transcribe_audio(audio_filename)
        transcribed_textbox.delete(1.0, tk.END)
        transcribed_textbox.insert(tk.END, transcribed_text)
        print("Transcribed Text:", transcribed_text)

        # الحصول على الرد من ChatGPT باستخدام المحادثة المستمرة وبث الرد
        status_label.config(text="Generating Response...")
        response_text = chat_with_gpt(transcribed_text)
        response_textbox.delete(1.0, tk.END)
        response_textbox.insert(tk.END, response_text)
        print("ChatGPT Response:", response_text)

        # تحويل الرد إلى كلام باستخدام ElevenLabs
        status_label.config(text="Converting Text to Speech...")
        text_to_speech(response_text, output_audio_filename)

        # دمج الصوت والفيديو
        status_label.config(text="Merging Audio and Video...")
        merged_video_path = "./media/videos/merged_output.mp4"
        merge_audio_and_video("./media/videos/arabic_text_animation.mp4", output_audio_filename, merged_video_path)

        # إيقاف GIF التفكير وبدء GIF الشرح
        stop_gif_animation()
        start_gif_animation("gifs/explaining.gif", gif_label, root)

        # تشغيل الفيديو المدمج باستخدام VLC في خيط منفصل
        status_label.config(text="Playing Video...")
        threading.Thread(target=play_video_with_vlc, args=(merged_video_path,), daemon=True).start()

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n\n{e}")
    finally:
        status_label.config(text="Ready")

def transcribe_audio(filename):
    try:
        # استخدام واجهة Whisper API لتحويل الصوت إلى نص
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

###############################################
# دالة التفاعل مع ChatGPT باستخدام المحادثة المستمرة وبث الرد
###############################################
def chat_with_gpt(transcribed_text):
    """
    ترسل هذه الدالة نص المستخدم (بعد النسخ) إلى المساعد باستخدام خاصية المحادثة المستمرة.
    إذا لم يكن هناك حوار قائم، يتم إنشاء واحد جديد وتخزين معرفه.
    كما يتم بث الرد بشكل تدريجي إلى صندوق النص.
    """
    global conversation_thread_id
    if not transcribed_text:
        return "لم يتم الحصول على نص من التسجيل."
    try:
        # إنشاء محادثة جديدة إذا لم يكن معرف الحوار موجودًا
        if conversation_thread_id is None:
            thread = openai.beta.threads.create()
            conversation_thread_id = thread.id
            print("تم إنشاء محادثة جديدة بمعرف:", conversation_thread_id)
        else:
            print("إعادة استخدام معرف المحادثة الحالي:", conversation_thread_id)
        thread_id = conversation_thread_id

        # إرسال رسالة المستخدم للمحادثة
        openai.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=transcribed_text,
        )
        print("تم إرسال رسالة المستخدم:", transcribed_text)

        # بث الرد التدريجي من المساعد باستخدام ResponseEventHandler
        event_handler = ResponseEventHandler(response_textbox)
        with openai.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
            event_handler=event_handler
        ) as stream:
            stream.until_done()
        print("رد المساعد النهائي:", event_handler.response)
        return event_handler.response

    except Exception as e:
        print("حدث خطأ في chat_with_gpt:", e)
        return f"Error: {e}"

###############################################
# دالة تحويل النص إلى كلام باستخدام ElevenLabs
###############################################
def text_to_speech(text, output_filename):
    try:
        client = ElevenLabs(api_key="sk_274b05820004e924913b674d3c4181aae2b89df0f66a2806")

        voice_settings = VoiceSettings(
            stability=0.75,        # ثبات الصوت
            similarity_boost=0.6,  # تعزيز التشابه
            style=0.3,             # أسلوب الكلام
            speed=0.1              # سرعة الكلام
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

###############################################
# دوال تشغيل الصوت والفيديو ودمجهما باستخدام ffmpeg وVLC
###############################################
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
            '-y',  # الكتابة فوق الملفات الموجودة دون استفسار
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

        # ضبط مخرج الفيديو للنافذة الخاصة بـ Tkinter
        if os.name == 'nt':  # لنظام Windows
            player.set_hwnd(video_label.winfo_id())
        else:
            player.set_xwindow(video_label.winfo_id())

        # بدء التشغيل
        player.play()

        # الانتظار حتى انتهاء التشغيل
        events = player.event_manager()
        event = threading.Event()

        def end_callback(event_type):
            event.set()

        events.event_attach(vlc.EventType.MediaPlayerEndReached, end_callback)
        event.wait()
        player.stop()

        # بعد انتهاء الفيديو، تغيير GIF إلى صورة ثابتة أو رسوم مختلفة
        stop_gif_animation()
        start_gif_animation("gifs/bw.gif", gif_label, root)

    except Exception as e:
        messagebox.showerror("Error", f"Error playing video:\n\n{e}")

###############################################
# دالة لتبديل حالة التسجيل عند الضغط على زر المسافة
###############################################
def toggle_recording(event):
    global recording
    if not recording:
        start_recording()
    else:
        stop_recording()

###############################################
# واجهة المستخدم الرئيسية باستخدام Tkinter
###############################################
def init_gui():
    global root, status_label, transcribed_textbox, response_textbox, video_label, gif_label
    # إنشاء نافذة رئيسية
    root = tk.Tk()
    root.title("Arabic Speech Assistant")
    # جعل النافذة ملء الشاشة (Full Screen)
    root.attributes("-fullscreen", True)
    # تغيير خلفية النافذة إلى اللون الأسود
    root.configure(bg="black")

    # إنشاء إطار الفيديو (يمكن استخدامه في حال الحاجة إلى عرض فيديو)
    video_frame = tk.Frame(root, width=800, height=400, bg="black")
    video_frame.pack(pady=10)
    video_label = tk.Label(video_frame, bg="black")
    video_label.pack()

    # إنشاء Label لعرض الرسوم المتحركة (GIF) في وسط النافذة
    gif_label = tk.Label(root, bg="black")
    gif_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    # إنشاء صناديق عرض النصوص
    transcribed_label = tk.Label(root, text="Transcribed Text:", font=("Helvetica", 20), bg="black", fg="white")
    transcribed_label.pack(pady=5)
    transcribed_textbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=5,
                                                     font=("Helvetica", 20), bg="#1f1f1f", fg="white")
    transcribed_textbox.pack(pady=5)

    response_label = tk.Label(root, text="Faris Response:", font=("Helvetica", 20), bg="black", fg="white")
    response_label.pack(pady=5)
    response_textbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=10,
                                                  font=("Helvetica", 20), bg="#1f1f1f", fg="white")
    response_textbox.pack(pady=5)

    # تسمية الحالة
    status_label = tk.Label(root, text="Ready", font=("Helvetica", 20), bg="black", fg="white")
    status_label.pack(pady=10)

    # بدء تشغيل GIF ابتدائي (مثلاً صورة bw)
    start_gif_animation("gifs/bw.gif", gif_label, root)

    # ربط زر المسافة لتبديل حالة التسجيل
    root.bind("<space>", toggle_recording)
    # إضافة إمكانية الخروج من وضع ملء الشاشة بالضغط على مفتاح ESC
    def exit_fullscreen(event):
        root.attributes("-fullscreen", False)
        root.destroy()  # إغلاق النافذة
    root.bind("<Escape>", exit_fullscreen)

    root.mainloop()

###############################################
# الدالة الرئيسية
###############################################
def main():
    # تعيين مفتاح API الخاص بـ OpenAI (يمكنك استخدام متغيرات البيئة)
    openai.api_key = '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'
            
    # تهيئة مشغل الصوت (Pygame)
    pygame.mixer.init()

    # بدء واجهة المستخدم
    init_gui()

if __name__ == "__main__":
    main()
