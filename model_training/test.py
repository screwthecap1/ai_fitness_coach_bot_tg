import pandas as pd

df = pd.read_csv("dataset_schedulee.csv")

# Нормализация
df["goal"] = df["goal"].astype(str).str.strip().str.capitalize()

# Вывод уникальных целей
print("🎯 Уникальные цели:", df["goal"].unique())

# Подсчёт каждой цели
print("\n📊 Сколько раз встречается каждая цель:")
print(df["goal"].value_counts())
