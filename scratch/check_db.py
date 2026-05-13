import asyncio
from app.bootstrap.config import get_settings
import os

async def check():
    settings = get_settings()
    print(f"DATABASE_URL: {settings.database_url}")
    print(f"CWD: {os.getcwd()}")
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    print(f"DB Absolute Path: {os.path.abspath(db_path)}")
    if os.path.exists(db_path):
        print("DB file exists.")
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables found via sqlite3: {tables}")
        conn.close()
    else:
        print("DB file does NOT exist.")

if __name__ == "__main__":
    asyncio.run(check())
