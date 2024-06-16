from transformers import MarianMTModel, MarianTokenizer


class Translator:
    def __init__(self, model_name: str = 'Helsinki-NLP/opus-mt-ru-en'):
        self.__tokenizer = MarianTokenizer.from_pretrained(model_name)
        self.__model = MarianMTModel.from_pretrained(model_name)

    def translate(self, text: str) -> str:
        inputs = self.__tokenizer(text, return_tensors="pt", padding=True)
        translated = self.__model.generate(**inputs)
        translated_text = self.__tokenizer.decode(translated[0], skip_special_tokens=True)
        return translated_text
