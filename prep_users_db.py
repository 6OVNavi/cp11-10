import sqlite3
import hashlib

# Подключение к базе данных
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Создаем таблицу пользователей
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    userID INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    access_level INTEGER DEFAULT 0,
    region TEXT NOT NULL,
    department TEXT NOT NULL,
    position TEXT NOT NULL,
    accessed_docs TEXT DEFAULT ""
)''')


# cursor.execute('''INSERT INTO users (email, password, access_level)
#                           VALUES (?, ?, ?)''', ('test', '12345', 2))

conn.commit()
conn.close()
