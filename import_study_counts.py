import pandas as pd
from app import create_app, db
from app.models import StudyCount
import uuid

app = create_app()

# Load the Excel file
file_path = 'исследования.xlsx'
df = pd.read_excel(file_path)

# Rename columns for consistency
df = df.rename(columns={
    'Год': 'year',
    'Номер недели': 'week_number',
    'Денситометр': 'densitometry',
    'КТ': 'ct',
    'КТ с КУ 1 зона': 'ct_with_cu_1_zone',
    'КТ с КУ 2 и более зон': 'ct_with_cu_2_or_more_zones',
    'ММГ': 'mmg',
    'МРТ': 'mrt',
    'МРТ с КУ 1 зона': 'mrt_with_cu_1_zone',
    'МРТ с КУ 2 и более зон': 'mrt_with_cu_2_or_more_zones',
    'РГ': 'rg',
    'Флюорограф': 'fluorography'
})

study_types = [
    'densitometry', 'ct', 'ct_with_cu_1_zone', 'ct_with_cu_2_or_more_zones',
    'mmg', 'mrt', 'mrt_with_cu_1_zone', 'mrt_with_cu_2_or_more_zones',
    'rg', 'fluorography'
]

# Create the study_count entries
with app.app_context():
    for _, row in df.iterrows():
        for study_type in study_types:
            if pd.notna(row[study_type]):
                new_study_count = StudyCount(
                    id=uuid.uuid4(),
                    year=int(row['year']),
                    week_number=int(row['week_number']),
                    study_type=study_type,
                    study_count=row[study_type]
                )
                db.session.add(new_study_count)
    db.session.commit()
