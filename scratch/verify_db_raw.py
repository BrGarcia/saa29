import sqlite3
import os

db_path = "var/db"

def check():
    if not os.path.exists(db_path):
        print(f"Erro: {db_path} não existe.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("--- Tipos de Inspeção ---")
    try:
        cursor.execute("SELECT codigo, nome FROM tipos_inspecao")
        for row in cursor.fetchall():
            print(f" - {row[0]}: {row[1]}")
    except Exception as e:
        print(f"Erro ao ler tipos: {e}")

    print("\n--- Inspeções Abertas (Contagem) ---")
    try:
        cursor.execute("SELECT COUNT(*) FROM inspecoes")
        count = cursor.fetchone()[0]
        print(f"Total: {count}")
    except Exception as e:
        print(f"Erro ao ler inspeções: {e}")

    conn.close()

if __name__ == "__main__":
    check()
