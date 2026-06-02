# StudyMatch

A Flask web app where students can find study partners, create study groups, schedule meetings, and chat — all organised around shared courses.

---

## Features

| Feature | Details |
|---|---|
| Authentication | Register, login, logout with hashed passwords. Sessions expire after 2 hours. |
| Profile editing | Update your major, course, availability, or password at any time. |
| Student matching | Dashboard shows all students enrolled in the same course as you. |
| User profiles | Every username is a clickable link to a public profile page showing major, course, availability, and shared groups. |
| Study groups | Create public (open join) or private (request-only) groups per course. Optional description and member limit. |
| Edit group | Group creator can update name, description, contact info, member limit, and public/private toggle at any time. |
| Transfer ownership | Group creator can hand ownership to any current member. |
| Group search | Search groups across any course, not just your own. |
| Member limit | Set a max member cap on a group. Full badge shown and join button disabled when capacity is reached. |
| Meetings | Schedule meetings with a date/time picker and optional location or video link; RSVP yes or no; delete when done. |
| Real-time chat | Per-group message board that updates every 2 seconds without page reloads. |
| Message reactions | React to any chat message with 👍 ❤️ 😂 — counts update instantly without a page reload. |
| Group management | Creator can remove members, approve/deny join requests, or delete the group. |
| Notifications | Bell badge in the nav bar alerts you when a join request is approved/denied or a new meeting is scheduled in your group. |

---

## Project Structure

```
MatchClass/
├── app.py                  # All routes, models, and app config
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── .gitignore
└── templates/
    ├── layout.html         # Base template with nav bar, flash messages, notification badge
    ├── login.html
    ├── register.html
    ├── dashboard.html      # Student matches + groups for your course
    ├── profile.html        # Edit your own profile settings
    ├── user_profile.html   # Public profile page for any user
    ├── search.html         # Search groups by course
    ├── create_group.html
    ├── edit_group.html     # Edit group details (creator only)
    ├── notifications.html  # Notification inbox
    └── group_detail.html   # Meetings, RSVP, live chat, reactions, member list
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

If you change the schema (add/remove model columns), you can either delete `instance/studyapp.db` and restart (wipes all data), or use `sqlite3` to run `ALTER TABLE` statements to add columns without data loss.

### Models at a glance

| Model | Purpose |
|---|---|
| `User` | Student account (username, hashed password, major, course, availability) |
| `StudyGroup` | A group tied to a course; public or private; optional description and member limit |
| `Meeting` | A scheduled session within a group; optional location or link |
| `RSVP` | A user's yes/no response to a meeting |
| `Message` | A chat message posted in a group |
| `Reaction` | An emoji reaction (👍 ❤️ 😂) on a chat message |
| `JoinRequest` | A pending/approved/denied request to join a private group |
| `Notification` | An unread alert for a user (join request outcome, new meeting) |

---

## Tech Stack

- **Backend:** Python 3, Flask 3, Flask-SQLAlchemy
- **Database:** SQLite (easily swappable for PostgreSQL via `DATABASE_URL`)
- **Templates:** Jinja2
- **CSS:** [Milligram](https://milligram.io/) (CDN, no build step)
- **Real-time chat:** Vanilla JS polling (`fetch` every 2 s against a JSON endpoint)
- **Reactions:** Vanilla JS `fetch` POST with live count updates

---

## Known Limitations

- **No production WSGI server** — `flask run` uses the development server. For deployment use Gunicorn: `gunicorn app:app`
- **SQLite** is fine for local use but not suitable for concurrent production traffic. Switch to PostgreSQL by changing `DATABASE_URL`.
- **No CSRF protection** — forms are not protected against cross-site request forgery. Add [Flask-WTF](https://flask-wtw.readthedocs.io/) before exposing this publicly.
- **Real-time chat via polling** — works well for small groups; for high traffic a WebSocket solution (e.g. Flask-SocketIO) would be more efficient.
- **No email notifications** — in-app notifications only; no email delivery on join request or meeting events.
