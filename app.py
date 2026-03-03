import os
import re
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, abort, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash

from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from config import Config
from db import init_db, get_conn

app = Flask(__name__)
app.config.from_object(Config)
init_db()

STROKES = ["Freestyle", "Breaststroke", "Backstroke", "Butterfly"]
LEVELS = ["BEGINNER", "ADVANCED"]
ROLES = ["USER", "COACH", "ADMIN"]


# ---------- Helpers ----------
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def role_required(*allowed_roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                flash("Please login first.", "warning")
                return redirect(url_for("login"))
            if session.get("role") not in allowed_roles:
                flash("Access denied.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return deco


def format_ms(ms: int) -> str:
    total_seconds = ms / 1000.0
    m = int(total_seconds // 60)
    s = total_seconds - (m * 60)
    return f"{m:02d}:{s:05.2f}"


def get_user_row(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.*, a.name AS academy_name
        FROM users u
        LEFT JOIN academies a ON a.academy_id = u.academy_id
        WHERE u.user_id = ?
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


@app.get("/")
def index():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))


# ---------- AUTH ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.", "danger")
            return render_template("auth_register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth_register.html")

        if not re.search(r"[^A-Za-z0-9]", password):
            flash("Password must contain at least 1 special character (example: @, #, $, !).", "danger")
            return render_template("auth_register.html")

        if password != confirm_password:
            flash("Password and Confirm Password do not match.", "danger")
            return render_template("auth_register.html")

        # default academy = first academy
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT academy_id FROM academies ORDER BY academy_id ASC LIMIT 1")
        acad = cur.fetchone()
        academy_id = acad["academy_id"] if acad else None

        try:
            cur.execute("""
                INSERT INTO users(name, email, password, role, academy_id, level, medals)
                VALUES (?,?,?,?,?,?,?)
            """, (name, email, generate_password_hash(password), "USER", academy_id, "BEGINNER", 0))
            conn.commit()
        except Exception:
            conn.close()
            flash("Email already exists. Try login.", "danger")
            return render_template("auth_register.html")

        conn.close()
        flash("Account created! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("auth_register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        conn.close()

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "danger")
            return render_template("auth_login.html")

        session["user_id"] = user["user_id"]
        session["user_name"] = user["name"]
        session["role"] = user["role"]
        session["academy_id"] = user["academy_id"]

        flash(f"Welcome, {user['name']}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("auth_login.html")


@app.get("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ---------- DASHBOARD ----------
@app.get("/dashboard")
@login_required
def dashboard():
    u = get_user_row(session["user_id"])
    return render_template("dashboard.html", user=u)


# ---------- PROFILE ----------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    conn = get_conn()
    cur = conn.cursor()

    if request.method == "POST":
        age = request.form.get("age", "").strip()
        height_cm = request.form.get("height_cm", "").strip()
        goal_distance_m = request.form.get("goal_distance_m", "").strip()

        def to_int(v): return int(v) if v != "" else None
        def to_float(v): return float(v) if v != "" else None

        try:
            cur.execute("""
                UPDATE users
                SET age = ?, height_cm = ?, goal_distance_m = ?
                WHERE user_id = ?
            """, (to_int(age), to_float(height_cm), to_float(goal_distance_m), session["user_id"]))
            conn.commit()
            flash("Profile updated ✅", "success")
        except Exception:
            flash("Invalid values.", "danger")

    cur.execute("""
        SELECT u.*, a.name AS academy_name
        FROM users u
        LEFT JOIN academies a ON a.academy_id = u.academy_id
        WHERE u.user_id = ?
    """, (session["user_id"],))
    user = cur.fetchone()
    conn.close()

    return render_template("profile.html", user=user)


# ---------- SWIM TRACKER ----------
@app.route("/swim", methods=["GET", "POST"])
@login_required
def swim():
    if request.method == "POST":
        time_ms = int(request.form.get("time_ms", "0"))
        laps = int(request.form.get("laps", "0"))
        pool_len = float(request.form.get("pool_len", "25"))
        stroke_type = request.form.get("stroke_type", "Freestyle")

        if stroke_type not in STROKES:
            flash("Invalid stroke type.", "danger")
            return redirect(url_for("swim"))

        if time_ms <= 0:
            flash("Time must be greater than 0. Start the stopwatch!", "danger")
            return redirect(url_for("swim"))

        if laps <= 0:
            flash("Laps must be greater than 0.", "danger")
            return redirect(url_for("swim"))

        distance = laps * pool_len
        date_str = datetime.now().strftime("%Y-%m-%d")

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO swim_records(user_id, date, time_ms, laps, distance, pool_len, stroke_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session["user_id"], date_str, time_ms, laps, distance, pool_len, stroke_type))
        conn.commit()
        conn.close()

        flash("Swim record saved ✅", "success")
        return redirect(url_for("progress"))

    return render_template("swim_tracker.html", strokes=STROKES)


# ---------- PROGRESS ----------
@app.get("/progress")
@login_required
def progress():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM swim_records
        WHERE user_id = ?
        ORDER BY record_id DESC
    """, (session["user_id"],))
    records = cur.fetchall()

    cur.execute("SELECT COALESCE(SUM(distance),0) AS total_distance FROM swim_records WHERE user_id = ?",
                (session["user_id"],))
    total_distance = cur.fetchone()["total_distance"]

    cur.execute("SELECT MIN(time_ms) AS best_time_ms FROM swim_records WHERE user_id = ?",
                (session["user_id"],))
    best_time_ms = cur.fetchone()["best_time_ms"]

    cur.execute("SELECT goal_distance_m FROM users WHERE user_id = ?",
                (session["user_id"],))
    goal_distance_m = cur.fetchone()["goal_distance_m"]

    conn.close()

    best_time = format_ms(best_time_ms) if best_time_ms else None

    display_records = [{
        "record_id": r["record_id"],
        "date": r["date"],
        "time": format_ms(r["time_ms"]),
        "laps": r["laps"],
        "pool_len": r["pool_len"],
        "distance": r["distance"],
        "stroke_type": r["stroke_type"]
    } for r in records]

    return render_template(
        "progress.html",
        records=display_records,
        total_distance=total_distance,
        best_time=best_time,
        goal_distance_m=goal_distance_m
    )


@app.get("/api/progress/chart")
@login_required
def progress_chart_api():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT date, distance, time_ms
        FROM swim_records
        WHERE user_id = ?
        ORDER BY record_id DESC
        LIMIT 14
    """, (session["user_id"],))
    rows = list(reversed(cur.fetchall()))
    conn.close()

    return jsonify({
        "labels": [r["date"] for r in rows],
        "distances": [float(r["distance"]) for r in rows],
        "times_sec": [round(r["time_ms"] / 1000.0, 2) for r in rows]
    })


# ---------- EDIT/DELETE RECORD ----------
@app.route("/records/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
def record_edit(record_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM swim_records WHERE record_id=? AND user_id=?",
                (record_id, session["user_id"]))
    rec = cur.fetchone()
    if not rec:
        conn.close()
        abort(404)

    if request.method == "POST":
        date = request.form.get("date", "").strip()
        laps = int(request.form.get("laps", rec["laps"]))
        pool_len = float(request.form.get("pool_len", rec["pool_len"]))
        time_ms = int(request.form.get("time_ms", rec["time_ms"]))
        stroke_type = request.form.get("stroke_type", rec["stroke_type"])

        if not date:
            flash("Date is required.", "danger")
            conn.close()
            return render_template("record_edit.html", rec=rec, time_display=format_ms(rec["time_ms"]), strokes=STROKES)

        if stroke_type not in STROKES or laps <= 0 or pool_len <= 0 or time_ms <= 0:
            flash("Invalid values.", "danger")
            conn.close()
            return render_template("record_edit.html", rec=rec, time_display=format_ms(rec["time_ms"]), strokes=STROKES)

        distance = laps * pool_len
        cur.execute("""
            UPDATE swim_records
            SET date=?, time_ms=?, laps=?, pool_len=?, distance=?, stroke_type=?
            WHERE record_id=? AND user_id=?
        """, (date, time_ms, laps, pool_len, distance, stroke_type, record_id, session["user_id"]))
        conn.commit()
        conn.close()

        flash("Record updated ✅", "success")
        return redirect(url_for("progress"))

    conn.close()
    return render_template("record_edit.html", rec=rec, time_display=format_ms(rec["time_ms"]), strokes=STROKES)


@app.post("/records/<int:record_id>/delete")
@login_required
def record_delete(record_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM swim_records WHERE record_id=? AND user_id=?",
                (record_id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("Record deleted 🗑️", "info")
    return redirect(url_for("progress"))


# ---------- PLAYERS ----------
@app.get("/players")
@login_required
def players():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM players ORDER BY name ASC")
    rows = cur.fetchall()
    conn.close()
    return render_template("players.html", players=rows)


@app.get("/players/<int:player_id>")
@login_required
def player_detail(player_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM players WHERE player_id=?", (player_id,))
    p = cur.fetchone()
    conn.close()

    if not p:
        flash("Player not found.", "danger")
        return redirect(url_for("players"))

    return render_template("player_detail.html", p=p)


# =========================
# ✅ ADMIN MODULE
# =========================
@app.get("/admin/users")
@role_required("ADMIN")
def admin_users():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.user_id, u.name, u.email, u.role, u.level, u.medals,
               a.name AS academy_name, u.academy_id
        FROM users u
        LEFT JOIN academies a ON a.academy_id = u.academy_id
        WHERE u.user_id != ?
        ORDER BY u.user_id DESC
    """, (session["user_id"],))
    users = cur.fetchall()

    cur.execute("SELECT * FROM academies ORDER BY name ASC")
    academies = cur.fetchall()

    conn.close()
    return render_template("admin_users.html", users=users, academies=academies, roles=ROLES, levels=LEVELS)


@app.post("/admin/users/<int:user_id>/update")
@role_required("ADMIN")
def admin_user_update(user_id):
    if user_id == session["user_id"]:
        flash("You cannot modify your own admin account from here.", "danger")
        return redirect(url_for("admin_users"))

    level = request.form.get("level", "BEGINNER")
    medals = request.form.get("medals", "0")
    academy_id = request.form.get("academy_id", "")

    if level not in LEVELS:
        flash("Invalid level.", "danger")
        return redirect(url_for("admin_users"))

    try:
        medals_i = int(medals)
        acad = int(academy_id) if academy_id != "" else None
    except Exception:
        flash("Invalid medals/academy.", "danger")
        return redirect(url_for("admin_users"))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash("User not found.", "danger")
        return redirect(url_for("admin_users"))

    if row["role"] == "ADMIN":
        conn.close()
        flash("You cannot modify an admin account.", "danger")
        return redirect(url_for("admin_users"))

    cur.execute("""
        UPDATE users
        SET level = ?, medals = ?, academy_id = ?
        WHERE user_id = ?
    """, (level, medals_i, acad, user_id))

    conn.commit()
    conn.close()

    flash("User updated ✅ (role locked)", "success")
    return redirect(url_for("admin_users"))


@app.post("/admin/users/add-coach")
@role_required("ADMIN")
def admin_add_coach():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    academy_id = request.form.get("academy_id", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not academy_id or not password or not confirm_password:
        flash("All fields are required to add a coach.", "danger")
        return redirect(url_for("admin_users"))

    if len(password) < 8:
        flash("Coach password must be at least 8 characters.", "danger")
        return redirect(url_for("admin_users"))

    if not re.search(r"[^A-Za-z0-9]", password):
        flash("Coach password must contain at least 1 special character (example: @, #, $, !).", "danger")
        return redirect(url_for("admin_users"))

    if password != confirm_password:
        flash("Coach password and confirm password do not match.", "danger")
        return redirect(url_for("admin_users"))

    try:
        academy_id_int = int(academy_id)
    except Exception:
        flash("Invalid academy selected.", "danger")
        return redirect(url_for("admin_users"))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT academy_id FROM academies WHERE academy_id=?", (academy_id_int,))
    if not cur.fetchone():
        conn.close()
        flash("Selected academy not found.", "danger")
        return redirect(url_for("admin_users"))

    try:
        cur.execute("""
            INSERT INTO users(name, email, password, role, academy_id, level, medals)
            VALUES (?, ?, ?, 'COACH', ?, 'ADVANCED', 0)
        """, (name, email, generate_password_hash(password), academy_id_int))
        conn.commit()
        flash("Coach added successfully ✅", "success")
    except Exception:
        flash("Coach email already exists. Use another email.", "danger")
    finally:
        conn.close()

    return redirect(url_for("admin_users"))


@app.get("/admin/academies")
@role_required("ADMIN")
def admin_academies():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM academies ORDER BY academy_id DESC")
    academies = cur.fetchall()
    conn.close()
    return render_template("admin_academies.html", academies=academies)


@app.post("/admin/academies/add")
@role_required("ADMIN")
def admin_academies_add():
    name = request.form.get("name", "").strip()
    city = request.form.get("city", "").strip()

    if not name:
        flash("Academy name required.", "danger")
        return redirect(url_for("admin_academies"))

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO academies(name, city) VALUES (?,?)", (name, city))
        conn.commit()
        flash("Academy created ✅", "success")
    except Exception:
        flash("Academy already exists.", "danger")
    conn.close()
    return redirect(url_for("admin_academies"))


@app.post("/admin/academies/<int:academy_id>/delete")
@role_required("ADMIN")
def admin_academies_delete(academy_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET academy_id=NULL WHERE academy_id=?", (academy_id,))
    cur.execute("DELETE FROM academies WHERE academy_id=?", (academy_id,))
    conn.commit()
    conn.close()
    flash("Academy deleted.", "info")
    return redirect(url_for("admin_academies"))


@app.get("/admin/reports")
@role_required("ADMIN")
def admin_reports():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM users")
    total_users = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM swim_records")
    total_records = cur.fetchone()["c"]

    cur.execute("SELECT COALESCE(SUM(distance),0) AS s FROM swim_records")
    total_distance = cur.fetchone()["s"]

    cur.execute("""
        SELECT a.name, COUNT(r.record_id) AS swims, COALESCE(SUM(r.distance),0) AS dist
        FROM academies a
        LEFT JOIN users u ON u.academy_id = a.academy_id
        LEFT JOIN swim_records r ON r.user_id = u.user_id
        GROUP BY a.academy_id
        ORDER BY dist DESC
    """)
    by_academy = cur.fetchall()

    conn.close()
    return render_template(
        "admin_reports.html",
        total_users=total_users,
        total_records=total_records,
        total_distance=total_distance,
        by_academy=by_academy
    )


@app.get("/admin/monitoring")
@role_required("ADMIN")
def admin_monitoring():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.user_id, u.name, u.level, u.medals, COALESCE(SUM(r.distance),0) AS total_dist
        FROM users u
        LEFT JOIN swim_records r ON r.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY total_dist DESC
        LIMIT 10
    """)
    top_swimmers = cur.fetchall()

    cur.execute("""
        SELECT stroke_type, COUNT(*) AS c
        FROM swim_records
        GROUP BY stroke_type
        ORDER BY c DESC
    """)
    stroke_stats = cur.fetchall()

    conn.close()
    return render_template("admin_monitoring.html", top_swimmers=top_swimmers, stroke_stats=stroke_stats)


# =========================
# ✅ COACH MODULE
# =========================
@app.get("/coach")
@role_required("COACH", "ADMIN")
def coach_dashboard():
    conn = get_conn()
    cur = conn.cursor()

    if session["role"] == "ADMIN":
        cur.execute("""
            SELECT u.user_id, u.name, u.level, u.medals, a.name AS academy_name
            FROM users u
            LEFT JOIN academies a ON a.academy_id = u.academy_id
            WHERE u.role = 'USER'
            ORDER BY u.user_id DESC
        """)
    else:
        cur.execute("""
            SELECT u.user_id, u.name, u.level, u.medals, a.name AS academy_name
            FROM users u
            LEFT JOIN academies a ON a.academy_id = u.academy_id
            WHERE u.role = 'USER' AND u.academy_id = ?
            ORDER BY u.user_id DESC
        """, (session["academy_id"],))

    swimmers = cur.fetchall()
    conn.close()
    return render_template("coach_dashboard.html", swimmers=swimmers)


@app.get("/coach/ranking")
@role_required("COACH", "ADMIN")
def coach_ranking():
    conn = get_conn()
    cur = conn.cursor()

    params = []
    where = "WHERE u.role = 'USER'"

    if session["role"] != "ADMIN":
        where += " AND u.academy_id = ?"
        params.append(session["academy_id"])

    cur.execute(f"""
        SELECT u.user_id, u.name, u.level, u.medals,
               COALESCE(SUM(r.distance),0) AS total_dist,
               MIN(r.time_ms) AS best_time_ms
        FROM users u
        LEFT JOIN swim_records r ON r.user_id = u.user_id
        {where}
        GROUP BY u.user_id
        ORDER BY total_dist DESC
    """, params)

    rows = cur.fetchall()
    conn.close()

    ranked = []
    for i, r in enumerate(rows, start=1):
        ranked.append({
            "rank": i,
            "user_id": r["user_id"],
            "name": r["name"],
            "level": r["level"],
            "medals": r["medals"],
            "total_dist": float(r["total_dist"]),
            "best_time": format_ms(r["best_time_ms"]) if r["best_time_ms"] else "—"
        })

    return render_template("coach_ranking.html", rows=ranked)


def _pdf_swimmer_report(user_id: int):
    user = get_user_row(user_id)
    if not user:
        return None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) AS swims,
               COALESCE(SUM(distance),0) AS total_dist,
               MIN(time_ms) AS best_time_ms
        FROM swim_records
        WHERE user_id = ?
    """, (user_id,))
    stats = cur.fetchone()

    cur.execute("""
        SELECT date, stroke_type, distance, time_ms
        FROM swim_records
        WHERE user_id = ?
        ORDER BY record_id DESC
        LIMIT 10
    """, (user_id,))
    recent = cur.fetchall()
    conn.close()

    buff = BytesIO()
    c = canvas.Canvas(buff, pagesize=A4)
    w, h = A4

    y = h - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Swimmer Performance Report")
    y -= 24

    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Name: {user['name']}   |   Email: {user['email']}")
    y -= 16
    c.drawString(40, y, f"Academy: {user['academy_name'] or '-'}   |   Level: {user['level']}   |   Medals: {user['medals']}")
    y -= 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Summary")
    y -= 16
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Total Swims: {stats['swims']}")
    y -= 14
    c.drawString(40, y, f"Total Distance: {float(stats['total_dist']):.0f} m")
    y -= 14
    best = format_ms(stats["best_time_ms"]) if stats["best_time_ms"] else "—"
    c.drawString(40, y, f"Best Time: {best}")
    y -= 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Recent 10 Swims")
    y -= 18

    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Date")
    c.drawString(130, y, "Stroke")
    c.drawString(240, y, "Distance")
    c.drawString(330, y, "Time")
    y -= 14
    c.setFont("Helvetica", 10)

    for r in recent:
        if y < 70:
            c.showPage()
            y = h - 60
        c.drawString(40, y, r["date"])
        c.drawString(130, y, r["stroke_type"])
        c.drawString(240, y, f"{float(r['distance']):.0f} m")
        c.drawString(330, y, format_ms(r["time_ms"]))
        y -= 13

    c.showPage()
    c.save()
    buff.seek(0)
    return buff


@app.get("/coach/report/pdf/<int:user_id>")
@role_required("COACH", "ADMIN")
def coach_export_pdf(user_id):
    target = get_user_row(user_id)
    if not target:
        flash("User not found.", "danger")
        return redirect(url_for("coach_dashboard"))

    if target["role"] != "USER":
        flash("PDF report allowed only for swimmers (USER).", "danger")
        return redirect(url_for("coach_dashboard"))

    if session["role"] != "ADMIN":
        if target["academy_id"] != session.get("academy_id"):
            flash("Access denied to that swimmer.", "danger")
            return redirect(url_for("coach_dashboard"))

    pdf = _pdf_swimmer_report(user_id)
    if not pdf:
        flash("User not found.", "danger")
        return redirect(url_for("coach_dashboard"))

    return send_file(
        pdf,
        as_attachment=True,
        download_name=f"swimmer_report_{user_id}.pdf",
        mimetype="application/pdf"
    )


@app.route("/coach/compare", methods=["GET", "POST"])
@role_required("COACH", "ADMIN")
def compare():
    conn = get_conn()
    cur = conn.cursor()

    if session["role"] == "ADMIN":
        cur.execute("SELECT user_id, name FROM users WHERE role='USER' ORDER BY name ASC")
        swimmers = cur.fetchall()
    else:
        cur.execute("""
            SELECT user_id, name
            FROM users
            WHERE role='USER' AND academy_id=?
            ORDER BY name ASC
        """, (session["academy_id"],))
        swimmers = cur.fetchall()

    compare_data = None

    if request.method == "POST":
        a = int(request.form.get("user_a"))
        b = int(request.form.get("user_b"))

        def stats(uid):
            cur.execute("""
                SELECT u.user_id, u.name, u.level, u.medals,
                       COUNT(r.record_id) AS swims,
                       COALESCE(SUM(r.distance),0) AS total_dist,
                       MIN(r.time_ms) AS best_time_ms,
                       AVG(r.time_ms) AS avg_time_ms
                FROM users u
                LEFT JOIN swim_records r ON r.user_id = u.user_id
                WHERE u.user_id = ? AND u.role='USER'
                GROUP BY u.user_id
            """, (uid,))
            s = cur.fetchone()
            if not s:
                return None
            return {
                "user_id": s["user_id"],
                "name": s["name"],
                "level": s["level"],
                "medals": s["medals"],
                "swims": s["swims"],
                "total_dist": float(s["total_dist"]),
                "best_time": format_ms(s["best_time_ms"]) if s["best_time_ms"] else "—",
                "avg_time": format_ms(int(s["avg_time_ms"])) if s["avg_time_ms"] else "—",
            }

        sa = stats(a)
        sb = stats(b)
        if sa and sb:
            compare_data = {"a": sa, "b": sb}
        else:
            flash("Invalid swimmers selected.", "danger")

    conn.close()
    return render_template("compare.html", swimmers=swimmers, compare_data=compare_data)


if __name__ == "__main__":
    # ✅ Coolify/production ready: binds to 0.0.0.0 and reads PORT from environment
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 4000)),
        debug=False
    )