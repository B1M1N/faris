# -*- coding: utf-8 -*-

import os
from elevenlabs import ElevenLabs
from tkinter import messagebox

def text_to_speech(text, output_filename):
    try:
        # أنشئ عميل ElevenLabs
        client = ElevenLabs(api_key="sk_274b05820004e924913b674d3c4181aae2b89df0f66a2806")

        # استدعاء TTS وتخزين النتيجة في ملف
        with open(output_filename, "wb") as file:
            audio_stream = client.text_to_speech.convert_as_stream(
                voice_id="egFWq5W0j5U7Q3RFFA8g",
                text=text,
                model_id="eleven_multilingual_v1"
                # جرّب إن احتجت تمرير model_id إذا كان صوتك يدعم العربية:
                # model_id="eleven_multilingual_v1"
            )
            for chunk in audio_stream:
                file.write(chunk)

        # تحقق من إنشاء الملف
        if os.path.exists(output_filename):
            print(f"Audio file saved successfully as {output_filename}")
        else:
            raise Exception("Failed to save audio file.")

    except Exception as e:
        messagebox.showerror("Error", f"Text-to-Speech conversion failed: {e}")


if __name__ == "__main__":
    # جرّب نصًا عربيًا للتأكد
    arabic_text = "مرحباً بالعالم، هذا اختبار لتحويل النص العربي إلى صوت"
    output_file = "arabic_test.wav"
    text_to_speech(arabic_text, output_file)
