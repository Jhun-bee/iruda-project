import sqlite3

conn = sqlite3.connect('database/iruda.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
print('Tables:', [row[0] for row in cursor.fetchall()])
conn.close()