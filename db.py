import sqlite3
from config import Config

def get_conn():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _cols(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [r["name"] for r in cur.fetchall()]

def _has_table(conn, table):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None

def _add_column(conn, table, col_def_sql):
    cur = conn.cursor()
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def_sql}")
    conn.commit()

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Academies
    cur.execute("""
    CREATE TABLE IF NOT EXISTS academies (
        academy_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        city TEXT
    )
    """)

    # Users (roles + academy + profile + medals + level)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    )
    """)

    # migrate users table
    cols = _cols(conn, "users")
    if "role" not in cols:
        _add_column(conn, "users", "role TEXT NOT NULL DEFAULT 'USER'")  # USER / COACH / ADMIN
    if "academy_id" not in cols:
        _add_column(conn, "users", "academy_id INTEGER")  # NULL allowed
    if "age" not in cols:
        _add_column(conn, "users", "age INTEGER")
    if "height_cm" not in cols:
        _add_column(conn, "users", "height_cm REAL")
    if "goal_distance_m" not in cols:
        _add_column(conn, "users", "goal_distance_m REAL")
    if "level" not in cols:
        _add_column(conn, "users", "level TEXT NOT NULL DEFAULT 'BEGINNER'")  # BEGINNER / ADVANCED
    if "medals" not in cols:
        _add_column(conn, "users", "medals INTEGER NOT NULL DEFAULT 0")

    # Swim Records (add stroke_type + pool_len)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS swim_records (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time_ms INTEGER NOT NULL,
        laps INTEGER NOT NULL,
        distance REAL NOT NULL,
        pool_len REAL NOT NULL DEFAULT 25,
        stroke_type TEXT NOT NULL DEFAULT 'Freestyle',
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)

    # Players (famous profiles)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS players (
        player_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        main_stroke TEXT NOT NULL,
        medals TEXT NOT NULL,
        best_time TEXT NOT NULL,
        world_records TEXT NOT NULL,
        photo_url TEXT NOT NULL,
        federation TEXT NOT NULL,
        event TEXT NOT NULL
    )
    """)

    conn.commit()
    seed_default_academy(conn)
    seed_players(conn)
    seed_first_admin(conn)
    conn.close()

def seed_default_academy(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM academies")
    if cur.fetchone()["c"] == 0:
        cur.execute("INSERT INTO academies(name, city) VALUES (?,?)", ("Main Academy", ""))
        conn.commit()

def seed_first_admin(conn):
    # If no admin exists, we keep it empty (you can create admin by SQL or update user role)
    # Optional: set first registered user to ADMIN manually.
    pass

def seed_players(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM players")
    if cur.fetchone()["c"] > 0:
        return

    players = [
        ("Michael Phelps", 38, "Butterfly / IM", "28 Olympic medals (23 Gold)", "100m Butterfly: 49.82",
         "Former multiple WR holder", "https://upload.wikimedia.org/wikipedia/commons/5/57/Michael_Phelps_Rio_Olympics_2016.jpg",
         "World Aquatics", "Summer Olympics"),
        ("Katie Ledecky", 27, "Freestyle (Distance)", "10 Olympic medals (7 Gold)", "1500m Free: 15:20.48",
         "Multiple WR holder (distance free)", "https://upload.wikimedia.org/wikipedia/commons/5/51/Katie_Ledecky_2016.jpg",
         "World Aquatics", "Summer Olympics"),
        ("Caeleb Dressel", 27, "Sprint Freestyle / Butterfly", "8 Olympic medals (7 Gold)", "100m Free: 46.96",
         "Multiple world champion + WRs", "https://upload.wikimedia.org/wikipedia/commons/5/59/Caeleb_Dressel_2017.jpg",
         "World Aquatics", "Summer Olympics"),
        ("Adam Peaty", 29, "Breaststroke", "6 Olympic medals (3 Gold)", "100m Breast: 56.88",
         "World record holder (100m Breast)", "https://upload.wikimedia.org/wikipedia/commons/0/0b/Adam_Peaty_2016.jpg",
         "World Aquatics", "Summer Olympics"),
    ]

    cur.executemany("""
    INSERT INTO players (name, age, main_stroke, medals, best_time, world_records, photo_url, federation, event)
    VALUES (?,?,?,?,?,?,?,?,?)
    """, players)
    conn.commit()