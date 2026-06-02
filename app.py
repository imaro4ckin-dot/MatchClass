import os
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-insecure-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///studyapp.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
db = SQLAlchemy(app)


# --- ASSOCIATION TABLES ---

group_members = db.Table('group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('study_group.id'), primary_key=True)
)


# --- MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    major = db.Column(db.String(80), nullable=False)
    course = db.Column(db.String(80), nullable=False)
    available_time = db.Column(db.String(80), nullable=False)


class StudyGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    course = db.Column(db.String(80), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_info = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_public = db.Column(db.Boolean, default=True, nullable=False)
    max_members = db.Column(db.Integer, nullable=True)  # None = unlimited

    members = db.relationship('User', secondary=group_members, lazy='subquery',
                              backref=db.backref('groups', lazy=True))
    meetings = db.relationship('Meeting', backref='group', lazy=True, cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='group', lazy=True, cascade='all, delete-orphan')
    join_requests = db.relationship('JoinRequest', backref='group', lazy=True, cascade='all, delete-orphan')


class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date_time = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('study_group.id'), nullable=False)

    rsvps = db.relationship('RSVP', backref='meeting', lazy=True, cascade='all, delete-orphan')


class RSVP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meeting.id'), nullable=False)
    status = db.Column(db.String(10), nullable=False)  # 'yes' or 'no'

    user = db.relationship('User', backref='rsvps')


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('study_group.id'), nullable=False)

    author = db.relationship('User', backref='messages')


class JoinRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('study_group.id'), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='pending')  # pending / approved / denied

    requester = db.relationship('User', backref='join_requests')


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    link = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    recipient = db.relationship('User', backref='notifications')


class Reaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    emoji = db.Column(db.String(10), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'message_id', 'emoji'),)


with app.app_context():
    db.create_all()


@app.context_processor
def inject_unread_count():
    if 'user_id' in session:
        count = Notification.query.filter_by(user_id=session['user_id'], is_read=False).count()
        return {'unread_count': count}
    return {'unread_count': 0}


# --- HELPERS ---

def current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


def notify(user_id, message, link=None):
    db.session.add(Notification(user_id=user_id, message=message, link=link))


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated


# --- AUTH ROUTES ---

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username
            next_page = request.args.get('next') or url_for('dashboard')
            return redirect(next_page)
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if User.query.filter_by(username=request.form['username']).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('register'))
        new_user = User(
            username=request.form['username'],
            password=generate_password_hash(request.form['password']),
            major=request.form['major'],
            course=request.form['course'],
            available_time=request.form['available_time']
        )
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


# --- PROFILE ---

@app.route('/user/<username>')
@login_required
def user_profile(username):
    viewer = current_user()
    profile_user = User.query.filter_by(username=username).first_or_404()
    shared_groups = [g for g in profile_user.groups if viewer in g.members]
    return render_template('user_profile.html', profile_user=profile_user, shared_groups=shared_groups)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user()
    if request.method == 'POST':
        user.major = request.form['major']
        user.course = request.form['course']
        user.available_time = request.form['available_time']
        if request.form.get('new_password'):
            user.password = generate_password_hash(request.form['new_password'])
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('profile.html', user=user)


# --- DASHBOARD & SEARCH ---

@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    matches = User.query.filter(User.course == user.course, User.id != user.id).all()
    all_groups = StudyGroup.query.filter_by(course=user.course).all()
    return render_template('dashboard.html', user=user, matches=matches, all_groups=all_groups)


@app.route('/search')
@login_required
def search():
    user = current_user()
    query = request.args.get('course', '').strip()
    results = []
    if query:
        results = StudyGroup.query.filter(StudyGroup.course.ilike(f'%{query}%')).all()
    return render_template('search.html', user=user, results=results, query=query)


# --- GROUP ROUTES ---

@app.route('/create_group', methods=['GET', 'POST'])
@login_required
def create_group():
    user = current_user()
    if request.method == 'POST':
        is_public = request.form.get('is_public') == 'on'
        new_group = StudyGroup(
            name=request.form['name'],
            course=user.course,
            creator_id=user.id,
            contact_info=request.form['contact_info'],
            description=request.form.get('description', '').strip() or None,
            is_public=is_public,
            max_members=int(m) if (m := request.form.get('max_members', '').strip()) and m.isdigit() and int(m) > 0 else None
        )
        new_group.members.append(user)
        db.session.add(new_group)
        db.session.commit()
        flash(f'Group "{new_group.name}" created!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('create_group.html', user=user)


@app.route('/join_group/<int:group_id>')
@login_required
def join_group(group_id):
    user = current_user()
    group = StudyGroup.query.get_or_404(group_id)

    if user in group.members:
        flash('You are already a member of that group.', 'error')
        return redirect(url_for('dashboard'))

    if group.is_public:
        if group.max_members and len(group.members) >= group.max_members:
            flash('This group is full.', 'error')
            return redirect(url_for('dashboard'))
        group.members.append(user)
        db.session.commit()
        flash(f'You joined {group.name}!', 'success')
    else:
        existing = JoinRequest.query.filter_by(user_id=user.id, group_id=group.id).first()
        if existing:
            flash('You already have a pending request for that group.', 'error')
        else:
            req = JoinRequest(user_id=user.id, group_id=group.id)
            db.session.add(req)
            db.session.commit()
            flash(f'Join request sent to "{group.name}".', 'success')

    return redirect(url_for('dashboard'))


@app.route('/leave_group/<int:group_id>')
@login_required
def leave_group(group_id):
    user = current_user()
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
    user = current_user()
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
    user = current_user()
    group = StudyGroup.query.get_or_404(group_id)

    if user.id != group.creator_id:
        flash('Only the group creator can edit this group.', 'error')
        return redirect(url_for('group_detail', group_id=group_id))

    if request.method == 'POST':
        group.name = request.form['name'].strip()
        group.contact_info = request.form['contact_info'].strip()
        group.description = request.form.get('description', '').strip() or None
        group.is_public = request.form.get('is_public') == 'on'
        max_m = request.form.get('max_members', '').strip()
        group.max_members = int(max_m) if max_m.isdigit() and int(max_m) > 0 else None
        db.session.commit()
        flash('Group updated!', 'success')
        return redirect(url_for('group_detail', group_id=group_id))

    return render_template('edit_group.html', group=group, user=user)


@app.route('/kick_member/<int:group_id>/<int:member_id>', methods=['POST'])
@login_required
def kick_member(group_id, member_id):
    user = current_user()
    group = StudyGroup.query.get_or_404(group_id)

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
    user = current_user()
    group = StudyGroup.query.get_or_404(group_id)

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
    user = current_user()
    group = StudyGroup.query.get_or_404(group_id)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'schedule_meeting':
            new_meeting = Meeting(
                title=request.form['title'],
                date_time=request.form['date_time'],
                location=request.form.get('location', '').strip() or None,
                group_id=group.id
            )
            db.session.add(new_meeting)
            # Notify all members except the scheduler
            for member in group.members:
                if member.id != user.id:
                    notify(member.id,
                           f'New meeting "{request.form["title"]}" in {group.name}',
                           url_for('group_detail', group_id=group.id))
            db.session.commit()
            flash('Meeting scheduled!', 'success')

        elif action == 'post_message':
            from datetime import datetime
            msg = Message(
                body=request.form['body'].strip(),
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'),
                user_id=user.id,
                group_id=group.id
            )
            db.session.add(msg)
            db.session.commit()

        return redirect(url_for('group_detail', group_id=group.id))

    # Build per-meeting RSVP lookup for current user
    user_rsvps = {r.meeting_id: r.status for r in RSVP.query.filter_by(user_id=user.id).all()}

    # Pending join requests (for creator)
    pending_requests = []
    if user.id == group.creator_id:
        pending_requests = JoinRequest.query.filter_by(group_id=group.id, status='pending').all()

    return render_template('group_detail.html', group=group, user=user,
                           user_rsvps=user_rsvps, pending_requests=pending_requests)


# --- MEETING ROUTES ---

@app.route('/delete_meeting/<int:meeting_id>', methods=['POST'])
@login_required
def delete_meeting(meeting_id):
    user = current_user()
    meeting = Meeting.query.get_or_404(meeting_id)
    group = meeting.group

    if user.id != group.creator_id and user not in group.members:
        flash('Not authorised.', 'error')
        return redirect(url_for('dashboard'))

    db.session.delete(meeting)
    db.session.commit()
    flash('Meeting deleted.', 'success')
    return redirect(url_for('group_detail', group_id=group.id))


@app.route('/rsvp/<int:meeting_id>/<status>', methods=['POST'])
@login_required
def rsvp(meeting_id, status):
    if status not in ('yes', 'no'):
        return redirect(url_for('dashboard'))

    user = current_user()
    meeting = Meeting.query.get_or_404(meeting_id)

    existing = RSVP.query.filter_by(user_id=user.id, meeting_id=meeting_id).first()
    if existing:
        existing.status = status
    else:
        db.session.add(RSVP(user_id=user.id, meeting_id=meeting_id, status=status))

    db.session.commit()
    return redirect(url_for('group_detail', group_id=meeting.group_id))


# --- JOIN REQUEST ROUTES ---

@app.route('/approve_request/<int:request_id>', methods=['POST'])
@login_required
def approve_request(request_id):
    user = current_user()
    req = JoinRequest.query.get_or_404(request_id)
    group = req.group

    if user.id != group.creator_id:
        flash('Not authorised.', 'error')
        return redirect(url_for('dashboard'))

    req.status = 'approved'
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
    user = current_user()
    req = JoinRequest.query.get_or_404(request_id)
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


# --- MESSAGES API ---

@app.route('/notifications')
@login_required
def notifications():
    user = current_user()
    notifs = Notification.query.filter_by(user_id=user.id).order_by(Notification.id.desc()).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template('notifications.html', user=user, notifs=notifs)


@app.route('/react/<int:message_id>/<path:emoji>', methods=['POST'])
@login_required
def react(message_id, emoji):
    if emoji not in ('👍', '❤️', '😂'):
        return jsonify({'error': 'invalid emoji'}), 400
    user = current_user()
    existing = Reaction.query.filter_by(user_id=user.id, message_id=message_id, emoji=emoji).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Reaction(user_id=user.id, message_id=message_id, emoji=emoji))
    db.session.commit()
    counts = {}
    for e in ('👍', '❤️', '😂'):
        counts[e] = Reaction.query.filter_by(message_id=message_id, emoji=e).count()
    return jsonify(counts)


@app.route('/group/<int:group_id>/messages')
@login_required
def group_messages(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    since = request.args.get('since', 0, type=int)
    msgs = Message.query.filter(
        Message.group_id == group_id,
        Message.id > since
    ).order_by(Message.id.asc()).all()
    return jsonify([
        {
            'id': m.id,
            'author': m.author.username,
            'body': m.body,
            'timestamp': m.timestamp,
            'reactions': {
                e: Reaction.query.filter_by(message_id=m.id, emoji=e).count()
                for e in ('👍', '❤️', '😂')
            }
        }
        for m in msgs
    ])


if __name__ == '__main__':
    app.run(debug=True)
