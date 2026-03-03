# 🏊 Swim Tracker

A Flask-based swim performance tracking web app with role-based access for swimmers, coaches, and admins.

---

## Features

**Swimmers (USER)**
- Log swim sessions with stopwatch, laps, pool length, and stroke type
- View progress charts and personal records
- Edit or delete past records
- Set distance goals and track completion
- Browse famous swimmer profiles

**Coaches (COACH)**
- View and manage swimmers in their academy
- Ranking leaderboard by total distance and best time
- Compare two swimmers side by side
- Export swimmer performance reports as PDF

**Admins (ADMIN)**
- Manage all users and assign levels/medals
- Add coaches to academies
- Create and delete academies
- View platform-wide reports and top swimmer monitoring

---

## Tech Stack

- **Backend:** Python 3, Flask
- **Database:** SQLite (auto-created on first run)
- **PDF Generation:** ReportLab
- **Frontend:** HTML, CSS, Jinja2 templates, Chart.js

---

## Getting Started

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/swim_tracker.git
cd swim_tracker
```

### 2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the app
```bash
python3 app.py
```

Visit `http://127.0.0.1:5000` in your browser.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev_secret_change_me` | Flask session secret — change in production |
| `DB_PATH` | `swim_tracker.db` | Path to SQLite database file |
| `PORT` | `5000` | Port the app runs on |

---

## Project Structure

```
swim_tracker/
├── app.py               # Main Flask application & all routes
├── db.py                # Database init, migrations, seed data
├── config.py            # App configuration
├── requirements.txt     # Python dependencies
├── Procfile             # For deployment (Coolify/Heroku)
├── static/
│   ├── css/style.css
│   ├── js/
│   │   ├── stopwatch.js
│   │   └── progress_chart.js
│   └── img/
│       ├── bg.jpg
│       └── players/
└── templates/           # Jinja2 HTML templates
    ├── base.html
    ├── dashboard.html
    ├── auth_login.html
    ├── auth_register.html
    ├── swim_tracker.html
    ├── progress.html
    ├── profile.html
    ├── players.html
    ├── player_detail.html
    ├── record_edit.html
    ├── coach_dashboard.html
    ├── coach_ranking.html
    ├── compare.html
    ├── admin_users.html
    ├── admin_academies.html
    ├── admin_reports.html
    └── admin_monitoring.html
```

---

## Roles

| Role | Access |
|------|--------|
| `USER` | Personal dashboard, swim logging, progress, player profiles |
| `COACH` | All USER access + swimmer management, rankings, PDF export |
| `ADMIN` | All COACH access + user management, academies, reports |

> To create the first ADMIN, register a normal account then update the role directly in the database:
> ```sql
> UPDATE users SET role = 'ADMIN' WHERE email = 'your@email.com';
> ```

---

## Deployment (Coolify)

1. Push this repo to GitHub
2. In Coolify: **New Resource → Git Repository**
3. Set start command: `python3 app.py`
4. Set environment variables: `SECRET_KEY`, `PORT`
5. Deploy 🚀

---

## License

MIT