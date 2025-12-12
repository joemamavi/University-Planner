from flask import Flask, render_template, request, redirect, url_for
from models import db, Subject, Assignment, Event
from datetime import datetime, date
import calendar as cal_module
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///planner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/')
def dashboard():
    subjects = Subject.query.all()
    assignments = Assignment.query.filter(
        Assignment.due_date >= date.today()
    ).order_by(Assignment.is_exam.desc(), Assignment.due_date).all()
    exams = [a for a in assignments if a.is_exam]
    return render_template('dashboard.html', subjects=subjects, assignments=assignments, exams=exams, today=date.today())

# --- MONTHLY CALENDAR (Events & Exams) ---
@app.route('/calendar')
@app.route('/calendar/<int:year>/<int:month>')
def calendar_view(year=None, month=None):
    if year is None: 
        now = datetime.now()
        year, month = now.year, now.month

    cal = cal_module.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(year, month)
    
    db_events = Event.query.all()
    db_assignments = Assignment.query.all()

    events_by_date = {}

    for e in db_events:
        d_str = e.date.strftime('%Y-%m-%d')
        if d_str not in events_by_date: events_by_date[d_str] = []
        events_by_date[d_str].append({'title': e.title, 'tag': e.tag, 'is_assignment': False, 'id': e.id})

    for a in db_assignments:
        d_str = a.due_date.strftime('%Y-%m-%d')
        if d_str not in events_by_date: events_by_date[d_str] = []
        tag = 'danger' if a.is_exam else 'warning'
        events_by_date[d_str].append({'title': f"{a.subject.code}: {a.title}", 'tag': tag, 'is_assignment': True, 'id': a.id})

    # Navigation
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    return render_template('calendar.html', 
                           month_days=month_days, events_by_date=events_by_date,
                           current_year=year, current_month=month, month_name=cal_module.month_name[month],
                           prev_year=prev_year, prev_month=prev_month, next_year=next_year, next_month=next_month)

# --- NEW: WEEKLY TIMETABLE (Recurring Classes) ---
@app.route('/timetable')
def timetable_view():
    subjects = Subject.query.all()
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    hours = range(8, 19) # 8 AM to 6 PM
    timetable = {h: {d: None for d in days} for h in hours}

    for sub in subjects:
        if sub.schedule:
            # Parse "Mon 9AM, Wed 2PM"
            parts = sub.schedule.split(',')
            for part in parts:
                part = part.upper().strip()
                found_day = None
                for d in days:
                    if d.upper() in part:
                        found_day = d
                        break
                
                match = re.search(r'(\d+)', part)
                if found_day and match:
                    hour = int(match.group(1))
                    # Convert PM to 24h (except 12PM)
                    if 'PM' in part and hour != 12: hour += 12
                    # Handle 12AM edge case if needed, or strict 8-18 range
                    if hour in timetable: 
                        timetable[hour][found_day] = sub

    return render_template('timetable.html', timetable=timetable, days=days, hours=hours)

# --- ACTIONS ---
@app.route('/add_event', methods=['POST'])
def add_event():
    new_event = Event(
        title=request.form.get('title'),
        date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
        tag=request.form.get('tag')
    )
    db.session.add(new_event)
    db.session.commit()
    year, month = int(request.form.get('date').split('-')[0]), int(request.form.get('date').split('-')[1])
    return redirect(url_for('calendar_view', year=year, month=month))

@app.route('/delete_event/<int:id>')
def delete_event(id):
    event = Event.query.get_or_404(id)
    db.session.delete(event)
    db.session.commit()
    return redirect(url_for('calendar_view'))

@app.route('/subject/<int:id>')
def subject_details(id):
    subject = Subject.query.get_or_404(id)
    return render_template('subject_details.html', subject=subject)

@app.route('/update_resources/<int:id>', methods=['POST'])
def update_resources(id):
    subject = Subject.query.get_or_404(id)
    subject.syllabus_link = request.form.get('syllabus_link')
    subject.zoom_link = request.form.get('zoom_link')
    subject.professor_email = request.form.get('professor_email')
    subject.notes = request.form.get('notes')
    db.session.commit()
    return redirect(url_for('subject_details', id=id))

@app.route('/add_subject', methods=['POST'])
def add_subject():
    new_subject = Subject(
        name=request.form.get('name'),
        code=request.form.get('code'),
        professor=request.form.get('prof'),
        schedule=request.form.get('schedule')
    )
    db.session.add(new_subject)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/add_assignment', methods=['POST'])
def add_assignment():
    is_exam = True if request.form.get('is_exam') else False
    new_task = Assignment(
        title=request.form.get('title'),
        due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date(),
        subject_id=request.form.get('subject_id'),
        is_exam=is_exam
    )
    db.session.add(new_task)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete_subject/<int:id>')
def delete_subject(id):
    subject = Subject.query.get_or_404(id)
    db.session.delete(subject)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete_assignment/<int:id>')
def delete_assignment(id):
    task = Assignment.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/update_attendance/<int:subject_id>/<action>')
def update_attendance(subject_id, action):
    subject = Subject.query.get_or_404(subject_id)
    if action == 'present':
        subject.attended += 1
        subject.total_classes += 1
    elif action == 'absent':
        subject.total_classes += 1
    db.session.commit()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)