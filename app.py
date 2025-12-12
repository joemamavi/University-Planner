from flask import Flask, render_template, request, redirect, url_for
from models import db, Subject, Assignment
from datetime import datetime, date
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
    
    # Sort: Exams first, then by date
    assignments = Assignment.query.filter(
        Assignment.due_date >= date.today()
    ).order_by(Assignment.is_exam.desc(), Assignment.due_date).all()
    
    # Filter just exams for the hero section alert
    exams = [a for a in assignments if a.is_exam]

    return render_template('dashboard.html', subjects=subjects, assignments=assignments, exams=exams, today=date.today())

@app.route('/calendar')
def calendar():
    subjects = Subject.query.all()
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    hours = range(8, 19)
    timetable = {h: {d: None for d in days} for h in hours}

    for sub in subjects:
        if sub.schedule:
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
                    if 'PM' in part and hour != 12: hour += 12
                    if hour in timetable: timetable[hour][found_day] = sub

    return render_template('calendar.html', timetable=timetable, days=days, hours=hours)

# --- NEW: Resource Locker Routes ---
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
# -----------------------------------

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
    # Check if "is_exam" checkbox was checked
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