
import os
import sqlite3
import uuid

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, send_from_directory, abort
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from database import create_tables, get_db_connection
from red_flags import detect_red_flags


app = Flask(__name__)
app.secret_key = "medikiosk_secret_key"

UPLOAD_FOLDER = os.path.join(app.root_path, "uploads")
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_FILE_SIZE = 10 * 1024 * 1024

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

create_tables()


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# SmartCare: simple symptom-to-specialization mapping
def get_department(symptom, system):
    if system == "ayurveda":
        if symptom in [
            "Headache", "Fever", "Cough or cold",
            "Stomach pain", "Body pain"
        ]:
            return "Ayurveda Physician"
        return None

    departments = {
        "Headache": "Neurologist",
        "Fever": "General Physician",
        "Cough or cold": "General Physician",
        "Stomach pain": "General Physician",
        "Body pain": "Orthopedic"
    }

    return departments.get(symptom)


# Find a matching doctor in the same medical system
def assign_doctor(conn, department, system):
    if not department:
        return None

    doctor = conn.execute("""
        SELECT id
        FROM users
        WHERE role = 'doctor'
        AND system = ?
        AND specialization = ?
        ORDER BY id ASC
        LIMIT 1
    """, (system, department)).fetchone()

    return doctor["id"] if doctor else None


@app.errorhandler(413)
def file_too_large(error):
    return "File is too large. Maximum allowed size is 10 MB.", 413


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/modern")
def modern():
    return render_template("system.html", system="Modern Medicine")


@app.route("/ayurveda")
def ayurveda():
    return render_template("system.html", system="Ayurveda")


@app.route("/<system>/<role>/register", methods=["GET", "POST"])
def register(system, role):
    if system not in ["modern", "ayurveda"] or role not in ["patient", "doctor"]:
        return "Invalid page", 404

    error = None
    success = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        age = request.form.get("age", "").strip()
        email = request.form.get("email", "").strip().lower()
        mobile = request.form.get("mobile", "").strip()
        gender = request.form.get("gender", "")
        password = request.form.get("password", "")

        specialization = ""
        qualification = ""
        hospital = ""

        if role == "doctor":
            specialization = request.form.get("specialization", "")
            qualification = request.form.get("qualification", "").strip()
            hospital = request.form.get("hospital", "").strip()

        if not name:
            error = "Please enter your name."
        elif not age.isdigit() or not (1 <= int(age) <= 120):
            error = "Please enter a valid age."
        elif len(mobile) != 10 or not mobile.isdigit():
            error = "Please enter a valid 10-digit mobile number."
        elif len(password) < 6:
            error = "Password must contain at least 6 characters."
        elif role == "doctor" and not specialization:
            error = "Please select your specialization."
        elif role == "doctor" and not qualification:
            error = "Please enter your qualification."
        else:
            conn = get_db_connection()
            try:
                conn.execute("""
                    INSERT INTO users
                    (name, age, email, mobile, gender, password,
                     system, role, specialization, qualification, hospital)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, int(age), email, mobile, gender,
                    generate_password_hash(password),
                    system, role, specialization, qualification, hospital
                ))
                conn.commit()
                success = "Your account has been created successfully!"
            except sqlite3.IntegrityError:
                error = "This email is already registered. Please use another email."
            finally:
                conn.close()

    system_name = "Modern Medicine" if system == "modern" else "Ayurveda"

    return render_template(
        "register.html",
        system=system_name,
        role=role,
        error=error,
        success=success
    )


@app.route("/<system>/<role>/login", methods=["GET", "POST"])
def login(system, role):
    if system not in ["modern", "ayurveda"] or role not in ["patient", "doctor"]:
        return "Invalid page", 404

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute("""
            SELECT * FROM users
            WHERE email = ? AND system = ? AND role = ?
        """, (email, system, role)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]
            session["user_system"] = user["system"]

            if role == "patient":
                return redirect(url_for("patient_dashboard"))

            return redirect(url_for("doctor_dashboard"))

        error = "Invalid email or password. Please try again."

    system_name = "Modern Medicine" if system == "modern" else "Ayurveda"

    return render_template(
        "login.html",
        system=system_name,
        role=role,
        error=error
    )


# Patient Dashboard
@app.route("/patient/dashboard")
def patient_dashboard():
    if "user_id" not in session or session.get("user_role") != "patient":
        return redirect(url_for("home"))

    conn = get_db_connection()

    cases = conn.execute("""
        SELECT
            patient_cases.*,
            EXISTS (
                SELECT 1
                FROM medical_reports
                WHERE medical_reports.case_id = patient_cases.id
            ) AS has_reports,
            doctors.name AS doctor_name,
            doctors.specialization AS doctor_specialization,
            doctors.qualification AS doctor_qualification,
            doctors.hospital AS doctor_hospital
        FROM patient_cases
        LEFT JOIN users AS doctors
            ON patient_cases.assigned_doctor_id = doctors.id
        WHERE patient_cases.patient_id = ?
        ORDER BY patient_cases.created_at DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "patient_dashboard.html",
        name=session.get("user_name"),
        system="Modern Medicine" if session.get("user_system") == "modern" else "Ayurveda",
        cases=cases
    )


@app.route("/patient/interview")
def patient_interview():
    if "user_id" not in session or session.get("user_role") != "patient":
        return redirect(url_for("home"))

    return render_template(
        "interview.html",
        name=session.get("user_name"),
        system="Modern Medicine" if session.get("user_system") == "modern" else "Ayurveda"
    )


@app.route("/patient/interview/save", methods=["POST"])
def save_interview():
    if "user_id" not in session or session.get("user_role") != "patient":
        return jsonify({"success": False, "message": "Please login first."}), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not isinstance(data.get("answers"), dict):
        return jsonify({"success": False, "message": "Invalid interview data."}), 400

    answers = data["answers"]

    symptoms = str(answers.get("symptom", "")).strip()
    duration = str(answers.get("duration", "")).strip()
    severity = str(answers.get("severity", "")).strip()

    if not symptoms or not duration or not severity:
        return jsonify({
            "success": False,
            "message": "Please complete the required interview questions."
        }), 400

    allowed_keys = {
        "symptom", "duration", "severity",
        "associated", "temperature", "cough_type", "stomach_details"
    }

    red_flag_result = detect_red_flags(answers)
    system = session["user_system"]

    department = get_department(symptoms, system)

    conn = get_db_connection()

    try:
        assigned_doctor_id = assign_doctor(
            conn, department, system
        )

        cursor = conn.execute("""
            INSERT INTO patient_cases
            (patient_id, system, symptoms, duration, severity,
             red_flag_level, red_flag_details,
             assigned_doctor_id, department)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            system,
            symptoms,
            duration,
            severity,
            red_flag_result["level"],
            red_flag_result["details"],
            assigned_doctor_id,
            department or "General Review"
        ))

        case_id = cursor.lastrowid

        for key, value in answers.items():
            if key in allowed_keys and isinstance(value, str) and value.strip():
                conn.execute("""
                    INSERT INTO interview_responses
                    (case_id, question_key, answer)
                    VALUES (?, ?, ?)
                """, (case_id, key, value.strip()))

        conn.commit()

        if assigned_doctor_id:
            assignment_message = "A matching doctor has been assigned."
        else:
            assignment_message = "No matching doctor is currently registered. Your case is unassigned."

        return jsonify({
            "success": True,
            "message": "Your assessment has been saved successfully!",
            "case_id": case_id,
            "red_flag_level": red_flag_result["level"],
            "red_flag_details": red_flag_result["details"],
            "department": department or "General Review",
            "doctor_assigned": assigned_doctor_id is not None,
            "assignment_message": assignment_message
        })

    except sqlite3.Error:
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Something went wrong while saving your assessment."
        }), 500
    finally:
        conn.close()


# Patient Report Upload
@app.route("/patient/case/<int:case_id>/upload", methods=["POST"])
def upload_report(case_id):
    if "user_id" not in session or session.get("user_role") != "patient":
        return redirect(url_for("home"))

    file = request.files.get("report")

    if not file or file.filename == "":
        return "Please select a report to upload.", 400

    if not allowed_file(file.filename):
        return "Only PDF, JPG, JPEG and PNG files are allowed.", 400

    original_name = secure_filename(file.filename)

    if not original_name:
        return "Invalid filename.", 400

    extension = original_name.rsplit(".", 1)[1].lower()
    stored_name = f"{uuid.uuid4().hex}.{extension}"

    conn = get_db_connection()

    case = conn.execute("""
        SELECT id FROM patient_cases
        WHERE id = ? AND patient_id = ?
    """, (case_id, session["user_id"])).fetchone()

    if case is None:
        conn.close()
        return "Assessment not found.", 404

    try:
        file.save(os.path.join(UPLOAD_FOLDER, stored_name))

        conn.execute("""
            INSERT INTO medical_reports
            (case_id, patient_id, file_name, file_path)
            VALUES (?, ?, ?, ?)
        """, (
            case_id,
            session["user_id"],
            original_name,
            stored_name
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        saved_path = os.path.join(UPLOAD_FOLDER, stored_name)

        if os.path.exists(saved_path):
            os.remove(saved_path)

        conn.close()
        return "Could not upload the report. Please try again.", 500

    conn.close()

    return redirect(url_for("patient_dashboard"))


# View Uploaded Report
@app.route("/report/<int:report_id>")
def view_report(report_id):
    if "user_id" not in session:
        return redirect(url_for("home"))

    conn = get_db_connection()

    report = conn.execute("""
        SELECT
            medical_reports.*,
            patient_cases.system
        FROM medical_reports
        JOIN patient_cases ON medical_reports.case_id = patient_cases.id
        WHERE medical_reports.id = ?
    """, (report_id,)).fetchone()

    conn.close()

    if report is None:
        return "Report not found.", 404

    if session.get("user_role") == "patient":
        if report["patient_id"] != session.get("user_id"):
            abort(403)

    elif session.get("user_role") == "doctor":
        if report["system"] != session.get("user_system"):
            abort(403)

    else:
        abort(403)

    return send_from_directory(
        UPLOAD_FOLDER,
        report["file_path"],
        as_attachment=False,
        download_name=report["file_name"]
    )


# Doctor Dashboard: only assigned cases
@app.route("/doctor/dashboard")
def doctor_dashboard():
    if "user_id" not in session or session.get("user_role") != "doctor":
        return redirect(url_for("home"))

    doctor_id = session["user_id"]
    doctor_system = session.get("user_system")

    conn = get_db_connection()

    total_cases = conn.execute("""
        SELECT COUNT(*) FROM patient_cases
        WHERE assigned_doctor_id = ? AND system = ?
    """, (doctor_id, doctor_system)).fetchone()[0]

    pending_cases = conn.execute("""
        SELECT COUNT(*) FROM patient_cases
        WHERE assigned_doctor_id = ?
        AND system = ? AND status = 'Pending'
    """, (doctor_id, doctor_system)).fetchone()[0]

    red_flag_cases = conn.execute("""
        SELECT COUNT(*) FROM patient_cases
        WHERE assigned_doctor_id = ?
        AND system = ? AND red_flag_level = 'Needs Review'
    """, (doctor_id, doctor_system)).fetchone()[0]

    cases = conn.execute("""
        SELECT
            patient_cases.id,
            patient_cases.symptoms,
            patient_cases.duration,
            patient_cases.severity,
            patient_cases.status,
            patient_cases.red_flag_level,
            patient_cases.created_at,
            patient_cases.department,
            users.name AS patient_name,
            users.age AS patient_age,
            users.gender AS patient_gender
        FROM patient_cases
        JOIN users ON patient_cases.patient_id = users.id
        WHERE patient_cases.assigned_doctor_id = ?
        AND patient_cases.system = ?
        ORDER BY patient_cases.created_at DESC
    """, (doctor_id, doctor_system)).fetchall()

    conn.close()

    system_name = "Modern Medicine" if doctor_system == "modern" else "Ayurveda"

    return render_template(
        "doctor_dashboard.html",
        name=session.get("user_name"),
        system=system_name,
        total_cases=total_cases,
        pending_cases=pending_cases,
        red_flag_cases=red_flag_cases,
        cases=cases
    )


# Doctor Case Details
@app.route("/doctor/case/<int:case_id>", methods=["GET", "POST"])
def doctor_case_details(case_id):
    if "user_id" not in session or session.get("user_role") != "doctor":
        return redirect(url_for("home"))

    conn = get_db_connection()

    case = conn.execute("""
        SELECT
            patient_cases.*,
            users.name AS patient_name,
            users.age AS patient_age,
            users.gender AS patient_gender
        FROM patient_cases
        JOIN users ON patient_cases.patient_id = users.id
        WHERE patient_cases.id = ?
        AND patient_cases.system = ?
        AND patient_cases.assigned_doctor_id = ?
    """, (
        case_id,
        session.get("user_system"),
        session.get("user_id")
    )).fetchone()

    if case is None:
        conn.close()
        return "Patient case not found or not assigned to you.", 404

    if request.method == "POST":
        doctor_notes = request.form.get("doctor_notes", "").strip()
        status = request.form.get("status", "Pending")

        allowed_statuses = ["Pending", "Under Review", "Reviewed"]

        if status not in allowed_statuses:
            conn.close()
            return "Invalid case status.", 400

        conn.execute("""
            UPDATE patient_cases
            SET doctor_notes = ?, status = ?
            WHERE id = ?
            AND system = ?
            AND assigned_doctor_id = ?
        """, (
            doctor_notes,
            status,
            case_id,
            session.get("user_system"),
            session.get("user_id")
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("doctor_case_details", case_id=case_id))

    responses = conn.execute("""
        SELECT question_key, answer
        FROM interview_responses
        WHERE case_id = ?
        ORDER BY id
    """, (case_id,)).fetchall()

    reports = conn.execute("""
        SELECT id, file_name, uploaded_at
        FROM medical_reports
        WHERE case_id = ?
        ORDER BY uploaded_at DESC
    """, (case_id,)).fetchall()

    conn.close()

    return render_template(
        "case_details.html",
        case=case,
        responses=responses,
        reports=reports
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
