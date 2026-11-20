
from flask import Flask, render_template, abort, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection, create_tables

app = Flask(__name__)
app.secret_key = 'medikiosk_secret_key_2026'


# HOME PAGE
@app.route('/')
def home():
    return render_template('index.html')


# MEDICINE PORTALS
@app.route('/modern')
def modern():
    return render_template('login.html', system='Modern Medicine')


@app.route('/ayurveda')
def ayurveda():
    return render_template('login.html', system='Ayurveda')


# RED FLAG DETECTION
def detect_red_flags(symptoms, severity):

    text = symptoms.lower()

    emergency_keywords = [
        'severe breathing difficulty',
        'difficulty breathing',
        'cannot breathe',
        'unconscious',
        'fainting',
        'severe bleeding'
    ]

    warning_keywords = [
        'chest pain',
        'breathlessness',
        'shortness of breath',
        'blood in vomit',
        'severe headache'
    ]

    detected_emergency = [
        word for word in emergency_keywords if word in text
    ]

    detected_warning = [
        word for word in warning_keywords if word in text
    ]

    if detected_emergency:
        return (
            'Emergency',
            'Potential emergency symptoms: ' + ', '.join(detected_emergency)
        )

    elif detected_warning:
        return (
            'Warning',
            'Symptoms requiring doctor review: ' + ', '.join(detected_warning)
        )

    elif severity == 'Severe':
        return (
            'Warning',
            'Patient has reported severe symptoms. Doctor review required.'
        )

    return (
        'Normal',
        'No predefined red flag keywords detected.'
    )


# DEPARTMENT SELECTION
def get_department(symptoms):

    symptoms = symptoms.lower()

    if any(word in symptoms for word in [
        'chest pain', 'heart', 'palpitation'
    ]):
        return 'Cardiology'

    elif any(word in symptoms for word in [
        'cough', 'breathing', 'breathlessness',
        'asthma', 'lungs'
    ]):
        return 'Respiratory Medicine'

    elif any(word in symptoms for word in [
        'stomach', 'abdomen', 'vomiting',
        'diarrhea', 'digestion'
    ]):
        return 'General Medicine'

    return 'General Medicine'


# FIND DOCTOR BASED ON SPECIALIZATION AND WORKLOAD
def assign_doctor(conn, system, department):

    if system == 'modern':

        specialization_map = {
            'Cardiology': 'Cardiologist',
            'Respiratory Medicine': 'Pulmonologist',
            'General Medicine': 'General Physician'
        }

        required_specialization = specialization_map.get(department)

    else:
        required_specialization = 'Ayurvedic General Physician'

    if not required_specialization:
        return None

    doctors = conn.execute('''
        SELECT id
        FROM users
        WHERE system = ?
        AND role = 'doctor'
        AND specialization = ?
    ''', (
        system,
        required_specialization
    )).fetchall()

    if not doctors:
        return None

    doctor_workload = []

    for doctor in doctors:

        pending_count = conn.execute('''
            SELECT COUNT(*) AS total
            FROM patient_cases
            WHERE assigned_doctor_id = ?
            AND system = ?
            AND status = 'Pending'
        ''', (
            doctor['id'],
            system
        )).fetchone()['total']

        doctor_workload.append(
            (doctor['id'], pending_count)
        )

    doctor_workload.sort(key=lambda x: x[1])

    return doctor_workload[0][0]


# PATIENT AND DOCTOR LOGIN
@app.route('/<system>/<role>', methods=['GET', 'POST'])
def user_login(system, role):

    if system not in ['modern', 'ayurveda'] or role not in ['patient', 'doctor']:
        abort(404)

    system_name = 'Modern Medicine' if system == 'modern' else 'Ayurveda'
    role_name = role.capitalize()

    if request.method == 'POST':

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_db_connection()

        user = conn.execute(
            '''SELECT * FROM users
               WHERE email = ? AND system = ? AND role = ?''',
            (email, system, role)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user['password'], password):

            session['user_id'] = user['id']
            session['name'] = user['name']
            session['system'] = system
            session['role'] = role

            return redirect(url_for('dashboard'))

        return render_template(
            'auth.html',
            system=system_name,
            role=role_name,
            error='Invalid email or password!'
        )

    return render_template(
        'auth.html',
        system=system_name,
        role=role_name
    )


# DASHBOARD
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('home'))

    system_name = (
        'Modern Medicine'
        if session['system'] == 'modern'
        else 'Ayurveda'
    )

    total_cases = 0
    pending_cases = 0
    completed_cases = 0

    journey_interview = False
    journey_red_flag = False
    journey_summary = False
    journey_doctor = False

    conn = get_db_connection()

    if session.get('role') == 'doctor':

        total_cases = conn.execute('''
            SELECT COUNT(*) AS total
            FROM patient_cases
            WHERE assigned_doctor_id = ?
            AND system = ?
        ''', (
            session['user_id'],
            session['system']
        )).fetchone()['total']

        pending_cases = conn.execute('''
            SELECT COUNT(*) AS total
            FROM patient_cases
            WHERE assigned_doctor_id = ?
            AND system = ?
            AND status = 'Pending'
        ''', (
            session['user_id'],
            session['system']
        )).fetchone()['total']

        completed_cases = conn.execute('''
            SELECT COUNT(*) AS total
            FROM patient_cases
            WHERE assigned_doctor_id = ?
            AND system = ?
            AND status = 'Completed'
        ''', (
            session['user_id'],
            session['system']
        )).fetchone()['total']

    elif session.get('role') == 'patient':

        total_cases = conn.execute('''
            SELECT COUNT(*) AS total
            FROM patient_cases
            WHERE patient_id = ? AND system = ?
        ''', (
            session['user_id'],
            session['system']
        )).fetchone()['total']

        latest_case = conn.execute('''
            SELECT id, assigned_doctor_id
            FROM patient_cases
            WHERE patient_id = ? AND system = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        ''', (
            session['user_id'],
            session['system']
        )).fetchone()

        if latest_case:

            journey_interview = True
            journey_red_flag = True
            journey_summary = True

            journey_doctor = (
                latest_case['assigned_doctor_id'] is not None
            )

    conn.close()

    return render_template(
        'dashboard.html',
        name=session['name'],
        system=system_name,
        role=session['role'].capitalize(),
        total_cases=total_cases,
        pending_cases=pending_cases,
        completed_cases=completed_cases,
        journey_interview=journey_interview,
        journey_red_flag=journey_red_flag,
        journey_summary=journey_summary,
        journey_doctor=journey_doctor
    )


# DOCTOR PROFILE
@app.route('/doctor/profile')
def doctor_profile():

    if 'user_id' not in session:
        return redirect(url_for('home'))

    if session.get('role') != 'doctor':
        abort(403)

    conn = get_db_connection()

    doctor = conn.execute('''
        SELECT name, age, gender, email, mobile,
               system, role, specialization
        FROM users
        WHERE id = ? AND system = ? AND role = 'doctor'
    ''', (
        session['user_id'],
        session['system']
    )).fetchone()

    if not doctor:
        conn.close()
        abort(404)

    total_cases = conn.execute('''
        SELECT COUNT(*) AS total
        FROM patient_cases
        WHERE assigned_doctor_id = ? AND system = ?
    ''', (
        session['user_id'],
        session['system']
    )).fetchone()['total']

    pending_cases = conn.execute('''
        SELECT COUNT(*) AS total
        FROM patient_cases
        WHERE assigned_doctor_id = ?
        AND system = ?
        AND status = 'Pending'
    ''', (
        session['user_id'],
        session['system']
    )).fetchone()['total']

    completed_cases = conn.execute('''
        SELECT COUNT(*) AS total
        FROM patient_cases
        WHERE assigned_doctor_id = ?
        AND system = ?
        AND status = 'Completed'
    ''', (
        session['user_id'],
        session['system']
    )).fetchone()['total']

    conn.close()

    return render_template(
        'doctor_profile.html',
        doctor=doctor,
        total_cases=total_cases,
        pending_cases=pending_cases,
        completed_cases=completed_cases
    )


# PATIENT PROFILE
@app.route('/patient/profile')
def patient_profile():

    if 'user_id' not in session:
        return redirect(url_for('home'))

    if session.get('role') != 'patient':
        abort(403)

    conn = get_db_connection()

    patient = conn.execute('''
        SELECT name, age, gender, email, mobile, system, role
        FROM users
        WHERE id = ? AND system = ? AND role = 'patient'
    ''', (
        session['user_id'],
        session['system']
    )).fetchone()

    if not patient:
        conn.close()
        abort(404)

    total_cases = conn.execute('''
        SELECT COUNT(*) AS total
        FROM patient_cases
        WHERE patient_id = ? AND system = ?
    ''', (
        session['user_id'],
        session['system']
    )).fetchone()['total']

    conn.close()

    return render_template(
        'patient_profile.html',
        patient=patient,
        total_cases=total_cases
    )


# PATIENT INTERVIEW
@app.route('/interview', methods=['GET', 'POST'])
def interview():

    if 'user_id' not in session:
        return redirect(url_for('home'))

    if session.get('role') != 'patient':
        abort(403)

    if request.method == 'GET':

        session['interview_answers'] = {}

        session['interview_messages'] = [
            {
                'sender': 'bot',
                'text': 'Hello! I will ask you a few questions to understand your health concern. What symptoms or health problems are you experiencing?'
            }
        ]

        session['interview_questions'] = []
        session['interview_step'] = 0

    else:

        answer = request.form.get('answer', '').strip()

        if not answer:
            return redirect(url_for('interview'))

        messages = session.get('interview_messages', [])
        answers = session.get('interview_answers', {})
        questions = session.get('interview_questions', [])
        step = session.get('interview_step', 0)

        messages.append({
            'sender': 'patient',
            'text': answer
        })

        answers[str(step)] = answer

        if step == 0:

            symptoms = answer.lower()

            if 'headache' in symptoms or 'head pain' in symptoms:
                questions = [
                    'Where exactly do you feel the headache?',
                    'Are you experiencing vomiting, blurred vision, fever or neck stiffness?'
                ]

            elif 'fever' in symptoms:
                questions = [
                    'Have you measured your body temperature? If yes, what was it?',
                    'Are you experiencing chills, headache, rash or vomiting?'
                ]

            elif 'cough' in symptoms:
                questions = [
                    'Is your cough dry or are you coughing up mucus?',
                    'Are you experiencing breathlessness or chest pain?'
                ]

            elif 'stomach' in symptoms or 'abdominal' in symptoms:
                questions = [
                    'Where exactly are you feeling the stomach pain?',
                    'Are you experiencing vomiting, diarrhoea or nausea?'
                ]

            else:
                questions = [
                    'Where exactly are you experiencing this problem?',
                    'Are you experiencing any other symptoms along with it?'
                ]

            questions.extend([
                'How long have you been experiencing these symptoms? (Example: 2 days, 1 week)',
                'How severe are your symptoms? Please answer Mild, Moderate or Severe.'
            ])

            session['interview_questions'] = questions

        step += 1

        session['interview_step'] = step
        session['interview_answers'] = answers
        session['interview_messages'] = messages

        if step <= len(questions):

            messages.append({
                'sender': 'bot',
                'text': questions[step - 1]
            })

            session['interview_messages'] = messages

        else:

            messages.append({
                'sender': 'bot',
                'text': 'Thank you! Your interview is complete. Please review your answers in the Health Assessment Form and add your remaining medical details.'
            })

            session['interview_messages'] = messages

            return redirect(url_for('assessment'))

    messages = session.get('interview_messages', [])
    step = session.get('interview_step', 0)

    return render_template(
        'interview.html',
        messages=messages,
        question_number=min(step + 1, 5),
        total_questions=5
    )


# PATIENT HEALTH ASSESSMENT
@app.route('/assessment', methods=['GET', 'POST'])
def assessment():

    if 'user_id' not in session:
        return redirect(url_for('home'))

    if session.get('role') != 'patient':
        abort(403)

    system_name = (
        'Modern Medicine'
        if session['system'] == 'modern'
        else 'Ayurveda'
    )

    interview_answers = session.get('interview_answers', {})

    followup_one = interview_answers.get('1', '')
    followup_two = interview_answers.get('2', '')

    followup_notes = ""

    if followup_one:
        followup_notes += "Follow-up Answer 1: " + followup_one

    if followup_two:
        if followup_notes:
            followup_notes += "\n"

        followup_notes += "Follow-up Answer 2: " + followup_two

    if request.method == 'POST':

        symptoms = request.form.get('symptoms', '').strip()
        duration = request.form.get('duration', '').strip()
        severity = request.form.get('severity', '').strip()
        medical_history = request.form.get('medical_history', '').strip()
        current_medications = request.form.get('current_medications', '').strip()
        allergies = request.form.get('allergies', '').strip()
        additional_notes = request.form.get('additional_notes', '').strip()

        if not symptoms or not duration or not severity:

            return render_template(
                'assessment.html',
                system=system_name,
                error='Please fill all required fields!',
                interview_answers=interview_answers,
                followup_notes=followup_notes
            )

        red_flag_level, red_flag_details = detect_red_flags(
            symptoms, severity
        )

        department = get_department(symptoms)

        conn = get_db_connection()

        doctor_id = assign_doctor(
            conn,
            session['system'],
            department
        )

        conn.execute('''
            INSERT INTO patient_cases
            (patient_id, system, symptoms, duration, severity,
             medical_history, current_medications, allergies,
             additional_notes, red_flag_level, red_flag_details,
             assigned_doctor_id, department)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            session['system'],
            symptoms,
            duration,
            severity,
            medical_history,
            current_medications,
            allergies,
            additional_notes,
            red_flag_level,
            red_flag_details,
            doctor_id,
            department
        ))

        conn.commit()
        conn.close()

        session.pop('interview_answers', None)
        session.pop('interview_messages', None)
        session.pop('interview_questions', None)
        session.pop('interview_step', None)

        success_message = 'Your health assessment has been submitted successfully!'

        if doctor_id:
            success_message += ' Your case has been assigned to a matching specialist.'
        else:
            success_message += ' No matching specialist is registered yet. Your case is currently unassigned.'

        return render_template(
            'assessment.html',
            system=system_name,
            success=success_message
        )

    return render_template(
        'assessment.html',
        system=system_name,
        interview_answers=interview_answers,
        followup_notes=followup_notes
    )


# PATIENT - VIEW OWN CASE HISTORY
@app.route('/patient/history')
def patient_history():

    if 'user_id' not in session:
        return redirect(url_for('home'))

    if session.get('role') != 'patient':
        abort(403)

    conn = get_db_connection()

    cases = conn.execute('''
        SELECT
            patient_cases.*,
            users.name AS assigned_doctor_name,
            users.specialization AS assigned_doctor_specialization
        FROM patient_cases
        LEFT JOIN users
        ON patient_cases.assigned_doctor_id = users.id
        WHERE patient_cases.patient_id = ? AND patient_cases.system = ?
        ORDER BY patient_cases.created_at DESC
    ''', (
        session['user_id'],
        session['system']
    )).fetchall()

    conn.close()

    system_name = (
        'Modern Medicine'
        if session['system'] == 'modern'
        else 'Ayurveda'
    )

    return render_template(
        'patient_history.html',
        cases=cases,
        system=system_name
    )


# DOCTOR - VIEW ASSIGNED PATIENT CASES
@app.route('/doctor/cases')
def doctor_cases():

    if 'user_id' not in session:
        return redirect(url_for('home'))

    if session.get('role') != 'doctor':
        abort(403)

    conn = get_db_connection()

    cases = conn.execute('''
        SELECT
            patient_cases.*,
            users.name AS patient_name,
            users.age AS patient_age,
            users.gender AS patient_gender
        FROM patient_cases
        JOIN users ON patient_cases.patient_id = users.id
        WHERE patient_cases.system = ?
        AND (
            patient_cases.assigned_doctor_id = ?
            OR patient_cases.assigned_doctor_id IS NULL
        )
        ORDER BY patient_cases.created_at DESC
    ''', (
        session['system'],
        session['user_id']
    )).fetchall()

    conn.close()

    system_name = (
        'Modern Medicine'
        if session['system'] == 'modern'
        else 'Ayurveda'
    )

    return render_template(
        'doctor_cases.html',
        cases=cases,
        system=system_name
    )


# DOCTOR - UPDATE CASE STATUS AND NOTES
@app.route('/doctor/case/<int:case_id>/update', methods=['POST'])
def update_doctor_case(case_id):

    if 'user_id' not in session:
        return redirect(url_for('home'))

    if session.get('role') != 'doctor':
        abort(403)

    new_status = request.form.get('status', '').strip()
    doctor_notes = request.form.get('doctor_notes', '').strip()

    allowed_statuses = ['Pending', 'Reviewed', 'Completed']

    if new_status not in allowed_statuses:
        abort(400)

    conn = get_db_connection()

    case = conn.execute('''
        SELECT id FROM patient_cases
        WHERE id = ? AND system = ?
        AND (
            assigned_doctor_id = ?
            OR assigned_doctor_id IS NULL
        )
    ''', (
        case_id,
        session['system'],
        session['user_id']
    )).fetchone()

    if not case:
        conn.close()
        abort(404)

    conn.execute('''
        UPDATE patient_cases
        SET status = ?, doctor_notes = ?
        WHERE id = ? AND system = ?
        AND (
            assigned_doctor_id = ?
            OR assigned_doctor_id IS NULL
        )
    ''', (
        new_status,
        doctor_notes,
        case_id,
        session['system'],
        session['user_id']
    ))

    conn.commit()
    conn.close()

    flash('Patient case updated successfully!', 'success')

    return redirect(url_for('doctor_cases'))


# LOGOUT
@app.route('/logout')
def logout():

    session.clear()
    return redirect(url_for('home'))


# REGISTRATION
@app.route('/<system>/<role>/register', methods=['GET', 'POST'])
def register(system, role):

    if system not in ['modern', 'ayurveda'] or role not in ['patient', 'doctor']:
        abort(404)

    system_name = 'Modern Medicine' if system == 'modern' else 'Ayurveda'
    role_name = role.capitalize()

    if request.method == 'POST':

        name = request.form.get('name', '').strip()
        age = request.form.get('age', '')
        email = request.form.get('email', '').strip().lower()
        mobile = request.form.get('mobile', '').strip()
        gender = request.form.get('gender', '')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        specialization = ''

        if role == 'doctor':
            specialization = request.form.get('specialization', '').strip()

            allowed_specializations = {
                'modern': [
                    'Cardiologist',
                    'Pulmonologist',
                    'General Physician'
                ],
                'ayurveda': [
                    'Ayurvedic General Physician',
                    'Kayachikitsa Specialist',
                    'Panchakarma Specialist'
                ]
            }

            if specialization not in allowed_specializations[system]:
                return render_template(
                    'register.html',
                    system=system_name,
                    role=role_name,
                    error='Please select a valid specialization!'
                )

        if not all([name, age, email, mobile, gender, password, confirm_password]):

            return render_template(
                'register.html',
                system=system_name,
                role=role_name,
                error='Please fill all the fields!'
            )

        if not age.isdigit() or not 1 <= int(age) <= 120:

            return render_template(
                'register.html',
                system=system_name,
                role=role_name,
                error='Please enter a valid age!'
            )

        if len(password) < 6:

            return render_template(
                'register.html',
                system=system_name,
                role=role_name,
                error='Password must contain at least 6 characters!'
            )

        if password != confirm_password:

            return render_template(
                'register.html',
                system=system_name,
                role=role_name,
                error='Passwords do not match!'
            )

        conn = get_db_connection()

        existing_user = conn.execute(
            '''SELECT id FROM users
               WHERE email = ? AND system = ? AND role = ?''',
            (email, system, role)
        ).fetchone()

        if existing_user:

            conn.close()

            return render_template(
                'register.html',
                system=system_name,
                role=role_name,
                error='Account already exists with this email!'
            )

        hashed_password = generate_password_hash(password)

        conn.execute('''
            INSERT INTO users
            (name, age, email, mobile, gender, password,
             system, role, specialization)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name,
            int(age),
            email,
            mobile,
            gender,
            hashed_password,
            system,
            role,
            specialization
        ))

        conn.commit()
        conn.close()

        return redirect(
            url_for('user_login', system=system, role=role)
        )

    return render_template(
        'register.html',
        system=system_name,
        role=role_name
    )


# START APPLICATION
if __name__ == '__main__':
    create_tables()
    app.run(debug=True)
