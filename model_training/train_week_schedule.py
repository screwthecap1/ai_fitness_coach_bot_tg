import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from joblib import dump

df = pd.read_csv("dataset_schedule.csv")

# Нормализуем цели
df["goal"] = df["goal"].astype(str).str.strip().str.capitalize()

# Проверка — обязательно!
print("🎯 Уникальные цели перед обучением:", df["goal"].unique())

# Возможные тренировки по локациям
valid_activities = {
    "Зал": [
        "Жим", "Тяга", "Присед", "Шраги", "Функционалка", "Плавание", "Йога", "Растяжка", "Кардио", "Бег", "Гиперэкстензия"
    ],
    "Дом": [
        "Отжимания", "Приседания", "Берпи", "Планка", "Йога", "Растяжка", "Кардио", "Функционалка"
    ],
    "Улица": [
        "Бег", "Вело", "Скандинавская", "Прыжки", "Кардио", "Прогулка", "Отжимания на турнике"
    ]
}


def is_valid(row, activity):
    location = row["location"]
    valid = valid_activities.get(location, [])
    return any(part in activity for part in valid)

# Только одна фильтрация!
days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
mask = df.apply(lambda row: all(is_valid(row, row[day]) for day in days), axis=1)
df = df[mask]

# Кодируем признаки
le_gender = LabelEncoder()
le_goal = LabelEncoder()
le_level = LabelEncoder()
le_location = LabelEncoder()

df["gender_enc"] = le_gender.fit_transform(df["gender"])
df["goal_enc"] = le_goal.fit_transform(df["goal"])
df["level_enc"] = le_level.fit_transform(df["level"])
df["location_enc"] = le_location.fit_transform(df["location"])

# Проверка — выводим классы
print("✅ Классы целей в энкодере:", le_goal.classes_)

X = df[["age", "weight", "height", "gender_enc", "goal_enc", "level_enc", "steps", "location_enc"]]
models = {}
for day in days:
    y = df[day]
    y_le = LabelEncoder()
    y_enc = y_le.fit_transform(y)
    model = RandomForestClassifier()
    model.fit(X, y_enc)
    models[day] = (model, y_le)

dump(models, "model.pkl")
dump((le_gender, le_goal, le_level, le_location), "encoders.pkl")
print("✅ Модель обучена и сохранена.")
