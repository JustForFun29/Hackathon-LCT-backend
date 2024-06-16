from app.nn.translator import Translator
import tensorflow_hub as hub
from app.nn.stt import stt
import numpy as np
import h5py

'''
tensorflow_hub
h5py
speech_recognition
sentencepiece
torch
pyaudio
sacremoses


sudo apt-get install python-pyaudio python3-pyaudio
'''


class VoiceController:
    def __init__(
            self,
            use_url: str = 'https://tfhub.dev/google/universal-sentence-encoder/4',
            embeddings_path: str = 'app/nn/embeddings/doctor_embeddings.h5',
            threshold: float = 0.7
    ):
        self.__translator = Translator()
        self.__use_url = use_url
        self.__threshold = threshold
        self.__embed = hub.load("https://tfhub.dev/google/universal-sentence-encoder/4")

        with h5py.File(embeddings_path, 'r') as f:
            self.__embeddings = np.array(f['embeddings'])
            self.__texts = np.array(f['texts'], dtype='S')
            self.__labels = np.array(f['labels'], dtype='S')

        self.__texts = [text.decode('utf-8') for text in self.__texts]
        self.__labels = [label.decode('utf-8') for label in self.__labels]

    def execute(self) -> str:
        target_text = self.__translator.translate(stt())
        print(target_text)

        target_embedding = self.__embed([target_text])

        cosine_similarities = np.dot(self.__embeddings, target_embedding[0]) / (
                np.linalg.norm(self.__embeddings, axis=1) * np.linalg.norm(target_embedding)
        )

        similar_indices = np.where(cosine_similarities >= self.__threshold)[0]

        if similar_indices.size > 0:
            for idx in similar_indices:
                return self.__labels[idx]

        return 'NO FUNCTION'


if __name__ == '__main__':
    vc = VoiceController()
    print(vc.execute())
    print(vc.execute())
