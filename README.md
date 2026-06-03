# MatchClass

A Flask web app where students can find study partners, create study groups, schedule meetings, and chat — all organised around shared courses.

---

## Features

### Core
| Feature | Details |
|---|---|
| Authentication | Register, login, logout with hashed passwords (min 6 chars). Sessions expire after 2 hours. |
| Profile editing | Update major, primary course, availability, bio, and additional courses. Password change requires re-entry. |
| Student matching | Dashboard shows all students enrolled in the same course, filterable by availability. |
| User profiles | Public profile page showing major, courses, availability, bio, shared groups, and reviews given. |
| Direct Messages | Private one-to-one messaging between any two users with real-time polling and unread badge. |

### Groups
| Feature | Details |
|---|---|
| Create group | Public (open join) or private (request-only) groups per course. Optional description, member limit, and tags. |
| Group tags | Tag groups with topic labels (e.g. `exam-prep`, `project`) for discovery. |
| Group search | Search groups across any course; filter by tag and availability. |
| Edit group | Creator can update name, description, contact info, member limit, visibility, and tags at any time. |
| Pinned announcement | Creator can pin a group-wide announcement shown at the top of the group page. |
| Transfer ownership | Creator can hand ownership to any current member. |
| Member management | Creator can approve/deny join requests and remove members. |

### Meetings
| Feature | Details |
|---|---|
| Schedule meetings | Date/time picker, optional location or video link, topic label. |
| Recurring meetings | Set weekly or biweekly recurrence with an optional end date — follow-up instances created automatically. |
| RSVP | Three-way RSVP: Yes / Maybe / No. Counts shown per status. |
| Export to calendar | Download a `.ics` file for any meeting to add it to Google Calendar, Apple Calendar, or Outlook. |
| Meeting reminders | In-app notification fired automatically when a meeting is under 24 hours away. |

### Chat & Communication
| Feature | Details |
|---|---|
| Real-time group chat | Per-group message board that updates every 2 seconds without page reloads. |
| Message reactions | React to any chat message with 👍 ❤️ 😂 — counts update instantly. |
| Message edit/delete | Edit or soft-delete your own messages inline; deleted messages show a placeholder. |
| @mentions | Type `@username` in chat to mention a group member — they receive a notification and mentions are highlighted in yellow. |
| Message search | Search the chat history by keyword directly from the chat panel. |
| Direct Messages | Poll-based DM threads with unread count badge in the nav bar. |

### Reviews & Discovery
| Feature | Details |
|---|---|
| Group reviews | Non-creator members can leave a 1–5 star rating and optional comment on a group. Aggregate score shown in header. |
| Activity indicator | Group cards show last-active date with a green dot for recently active groups. |
| Notifications | Bell badge in the nav bar for join request outcomes, new meetings, @mentions, and DMs. |

---

## Project Structure

```
MatchClass/
├── app.py                  # All routes, models, helpers, and app config (~1080 lines)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── .gitignore
├── static/
│   └── css/
│       └── style.css       # Campus Ink design system (~1600 lines, no framework)
└── templates/
    ├── layout.html         # Base template — nav, flash messages, notification badges
    ├── login.html
    ├── register.html
    ├── dashboard.html      # Student matches + groups, availability filter, last-active
    ├── profile.html        # Edit profile — bio, courses, availability
    ├── user_profile.html   # Public profile — bio, courses, reviews, DM button
    ├── search.html         # Search groups by course, tag, availability
    ├── create_group.html   # Create group with tags
    ├── edit_group.html     # Edit group details (creator only)
    ├── notifications.html  # Notification inbox
    ├── group_detail.html   # Meetings, RSVP, recurring, .ics, chat, @mention, edit/delete, reviews
    ├── messages.html       # DM inbox
    └── dm_thread.html      # DM conversation thread
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
# or
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

The SQLite database is created automatically at `instance/studyapp.db` on first run — no setup required.

---

## Database

### Schema migration

If you pull changes that add new model columns to an existing database, the simplest approach is to delete `instance/studyapp.db` and restart (wipes all data). For production, use Flask-Migrate or run `ALTER TABLE` statements manually.

### Models

| Model | Purpose |
|---|---|
| `User` | Student account — username, hashed password, major, primary course, availability, bio |
| `UserCourse` | Additional courses a student is enrolled in |
| `StudyGroup` | A group tied to a course — public/private, description, member limit, pinned announcement, last-active timestamp |
| `GroupTag` | Reusable topic tag attached to groups |
| `Meeting` | A scheduled session — title, date/time, location, recurrence settings |
| `RSVP` | A user's yes/maybe/no response to a meeting |
| `Message` | A chat message — supports soft-delete and edit timestamp |
| `Reaction` | An emoji reaction (👍 ❤️ 😂) on a chat message |
| `JoinRequest` | A pending/approved/denied request to join a private group |
| `Notification` | An unread in-app alert |
| `DirectMessage` | A private message between two users |
| `GroupReview` | A star rating + comment left on a group by a member |

---

## Tech Stack

- **Backend:** Python 3.11+, Flask 3, Flask-SQLAlchemy
- **Database:** SQLite (swappable for PostgreSQL via `DATABASE_URL`)
- **Templates:** Jinja2 with autoescape enabled
- **CSS:** Custom "Campus Ink" design system — dark editorial theme, no framework, no build step
- **Fonts:** Playfair Display (display) + DM Sans (body) via Google Fonts
- **Real-time:** Vanilla JS polling (`fetch` every 2 s) for group chat and DM threads
- **Calendar export:** `icalendar` library for `.ics` file generation

---

## Known Limitations

- **No CSRF protection** — forms are not protected against cross-site request forgery. Add [Flask-WTF](https://flask-wtf.readthedocs.io/) before deploying publicly.
- **SQLite** is fine for local use but not suitable for concurrent production traffic. Switch to PostgreSQL by changing `DATABASE_URL`.
- **No production WSGI server** — for deployment use Gunicorn: `gunicorn app:app`
- **Real-time via polling** — works well for small groups; for high traffic consider Flask-SocketIO.
- **No email notifications** — in-app only; no email delivery.
