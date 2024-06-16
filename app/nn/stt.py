import speech_recognition as sr


def stt() -> str:
    recognizer = sr.Recognizer()

    with sr.Microphone() as mic:
        recognizer.adjust_for_ambient_noise(source=mic, duration=1)
        print("Дергаем API")
        print("ГОЛОС: Слушаю")
        audio = recognizer.listen(source=mic, timeout=20, phrase_time_limit=20)
        query = recognizer.recognize_google(audio_data=audio, language="ru-RU").lower()
        return query
