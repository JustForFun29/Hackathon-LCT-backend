import pandas as pd
from app import create_app, db
from app.models import StudyCount
import uuid

app = create_app()

# Load the Excel file
file_path = 'исследования.xlsx'
df = pd.read_excel(file_path)

# Mapping of original study type names to the desired names
study_type_mapping = {
    'Денситометр': 'Денситометрия',
    'КТ': 'КТ',
    'КТ с КУ 1 зона': 'КТ с КУ 1 зона',
    'КТ с КУ 2 и более зон': 'КТ с КУ 2 и более зон',
    'ММГ': 'ММГ',
    'МРТ': 'МРТ',
    'МРТ с КУ 1 зона': 'МРТ с КУ 1 зона',
    'МРТ с КУ 2 и более зон': 'МРТ с КУ 2 и более зон',
    'РГ': 'РГ',
    'Флюорограф': 'ФЛГ'
}

# Create the study_count entries
with app.app_context():
    for _, row in df.iterrows():
        for original_study_type, desired_study_type in study_type_mapping.items():
            if pd.notna(row[original_study_type]):
                new_study_count = StudyCount(
                    id=uuid.uuid4(),
                    year=int(row['Год']),
                    week_number=int(row['Номер недели']),
                    study_type=desired_study_type,
                    study_count=row[original_study_type]
                )
                db.session.add(new_study_count)
    db.session.commit()

print("Импорт данных завершен успешно.")
