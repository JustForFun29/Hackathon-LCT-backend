from pandas.core.frame import DataFrame
from typing import List
import pandas as pd
import joblib
import os


class Predictor:
    def __init__(self):
        self.models = {}
        dir_ = os.path.join(os.path.dirname(__file__), 'saved_models')
        for folder in os.listdir(dir_):
            for file in os.listdir(f'{dir_}/{folder}'):
                if file == 'forest_model.pkl':
                    self.models[folder] = joblib.load(f'{dir_}/{folder}/{file}').predict

    def predict(self, target: str, data: DataFrame) -> List:
        return list(self.models[target](data))


if __name__ == '__main__':
    predictor = Predictor()

    start = 1
    finish = 52

    example = {
        'Год': [2024 for _ in range(finish - start + 1)],
        'Номер недели': [i for i in range(start, finish + 1)],
    }

    df = pd.read_csv('testing.csv')
    cols = list(df.columns)
    out = {
        'Год': [2024 for _ in range(52)],
        'Номер недели': [i for i in range(1, 53)],
    }

    for i in range(2, 12):
        if cols[i] != 'МРТ с КУ 2 и более зон':
            data = pd.DataFrame(example)
            pred = predictor.predict(target=cols[i], data=data)
            out[cols[i]] = pred

    pd.DataFrame(out).to_csv('predictions.csv', index=False)
