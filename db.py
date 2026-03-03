import sqlite3
from werkzeug.security import generate_password_hash
from config import Config


# ─── Connection ───────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Schema Helpers ───────────────────────────────────────────────────────────

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


# ─── DB Initialization ────────────────────────────────────────────────────────

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Academies
    cur.execute("""
        CREATE TABLE IF NOT EXISTS academies (
            academy_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            city        TEXT
        )
    """)

    # Users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            email     TEXT NOT NULL UNIQUE,
            password  TEXT NOT NULL
        )
    """)

    # Migrate users table — add missing columns
    cols = _cols(conn, "users")
    migrations = [
        ("role",             "role TEXT NOT NULL DEFAULT 'USER'"),       # USER / COACH / ADMIN
        ("academy_id",       "academy_id INTEGER"),                       # NULL allowed
        ("age",              "age INTEGER"),
        ("height_cm",        "height_cm REAL"),
        ("goal_distance_m",  "goal_distance_m REAL"),
        ("level",            "level TEXT NOT NULL DEFAULT 'BEGINNER'"),   # BEGINNER / ADVANCED
        ("medals",           "medals INTEGER NOT NULL DEFAULT 0"),
    ]
    for col_name, col_def in migrations:
        if col_name not in cols:
            _add_column(conn, "users", col_def)

    # Swim Records
    cur.execute("""
        CREATE TABLE IF NOT EXISTS swim_records (
            record_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            date        TEXT NOT NULL,
            time_ms     INTEGER NOT NULL,
            laps        INTEGER NOT NULL,
            distance    REAL NOT NULL,
            pool_len    REAL NOT NULL DEFAULT 25,
            stroke_type TEXT NOT NULL DEFAULT 'Freestyle',
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Famous Players
    cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            age           INTEGER NOT NULL,
            main_stroke   TEXT NOT NULL,
            medals        TEXT NOT NULL,
            best_time     TEXT NOT NULL,
            world_records TEXT NOT NULL,
            photo_url     TEXT NOT NULL,
            federation    TEXT NOT NULL,
            event         TEXT NOT NULL
        )
    """)

    conn.commit()

    # Seed reference data
    seed_default_academy(conn)
    seed_players(conn)
    seed_first_admin(conn)

    conn.close()


# ─── Seed Functions ───────────────────────────────────────────────────────────

def seed_default_academy(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM academies")
    if cur.fetchone()["c"] == 0:
        cur.execute("INSERT INTO academies (name, city) VALUES (?, ?)", ("Main Academy", ""))
        conn.commit()


def seed_first_admin(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'ADMIN'")
    if cur.fetchone()["c"] == 0:
        cur.execute("""
            INSERT INTO users (name, email, password, role, level, medals)
            VALUES (?, ?, ?, 'ADMIN', 'ADVANCED', 0)
        """, (
            "Super Admin",
            "admin@swim.com",
            generate_password_hash("Admin@123"),
        ))
        conn.commit()


def seed_players(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM players")
    if cur.fetchone()["c"] > 0:
        return

    players = [
        (
            "Michael Phelps", 38, "Butterfly / IM",
            "28 Olympic medals (23 Gold)", "100m Butterfly: 49.82",
            "Former multiple WR holder",
            "https://upload.wikimedia.org/wikipedia/commons/5/57/Michael_Phelps_Rio_Olympics_2016.jpg",
            "World Aquatics", "Summer Olympics",
        ),
        (
            "Katie Ledecky", 27, "Freestyle (Distance)",
            "10 Olympic medals (7 Gold)", "1500m Free: 15:20.48",
            "Multiple WR holder (distance free)",
            "https://upload.wikimedia.org/wikipedia/commons/5/51/Katie_Ledecky_2016.jpg",
            "World Aquatics", "Summer Olympics",
        ),
        (
            "Caeleb Dressel", 27, "Sprint Freestyle / Butterfly",
            "8 Olympic medals (7 Gold)", "100m Free: 46.96",
            "Multiple world champion + WRs",
            "https://upload.wikimedia.org/wikipedia/commons/5/59/Caeleb_Dressel_2017.jpg",
            "World Aquatics", "Summer Olympics",
        ),
        (
            "Adam Peaty", 29, "Breaststroke",
            "6 Olympic medals (3 Gold)", "100m Breast: 56.88",
            "World record holder (100m Breast)",
            "https://upload.wikimedia.org/wikipedia/commons/0/0b/Adam_Peaty_2016.jpg",
            "World Aquatics", "Summer Olympics",
        ),
    ]

    cur.executemany("""
        INSERT INTO players
            (name, age, main_stroke, medals, best_time, world_records, photo_url, federation, event)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, players)
    conn.commit()