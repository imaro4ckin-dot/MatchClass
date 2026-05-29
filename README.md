# StudyMatch

A Flask web app where students can find study partners, create study groups, schedule meetings, and chat — all organised around shared courses.

---

## Features

| Feature | Details |
|---|---|
| Authentication | Register, login, logout with hashed passwords. Sessions expire after 2 hours. |
| Profile editing | Update your major, course, availability, or password at any time. |
| Student matching | Dashboard shows all students enrolled in the same course as you. |
| Study groups | Create public (open join) or private (request-only) groups per course. |
| Group search | Search groups across any course, not just your own. |
| Meetings | Schedule meetings with a date/time picker; RSVP yes or no; delete when done. |
| Real-time chat | Per-group message board that updates every 2 seconds without page reloads. |
| Group management | Creator can remove members, approve/deny join requests, or delete the group. |

---

## Project Structure

```
MatchClass/
├── app.py                  # All routes, models, and app config
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── .gitignore
└── templates/
    ├── layout.html         # Base template with nav bar and flash messages
    ├── login.html
    ├── register.html
    ├── dashboard.html      # Student matches + groups for your course
    ├── profile.html        # Edit profile
    ├── search.html         # Search groups by course
    ├── create_group.html
    └── group_detail.html   # Meetings, RSVP, live chat, member list
```

---

## Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd MatchClass
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set a strong `SECRET_KEY`:

```
SECRET_KEY=replace-this-with-a-long-random-string
DATABASE_URL=sqlite:///studyapp.db
```

Generate a secure key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Run

```bash
flask run
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## Database

The app uses **SQLite** via SQLAlchemy. The database file is created automatically at `instance/studyapp.db` on first run — no setup required.

If you change the schema (add/remove model columns), delete `instance/studyapp.db` and restart the server to recreate it. Note: this wipes all data.

### Models at a glance

| Model | Purpose |
|---|---|
| `User` | Student account (username, hashed password, major, course, availability) |
| `StudyGroup` | A group tied to a course; public or private |
| `Meeting` | A scheduled session within a group |
| `RSVP` | A user's yes/no response to a meeting |
| `Message` | A chat message posted in a group |
| `JoinRequest` | A pending/approved/denied request to join a private group |

---

## Tech Stack

- **Backend:** Python 3, Flask 3, Flask-SQLAlchemy
- **Database:** SQLite (easily swappable for PostgreSQL via `DATABASE_URL`)
- **Templates:** Jinja2
- **CSS:** [Milligram](https://milligram.io/) (CDN, no build step)
- **Real-time chat:** Vanilla JS polling (`fetch` every 2 s against a JSON endpoint)

---

## Known Limitations

- **No production WSGI server** — `flask run` uses the development server. For deployment use Gunicorn: `gunicorn app:app`
- **SQLite** is fine for local use but not suitable for concurrent production traffic. Switch to PostgreSQL by changing `DATABASE_URL`.
- **No CSRF protection** — forms are not protected against cross-site request forgery. Add [Flask-WTF](https://flask-wtf.readthedocs.io/) before exposing this publicly.
- **Real-time chat via polling** — works well for small groups; for high traffic a WebSocket solution (e.g. Flask-SocketIO) would be more efficient.
