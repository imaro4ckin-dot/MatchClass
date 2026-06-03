import io
import os
import re
from datetime import timedelta, datetime, UTC
from sqlalchemy.exc import IntegrityError
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, send_file)
from flask_sqlalchemy import SQLAlchemy
from icalendar import Calendar, Event
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-insecure-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///studyapp.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
db = SQLAlchemy(app)


# ── Association tables ──────────────────────────────────────────────────────

group_members = db.Table('group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('study_group.id'), primary_key=True)
)

group_tags_assoc = db.Table('group_tags_assoc',
    db.Column('group_id', db.Integer, db.ForeignKey('study_group.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('group_tag.id'), primary_key=True)
)


# ── Models ──────────────────────────────────────────────────────────────────

class User(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    username       = db.Column(db.String(80), unique=True, nullable=False)
    password       = db.Column(db.String(200), nullable=False)
    major          = db.Column(db.String(80), nullable=False)
    course         = db.Column(db.String(80), nullable=False)   # primary course
    available_time = db.Column(db.String(80), nullable=False)
    bio            = db.Column(db.Text, nullable=True)          # user bio (feature 9)

    extra_courses  = db.relationship('UserCourse', backref='user',
                                     lazy=True, cascade='all, delete-orphan')


class UserCourse(db.Model):
    """Secondary courses a student is enrolled in (feature 2)."""
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course  = db.Column(db.String(80), nullable=False)


class GroupTag(db.Model):
    """Reusable tag that can be attached to many groups (feature 12)."""
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)


class StudyGroup(db.Model):
    id                   = db.Column(db.Integer, primary_key=True)
    name                 = db.Column(db.String(80), nullable=False)
    course               = db.Column(db.String(80), nullable=False)
    creator_id           = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_info         = db.Column(db.String(120), nullable=False)
    description          = db.Column(db.Text, nullable=True)
    is_public            = db.Column(db.Boolean, default=True, nullable=False)
    max_members          = db.Column(db.Integer, nullable=True)
    pinned_announcement  = db.Column(db.Text, nullable=True)        # feature 5
    last_active          = db.Column(db.DateTime, nullable=True)    # feature 8

    members      = db.relationship('User', secondary=group_members, lazy='subquery',
                                   backref=db.backref('groups', lazy=True))
    meetings     = db.relationship('Meeting', backref='group', lazy=True,
                                   cascade='all, delete-orphan')
    messages     = db.relationship('Message', backref='group', lazy=True,
                                   cascade='all, delete-orphan')
    join_requests = db.relationship('JoinRequest', backref='group', lazy=True,
                                    cascade='all, delete-orphan')
    tags         = db.relationship('GroupTag', secondary=group_tags_assoc, lazy='subquery',
                                   backref=db.backref('groups', lazy=True))
    reviews      = db.relationship('GroupReview', backref='group', lazy=True,
                                   cascade='all, delete-orphan')


class Meeting(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    title           = db.Column(db.String(100), nullable=False)
    date_time       = db.Column(db.String(50), nullable=False)
    location        = db.Column(db.String(200), nullable=True)
    group_id        = db.Column(db.Integer, db.ForeignKey('study_group.id'), nullable=False)
    recurrence      = db.Column(db.String(20), nullable=True)   # 'weekly'/'biweekly'/None (feature 11)
    recurrence_end  = db.Column(db.String(20), nullable=True)   # YYYY-MM-DD cutoff

    rsvps = db.relationship('RSVP', backref='meeting', lazy=True, cascade='all, delete-orphan')


class RSVP(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meeting.id'), nullable=False)
    status     = db.Column(db.String(10), nullable=False)   # 'yes' / 'no' / 'maybe' (feature 13)

    user = db.relationship('User', backref='rsvps')


class Message(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    body       = db.Column(db.Text, nullable=False)
    timestamp  = db.Column(db.String(50), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id   = db.Column(db.Integer, db.ForeignKey('study_group.id'), nullable=False)
    edited_at  = db.Column(db.String(50), nullable=True)        # feature 3
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)  # feature 3

    author = db.relationship('User', backref='messages')


class JoinRequest(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('study_group.id'), nullable=False)
    status   = db.Column(db.String(10), nullable=False, default='pending')

    requester = db.relationship('User', backref='join_requests')


class Notification(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    link    = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    recipient = db.relationship('User', backref='notifications')


class Reaction(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    emoji      = db.Column(db.String(10), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'message_id', 'emoji'),)


class DirectMessage(db.Model):
    """DM between two users (feature 1)."""
    id           = db.Column(db.Integer, primary_key=True)
    sender_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body         = db.Column(db.Text, nullable=False)
    timestamp    = db.Column(db.String(50), nullable=False)
    is_read      = db.Column(db.Boolean, default=False, nullable=False)

    sender    = db.relationship('User', foreign_keys=[sender_id], backref='sent_dms')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_dms')


class GroupReview(db.Model):
    """Star rating + comment left on a group (feature 14)."""
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id  = db.Column(db.Integer, db.ForeignKey('study_group.id'), nullable=False)
    rating    = db.Column(db.Integer, nullable=False)   # 1–5
    comment   = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.String(50), nullable=False)

    reviewer  = db.relationship('User', backref='reviews_given')

    __table_args__ = (db.UniqueConstraint('user_id', 'group_id'),)


with app.app_context():
    db.create_all()


# ── Context processors ──────────────────────────────────────────────────────

@app.context_processor
def inject_unread_counts():
    if 'user_id' in session:
        uid = session['user_id']
        notif_count = Notification.query.filter_by(user_id=uid, is_read=False).count()
        dm_count    = DirectMessage.query.filter_by(recipient_id=uid, is_read=False).count()
        return {'unread_count': notif_count, 'unread_dm_count': dm_count}
    return {'unread_count': 0, 'unread_dm_count': 0}


# ── Helpers ─────────────────────────────────────────────────────────────────

def current_user():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user is None:
            session.clear()
        return user
    return None


def notify(user_id, message, link=None):
    db.session.add(Notification(user_id=user_id, message=message, link=link))


def update_last_active(group):
    group.last_active = datetime.now(UTC)


def parse_mentions(body, group, sender_id):
    """Fire notifications for every @username found in a message body."""
    for username in set(re.findall(r'@(\w+)', body)):
        target = User.query.filter_by(username=username).first()
        if target and target.id != sender_id and target in group.members:
            notify(target.id,
                   f'You were mentioned in "{group.name}"',
                   url_for('group_detail', group_id=group.id))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.path))
        if current_user() is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def _escape_like(s):
    """Escape SQL LIKE special characters to prevent unintended wildcard matches."""
    return s.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _sync_tags(group, raw_tags_str):
    """Replace a group's tags from a comma-separated string."""
    names = [t.strip().lower() for t in raw_tags_str.split(',') if t.strip()][:8]
    new_tags = []
    for name in names:
        tag = GroupTag.query.filter_by(name=name).first()
        if not tag:
            tag = GroupTag(name=name)
            db.session.add(tag)
        new_tags.append(tag)
    group.tags = new_tags


def _create_recurring_instances(base_meeting, group):
    """Spawn follow-up meeting copies for weekly/biweekly recurrence."""
    if not base_meeting.recurrence or base_meeting.recurrence == 'none':
        return
    try:
        dt = datetime.strptime(base_meeting.date_time, '%Y-%m-%dT%H:%M')
    except ValueError:
        return
    end_cutoff = None
    if base_meeting.recurrence_end:
        try:
            end_cutoff = datetime.strptime(base_meeting.recurrence_end, '%Y-%m-%d')
        except ValueError:
            pass
    delta = timedelta(weeks=1 if base_meeting.recurrence == 'weekly' else 2)
    for _ in range(8):  # cap at 8 instances
        dt += delta
        if end_cutoff and dt > end_cutoff:
            break
        db.session.add(Meeting(
            title=base_meeting.title,
            date_time=dt.strftime('%Y-%m-%dT%H:%M'),
            location=base_meeting.location,
            group_id=group.id,
            recurrence=None,   # instances are not themselves recurring
        ))


def _check_meeting_reminders(user, group):
    """Lazily fire a 24-h reminder notification if not already sent."""
    now = datetime.now(UTC)
    cutoff = now + timedelta(hours=24)
    for meeting in group.meetings:
        try:
            mt = datetime.strptime(meeting.date_time, '%Y-%m-%dT%H:%M')
        except ValueError:
            continue
        if now < mt <= cutoff:
            marker = f'reminder_meeting_{meeting.id}_user_{user.id}'
            already = Notification.query.filter_by(
                user_id=user.id, message=marker).first()
            if not already:
                db.session.add(Notification(
                    user_id=user.id,
                    message=marker,
                    link=url_for('group_detail', group_id=group.id),
                    is_read=False
                ))
                # visible reminder (separate record)
                notify(user.id,
                       f'Reminder: "{meeting.title}" in {group.name} is in less than 24 hours.',
                       url_for('group_detail', group_id=group.id))
    db.session.commit()


# ── Auth routes ─────────────────────────────────────────────────────────────

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('login.html')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username
            next_page = request.args.get('next', '')
            if not next_page or not next_page.startswith('/') or next_page.startswith('//'):
                next_page = url_for('dashboard')
            return redirect(next_page)
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username       = request.form.get('username', '').strip()
        password       = request.form.get('password', '')
        major          = request.form.get('major', '').strip()
        course         = request.form.get('course', '').strip()
        available_time = request.form.get('available_time', '').strip()

        if not all([username, password, major, course, available_time]):
            flash('All fields are required.', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('register.html')
        if len(username) > 80 or len(major) > 80 or len(course) > 80:
            flash('Input exceeds maximum length.', 'error')
            return render_template('register.html')
        if available_time not in ('Mornings', 'Afternoons', 'Evenings', 'Weekends'):
            flash('Invalid availability selection.', 'error')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username,
                        password=generate_password_hash(password),
                        major=major, course=course, available_time=available_time)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))


# ── Profile routes ───────────────────────────────────────────────────────────

@app.route('/user/<username>')
@login_required
def user_profile(username):
    viewer       = current_user()
    profile_user = User.query.filter_by(username=username).first_or_404()
    shared_groups = [g for g in profile_user.groups if viewer in g.members]
    reviews = GroupReview.query.filter_by(user_id=profile_user.id).all()
    return render_template('user_profile.html', profile_user=profile_user,
                           shared_groups=shared_groups, reviews=reviews)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user()
    if request.method == 'POST':
        major          = request.form.get('major', '').strip()
        course         = request.form.get('course', '').strip()
        available_time = request.form.get('available_time', '').strip()
        bio            = request.form.get('bio', '').strip()

        if not all([major, course, available_time]):
            flash('Major, course and availability are required.', 'error')
            return render_template('profile.html', user=user,
                                   extra_courses_str=', '.join(ec.course for ec in user.extra_courses))
        if available_time not in ('Mornings', 'Afternoons', 'Evenings', 'Weekends'):
            flash('Invalid availability selection.', 'error')
            return render_template('profile.html', user=user,
                                   extra_courses_str=', '.join(ec.course for ec in user.extra_courses))

        user.major          = major
        user.course         = course
        user.available_time = available_time
        user.bio            = bio or None

        # Extra courses (feature 2): replace all
        UserCourse.query.filter_by(user_id=user.id).delete()
        raw_extra = request.form.get('extra_courses', '')
        for c in [x.strip() for x in raw_extra.split(',') if x.strip()]:
            if c.lower() != course.lower():
                db.session.add(UserCourse(user_id=user.id, course=c[:80]))

        new_pw = request.form.get('new_password', '')
        if new_pw:
            if len(new_pw) < 6:
                flash('Password must be at least 6 characters.', 'error')
                return render_template('profile.html', user=user,
                                       extra_courses_str=', '.join(ec.course for ec in user.extra_courses))
            user.password = generate_password_hash(new_pw)

        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('profile.html', user=user,
                           extra_courses_str=', '.join(ec.course for ec in user.extra_courses))


# ── Dashboard & search ───────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    user       = current_user()
    avail_filter = request.args.get('avail', '').strip()

    match_q = User.query.filter(User.course == user.course, User.id != user.id)
    if avail_filter and avail_filter in ('Mornings', 'Afternoons', 'Evenings', 'Weekends'):
        match_q = match_q.filter(User.available_time == avail_filter)
    matches = match_q.all()

    all_groups = StudyGroup.query.filter_by(course=user.course).all()
    return render_template('dashboard.html', user=user, matches=matches,
                           all_groups=all_groups, avail_filter=avail_filter,
                           now=datetime.now(UTC))


@app.route('/search')
@login_required
def search():
    user       = current_user()
    query      = request.args.get('course', '').strip()
    tag_filter = request.args.get('tag', '').strip().lower()
    avail_f    = request.args.get('avail', '').strip()
    results    = []
    if query:
        q = StudyGroup.query.filter(StudyGroup.course.ilike(f'%{_escape_like(query)}%'))
        if tag_filter:
            q = q.join(StudyGroup.tags).filter(GroupTag.name == tag_filter)
        results = q.all()
    all_tags = GroupTag.query.order_by(GroupTag.name).all()
    return render_template('search.html', user=user, results=results,
                           query=query, tag_filter=tag_filter,
                           avail_filter=avail_f, all_tags=all_tags,
                           now=datetime.now(UTC))


# ── Group routes ─────────────────────────────────────────────────────────────

@app.route('/create_group', methods=['GET', 'POST'])
@login_required
def create_group():
    user = current_user()
    if request.method == 'POST':
        is_public = request.form.get('is_public') == 'on'
        new_group = StudyGroup(
            name=request.form.get('name', '').strip(),
            course=user.course,
            creator_id=user.id,
            contact_info=request.form.get('contact_info', '').strip(),
            description=request.form.get('description', '').strip() or None,
            is_public=is_public,
            max_members=int(m) if (m := request.form.get('max_members', '').strip())
                        and m.isdigit() and int(m) >= 2 else None
        )
        _sync_tags(new_group, request.form.get('tags_input', ''))
        new_group.members.append(user)
        db.session.add(new_group)
        db.session.commit()
        flash(f'Group "{new_group.name}" created!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('create_group.html', user=user)


@app.route('/join_group/<int:group_id>')
@login_required
def join_group(group_id):
    user  = current_user()
    group = StudyGroup.query.get_or_404(group_id)

    if user in group.members:
        flash('You are already a member of that group.', 'error')
        return redirect(url_for('dashboard'))

    if group.is_public:
        if group.max_members and len(group.members) >= group.max_members:
            flash('This group is full.', 'error')
            return redirect(url_for('dashboard'))
        try:
            group.members.append(user)
            db.session.commit()
            flash(f'You joined {group.name}!', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('You are already a member of that group.', 'error')
    else:
        existing = JoinRequest.query.filter_by(user_id=user.id, group_id=group.id).first()
        if existing and existing.status in ('pending', 'approved'):
            flash('You already have a pending or approved request for that group.', 'error')
        elif existing and existing.status == 'denied':
            existing.status = 'pending'
            db.session.commit()
            flash(f'Join request re-sent to "{group.name}".', 'success')
        else:
            db.session.add(JoinRequest(user_id=user.id, group_id=group.id))
            db.session.commit()
            flash(f'Join request sent to "{group.name}".', 'success')

    return redirect(url_for('dashboard'))


@app.route('/leave_group/<int:group_id>')
@login_required
def leave_group(group_id):
    user  = current_user()
    group = StudyGroup.query.get_or_404(group_id)

    if user.id == group.creator_id:
        flash('You are the group creator — delete the group instead.', 'error')
        return redirect(url_for('group_detail', group_id=group_id))

    if user in group.members:
        group.members.remove(user)
        db.session.commit()
        flash(f'You left "{group.name}".', 'success')
    return redirect(url_for('dashboard'))


@app.route('/delete_group/<int:group_id>', methods=['POST'])
@login_required
def delete_group(group_id):
    user  = current_user()
    group = StudyGroup.query.get_or_404(group_id)

    if user.id != group.creator_id:
        flash('Only the group creator can delete this group.', 'error')
        return redirect(url_for('group_detail', group_id=group_id))

    db.session.delete(group)
    db.session.commit()
    flash(f'Group "{group.name}" deleted.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/edit_group/<int:group_id>', methods=['GET', 'POST'])
@login_required
def edit_group(group_id):
    user  = current_user()
    group = StudyGroup.query.get_or_404(group_id)

    if user.id != group.creator_id:
        flash('Only the group creator can edit this group.', 'error')
        return redirect(url_for('group_detail', group_id=group_id))

    if request.method == 'POST':
        group.name         = request.form.get('name', '').strip()
        group.contact_info = request.form.get('contact_info', '').strip()
        group.description  = request.form.get('description', '').strip() or None
        group.is_public    = request.form.get('is_public') == 'on'
        max_m              = request.form.get('max_members', '').strip()
        group.max_members  = int(max_m) if max_m.isdigit() and int(max_m) >= 2 else None
        _sync_tags(group, request.form.get('tags_input', ''))
        db.session.commit()
        flash('Group updated!', 'success')
        return redirect(url_for('group_detail', group_id=group_id))

    return render_template('edit_group.html', group=group, user=user)


@app.route('/kick_member/<int:group_id>/<int:member_id>', methods=['POST'])
@login_required
def kick_member(group_id, member_id):
    user   = current_user()
    group  = StudyGroup.query.get_or_404(group_id)
    if user.id != group.creator_id:
        flash('Only the group creator can remove members.', 'error')
        return redirect(url_for('group_detail', group_id=group_id))
    member = User.query.get_or_404(member_id)
    if member in group.members:
        group.members.remove(member)
        db.session.commit()
        flash(f'{member.username} removed from the group.', 'success')
    return redirect(url_for('group_detail', group_id=group_id))


@app.route('/transfer_ownership/<int:group_id>/<int:member_id>', methods=['POST'])
@login_required
def transfer_ownership(group_id, member_id):
    user      = current_user()
    group     = StudyGroup.query.get_or_404(group_id)
    if user.id != group.creator_id:
        flash('Only the group creator can transfer ownership.', 'error')
        return redirect(url_for('group_detail', group_id=group_id))
    new_owner = User.query.get_or_404(member_id)
    if new_owner not in group.members:
        flash('That user is not a member of this group.', 'error')
        return redirect(url_for('group_detail', group_id=group_id))
    group.creator_id = new_owner.id
    db.session.commit()
    flash(f'Ownership transferred to {new_owner.username}.', 'success')
    return redirect(url_for('group_detail', group_id=group_id))


@app.route('/group/<int:group_id>', methods=['GET', 'POST'])
@login_required
def group_detail(group_id):
    user  = current_user()
    group = StudyGroup.query.get_or_404(group_id)

    if request.method == 'POST':
        if user not in group.members:
            flash('You must be a member to perform this action.', 'error')
            return redirect(url_for('group_detail', group_id=group_id))

        action = request.form.get('action')

        if action == 'schedule_meeting':
            recurrence = request.form.get('recurrence', 'none')
            rec_end    = request.form.get('recurrence_end', '').strip() or None
            new_meeting = Meeting(
                title=request.form.get('title', '').strip(),
                date_time=request.form.get('date_time', ''),
                location=request.form.get('location', '').strip() or None,
                group_id=group.id,
                recurrence=recurrence if recurrence != 'none' else None,
                recurrence_end=rec_end,
            )
            db.session.add(new_meeting)
            _create_recurring_instances(new_meeting, group)
            for member in group.members:
                if member.id != user.id:
                    notify(member.id,
                           f'New meeting "{new_meeting.title}" in {group.name}',
                           url_for('group_detail', group_id=group.id))
            update_last_active(group)
            db.session.commit()
            flash('Meeting scheduled!', 'success')

        elif action == 'post_message':
            body = request.form.get('body', '').strip()
            if body:
                msg = Message(body=body,
                              timestamp=datetime.now(UTC).strftime('%Y-%m-%d %H:%M'),
                              user_id=user.id, group_id=group.id)
                db.session.add(msg)
                parse_mentions(body, group, user.id)
                update_last_active(group)
                db.session.commit()

        return redirect(url_for('group_detail', group_id=group.id))

    # Lazy meeting reminders (feature 7)
    _check_meeting_reminders(user, group)

    user_rsvps = {r.meeting_id: r.status for r in RSVP.query.filter_by(user_id=user.id).all()}
    pending_requests = []
    if user.id == group.creator_id:
        pending_requests = JoinRequest.query.filter_by(group_id=group.id, status='pending').all()

    # Review data
    reviews      = GroupReview.query.filter_by(group_id=group.id).all()
    avg_rating   = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else None
    user_review  = GroupReview.query.filter_by(group_id=group.id, user_id=user.id).first()
    can_review   = (user in group.members and user.id != group.creator_id and user_review is None)

    return render_template('group_detail.html', group=group, user=user,
                           user_rsvps=user_rsvps, pending_requests=pending_requests,
                           reviews=reviews, avg_rating=avg_rating,
                           user_review=user_review, can_review=can_review)


# ── Pin announcement (feature 5) ─────────────────────────────────────────────

@app.route('/group/<int:group_id>/pin', methods=['POST'])
@login_required
def pin_announcement(group_id):
    user  = current_user()
    group = StudyGroup.query.get_or_404(group_id)
    if user.id != group.creator_id:
        flash('Only the group creator can pin an announcement.', 'error')
        return redirect(url_for('group_detail', group_id=group_id))
    group.pinned_announcement = request.form.get('announcement', '').strip() or None
    db.session.commit()
    flash('Announcement updated.', 'success')
    return redirect(url_for('group_detail', group_id=group_id))


# ── Group tags (feature 12) ──────────────────────────────────────────────────

@app.route('/group/<int:group_id>/tags', methods=['POST'])
@login_required
def update_group_tags(group_id):
    user  = current_user()
    group = StudyGroup.query.get_or_404(group_id)
    if user.id != group.creator_id:
        return jsonify({'error': 'forbidden'}), 403
    _sync_tags(group, request.form.get('tags', ''))
    db.session.commit()
    return jsonify({'tags': [t.name for t in group.tags]})


# ── Group reviews (feature 14) ───────────────────────────────────────────────

@app.route('/group/<int:group_id>/reviews', methods=['POST'])
@login_required
def submit_review(group_id):
    user  = current_user()
    group = StudyGroup.query.get_or_404(group_id)

    if user not in group.members or user.id == group.creator_id:
        flash('Only non-creator members can leave a review.', 'error')
        return redirect(url_for('group_detail', group_id=group_id))

    if GroupReview.query.filter_by(group_id=group_id, user_id=user.id).first():
        flash('You have already reviewed this group.', 'error')
        return redirect(url_for('group_detail', group_id=group_id))

    rating_raw = request.form.get('rating', '')
    if not rating_raw.isdigit() or not (1 <= int(rating_raw) <= 5):
        flash('Rating must be between 1 and 5.', 'error')
        return redirect(url_for('group_detail', group_id=group_id))

    db.session.add(GroupReview(
        user_id=user.id, group_id=group_id,
        rating=int(rating_raw),
        comment=request.form.get('comment', '').strip() or None,
        timestamp=datetime.now(UTC).strftime('%Y-%m-%d %H:%M')
    ))
    db.session.commit()
    flash('Review submitted!', 'success')
    return redirect(url_for('group_detail', group_id=group_id))


# ── Meeting routes ────────────────────────────────────────────────────────────

@app.route('/delete_meeting/<int:meeting_id>', methods=['POST'])
@login_required
def delete_meeting(meeting_id):
    user    = current_user()
    meeting = Meeting.query.get_or_404(meeting_id)
    group   = meeting.group
    if user.id != group.creator_id:
        flash('Only the group creator can delete meetings.', 'error')
        return redirect(url_for('group_detail', group_id=group.id))
    db.session.delete(meeting)
    db.session.commit()
    flash('Meeting deleted.', 'success')
    return redirect(url_for('group_detail', group_id=group.id))


@app.route('/rsvp/<int:meeting_id>/<status>', methods=['POST'])
@login_required
def rsvp(meeting_id, status):
    if status not in ('yes', 'no', 'maybe'):   # feature 13
        return redirect(url_for('dashboard'))
    user    = current_user()
    meeting = Meeting.query.get_or_404(meeting_id)
    existing = RSVP.query.filter_by(user_id=user.id, meeting_id=meeting_id).first()
    if existing:
        existing.status = status
    else:
        db.session.add(RSVP(user_id=user.id, meeting_id=meeting_id, status=status))
    db.session.commit()
    return redirect(url_for('group_detail', group_id=meeting.group_id))


@app.route('/meeting/<int:meeting_id>/export.ics')
@login_required
def export_ics(meeting_id):
    """Download a .ics calendar file for a meeting (feature 15)."""
    user    = current_user()
    meeting = Meeting.query.get_or_404(meeting_id)
    group   = meeting.group

    if user not in group.members:
        flash('You must be a member to export this meeting.', 'error')
        return redirect(url_for('dashboard'))

    try:
        dt = datetime.strptime(meeting.date_time, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Invalid meeting date format.', 'error')
        return redirect(url_for('group_detail', group_id=group.id))

    cal = Calendar()
    cal.add('prodid', '-//MatchClass//EN')
    cal.add('version', '2.0')

    event = Event()
    event.add('summary', f'{meeting.title} — {group.name}')
    event.add('dtstart', dt)
    event.add('dtend',   dt + timedelta(hours=1))
    if meeting.location:
        event.add('location', meeting.location)
    event.add('description', f'Study group: {group.name}\nCourse: {group.course}')
    cal.add_component(event)

    buf = io.BytesIO(cal.to_ical())
    buf.seek(0)
    safe_title = re.sub(r'[^\w\-]', '_', meeting.title)
    return send_file(buf, mimetype='text/calendar',
                     as_attachment=True,
                     download_name=f'{safe_title}.ics')


# ── Join request routes ───────────────────────────────────────────────────────

@app.route('/approve_request/<int:request_id>', methods=['POST'])
@login_required
def approve_request(request_id):
    user  = current_user()
    req   = JoinRequest.query.get_or_404(request_id)
    group = req.group

    if user.id != group.creator_id:
        flash('Not authorised.', 'error')
        return redirect(url_for('dashboard'))
    if req.status != 'pending':
        flash('This request has already been handled.', 'error')
        return redirect(url_for('group_detail', group_id=group.id))
    if group.max_members and len(group.members) >= group.max_members:
        flash('Cannot approve — group is already full.', 'error')
        return redirect(url_for('group_detail', group_id=group.id))

    req.status = 'approved'
    if req.requester not in group.members:
        group.members.append(req.requester)
    notify(req.user_id,
           f'Your request to join "{group.name}" was approved!',
           url_for('group_detail', group_id=group.id))
    db.session.commit()
    flash(f'{req.requester.username} approved!', 'success')
    return redirect(url_for('group_detail', group_id=group.id))


@app.route('/deny_request/<int:request_id>', methods=['POST'])
@login_required
def deny_request(request_id):
    user  = current_user()
    req   = JoinRequest.query.get_or_404(request_id)
    group = req.group

    if user.id != group.creator_id:
        flash('Not authorised.', 'error')
        return redirect(url_for('dashboard'))

    req.status = 'denied'
    notify(req.user_id,
           f'Your request to join "{group.name}" was declined.',
           url_for('dashboard'))
    db.session.commit()
    flash(f'{req.requester.username} denied.', 'success')
    return redirect(url_for('group_detail', group_id=group.id))


# ── Message edit / delete (feature 3) ────────────────────────────────────────

@app.route('/group/<int:group_id>/messages/<int:msg_id>/edit', methods=['POST'])
@login_required
def edit_message(group_id, msg_id):
    user = current_user()
    msg  = Message.query.get_or_404(msg_id)
    if msg.group_id != group_id or msg.user_id != user.id:
        return jsonify({'error': 'forbidden'}), 403
    new_body = request.form.get('body', '').strip()
    if not new_body:
        return jsonify({'error': 'empty body'}), 400
    msg.body      = new_body
    msg.edited_at = datetime.now(UTC).strftime('%Y-%m-%d %H:%M')
    db.session.commit()
    return jsonify({'ok': True, 'id': msg.id, 'body': msg.body, 'edited_at': msg.edited_at})


@app.route('/group/<int:group_id>/messages/<int:msg_id>/delete', methods=['POST'])
@login_required
def delete_message(group_id, msg_id):
    user = current_user()
    msg  = Message.query.get_or_404(msg_id)
    group = StudyGroup.query.get_or_404(group_id)
    # Allow own messages or group creator
    if msg.group_id != group_id or (msg.user_id != user.id and user.id != group.creator_id):
        return jsonify({'error': 'forbidden'}), 403
    msg.is_deleted = True
    msg.body       = ''   # clear content
    db.session.commit()
    return jsonify({'ok': True, 'id': msg.id, 'deleted': True})


# ── Notifications ─────────────────────────────────────────────────────────────

@app.route('/notifications')
@login_required
def notifications():
    user   = current_user()
    notifs = Notification.query.filter_by(user_id=user.id).order_by(
        Notification.id.desc()).all()
    # Render first so unread styling is visible, then mark read
    response = render_template('notifications.html', user=user, notifs=notifs)
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return response


# ── Group messages API ────────────────────────────────────────────────────────

@app.route('/react/<int:message_id>/<path:emoji>', methods=['POST'])
@login_required
def react(message_id, emoji):
    if emoji not in ('👍', '❤️', '😂'):
        return jsonify({'error': 'invalid emoji'}), 400
    user = current_user()
    existing = Reaction.query.filter_by(
        user_id=user.id, message_id=message_id, emoji=emoji).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Reaction(user_id=user.id, message_id=message_id, emoji=emoji))
    db.session.commit()
    counts = {e: Reaction.query.filter_by(message_id=message_id, emoji=e).count()
              for e in ('👍', '❤️', '😂')}
    return jsonify(counts)


@app.route('/group/<int:group_id>/messages')
@login_required
def group_messages(group_id):
    user  = current_user()
    group = StudyGroup.query.get_or_404(group_id)
    if user not in group.members:
        return jsonify({'error': 'forbidden'}), 403

    since = request.args.get('since', 0, type=int)
    q_str = request.args.get('q', '').strip()   # feature 10: search

    q = Message.query.filter(
        Message.group_id == group_id,
        Message.id > since,
        Message.is_deleted == False        # noqa: E712
    )
    if q_str:
        q = q.filter(Message.body.ilike(f'%{_escape_like(q_str)}%'))

    msgs = q.order_by(Message.id.asc()).limit(100).all()
    return jsonify([
        {
            'id':        m.id,
            'author':    m.author.username,
            'body':      m.body,
            'timestamp': m.timestamp,
            'edited_at': m.edited_at,
            'is_mine':   m.user_id == user.id,
            'reactions': {e: Reaction.query.filter_by(message_id=m.id, emoji=e).count()
                          for e in ('👍', '❤️', '😂')}
        }
        for m in msgs
    ])


# ── Direct Messages (feature 1) ───────────────────────────────────────────────

@app.route('/messages')
@login_required
def dm_inbox():
    user = current_user()
    # Get the latest DM per conversation partner
    sent      = db.session.query(DirectMessage.recipient_id).filter_by(sender_id=user.id)
    received  = db.session.query(DirectMessage.sender_id).filter_by(recipient_id=user.id)
    partner_ids = {r[0] for r in sent.union(received).all()}
    partners  = User.query.filter(User.id.in_(partner_ids)).all()

    conversations = []
    for partner in partners:
        last_msg = DirectMessage.query.filter(
            db.or_(
                db.and_(DirectMessage.sender_id == user.id,
                        DirectMessage.recipient_id == partner.id),
                db.and_(DirectMessage.sender_id == partner.id,
                        DirectMessage.recipient_id == user.id)
            )
        ).order_by(DirectMessage.id.desc()).first()
        unread = DirectMessage.query.filter_by(
            sender_id=partner.id, recipient_id=user.id, is_read=False).count()
        conversations.append({
            'username':  partner.username,
            'preview':   (last_msg.body[:60] + '…' if last_msg and len(last_msg.body) > 60 else (last_msg.body if last_msg else '')),
            'timestamp': last_msg.timestamp if last_msg else '',
            'unread':    unread > 0,
            '_sort_key': last_msg.id if last_msg else 0,
        })

    conversations.sort(key=lambda c: c['_sort_key'], reverse=True)
    return render_template('messages.html', user=user, conversations=conversations)


@app.route('/messages/<username>', methods=['GET', 'POST'])
@login_required
def dm_thread(username):
    user  = current_user()
    other = User.query.filter_by(username=username).first_or_404()
    if other.id == user.id:
        return redirect(url_for('dm_inbox'))

    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if body:
            db.session.add(DirectMessage(
                sender_id=user.id, recipient_id=other.id,
                body=body, timestamp=datetime.now(UTC).strftime('%Y-%m-%d %H:%M')
            ))
            notify(other.id, f'{user.username} sent you a message.',
                   url_for('dm_thread', username=user.username))
            db.session.commit()
        return redirect(url_for('dm_thread', username=username))

    # Mark incoming as read
    DirectMessage.query.filter_by(
        sender_id=other.id, recipient_id=user.id, is_read=False
    ).update({'is_read': True})
    db.session.commit()

    messages = DirectMessage.query.filter(
        db.or_(
            db.and_(DirectMessage.sender_id == user.id,
                    DirectMessage.recipient_id == other.id),
            db.and_(DirectMessage.sender_id == other.id,
                    DirectMessage.recipient_id == user.id)
        )
    ).order_by(DirectMessage.id.asc()).limit(200).all()

    last_id = messages[-1].id if messages else 0
    return render_template('dm_thread.html', user=user, other=other,
                           messages=messages, last_id=last_id)


@app.route('/messages/<username>/poll')
@login_required
def dm_poll(username):
    user    = current_user()
    partner = User.query.filter_by(username=username).first_or_404()
    since   = request.args.get('since', 0, type=int)
    msgs = DirectMessage.query.filter(
        db.or_(
            db.and_(DirectMessage.sender_id == user.id,
                    DirectMessage.recipient_id == partner.id),
            db.and_(DirectMessage.sender_id == partner.id,
                    DirectMessage.recipient_id == user.id)
        ),
        DirectMessage.id > since
    ).order_by(DirectMessage.id.asc()).limit(50).all()

    # Mark new incoming as read
    for m in msgs:
        if m.recipient_id == user.id and not m.is_read:
            m.is_read = True
    db.session.commit()

    return jsonify([
        {'id': m.id, 'author': m.sender.username,
         'body': m.body, 'timestamp': m.timestamp,
         'is_mine': m.sender_id == user.id}
        for m in msgs
    ])


if __name__ == '__main__':
    app.run(debug=True)
