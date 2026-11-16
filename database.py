
import sqlite3

def get_db_connection():
    conn = sqlite3.connect("medikiosk.db")
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            email TEXT NOT NULL UNIQUE,
            mobile TEXT NOT NULL,
            gender TEXT NOT NULL,
            password TEXT NOT NULL,
            system TEXT NOT NULL,
            role TEXT NOT NULL,
            specialization TEXT DEFAULT '',
            qualification TEXT DEFAULT '',
            hospital TEXT DEFAULT ''
        )
    """)

    existing_columns = [
        row["name"] for row in conn.execute("PRAGMA table_info(users)")
    ]

    if "qualification" not in existing_columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN qualification TEXT DEFAULT ''"
        )

    if "hospital" not in existing_columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN hospital TEXT DEFAULT ''"
        )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS patient_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            system TEXT NOT NULL,
            symptoms TEXT NOT NULL,
            duration TEXT NOT NULL,
            severity TEXT NOT NULL,
            medical_history TEXT,
            current_medications TEXT,
            allergies TEXT,
            additional_notes TEXT,
            status TEXT DEFAULT 'Pending',
            red_flag_level TEXT DEFAULT 'Normal',
            red_flag_details TEXT DEFAULT 'No red flags detected',
            doctor_notes TEXT DEFAULT '',
            assigned_doctor_id INTEGER,
            department TEXT DEFAULT 'General Medicine',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS interview_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            question_key TEXT NOT NULL,
            answer TEXT NOT NULL,
            FOREIGN KEY (case_id) REFERENCES patient_cases(id)
        )
    """)

    # Store uploaded medical report details
    conn.execute("""
        CREATE TABLE IF NOT EXISTS medical_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES patient_cases(id),
            FOREIGN KEY (patient_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_tables()
    print("MediKiosk database created successfully!")
