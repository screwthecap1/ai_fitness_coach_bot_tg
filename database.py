import sqlite3

def create_table():
    # TODO: Повторение conn -> cursor -> commit в каждой функции
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            age INTEGER,
            gender TEXT,
            weight INTEGER,
            height INTEGER,
            goal TEXT,
            level TEXT,
            location TEXT,
            steps INTEGER,
            last_plan TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_user(user_id, data):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, age, gender, weight, height, goal, level, location, steps)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        data.get("age"),
        data.get("gender"),
        data.get("weight"),
        data.get("height"),
        data.get("goal"),
        data.get("level"),
        data.get("location"),
        # TODO: Значение 6000 стоит вынести в константу
        data.get("steps", 6000)
    ))
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def delete_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def update_steps(user_id, steps):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        cursor.execute("UPDATE users SET steps = ? WHERE user_id = ?", (steps, user_id))
    else:
        cursor.execute("INSERT INTO users (user_id, steps) VALUES (?, ?)", (user_id, steps))
    conn.commit()
    conn.close()


def update_plan(user_id, plan_text):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_plan = ? WHERE user_id = ?", (plan_text, user_id))
    conn.commit()
    conn.close()
