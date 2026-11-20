
import sqlite3

def get_db_connection():
    conn = sqlite3.connect('medikiosk.db')
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():

    conn = get_db_connection()

    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            email TEXT NOT NULL,
            mobile TEXT NOT NULL,
            gender TEXT NOT NULL,
            password TEXT NOT NULL,
            system TEXT NOT NULL,
            role TEXT NOT NULL,
            specialization TEXT DEFAULT ''
        )
    ''')

    conn.execute('''
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
    ''')

    # Check existing users columns
    user_columns = [
        row['name']
        for row in conn.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if 'specialization' not in user_columns:
        conn.execute("""
            ALTER TABLE users
            ADD COLUMN specialization TEXT DEFAULT ''
        """)

    # Check existing patient_cases columns
    case_columns = [
        row['name']
        for row in conn.execute(
            "PRAGMA table_info(patient_cases)"
        ).fetchall()
    ]

    if 'red_flag_level' not in case_columns:
        conn.execute("""
            ALTER TABLE patient_cases
            ADD COLUMN red_flag_level TEXT DEFAULT 'Normal'
        """)

    if 'red_flag_details' not in case_columns:
        conn.execute("""
            ALTER TABLE patient_cases
            ADD COLUMN red_flag_details TEXT DEFAULT 'No red flags detected'
        """)

    if 'doctor_notes' not in case_columns:
        conn.execute("""
            ALTER TABLE patient_cases
            ADD COLUMN doctor_notes TEXT DEFAULT ''
        """)

    if 'assigned_doctor_id' not in case_columns:
        conn.execute("""
            ALTER TABLE patient_cases
            ADD COLUMN assigned_doctor_id INTEGER
        """)

    if 'department' not in case_columns:
        conn.execute("""
            ALTER TABLE patient_cases
            ADD COLUMN department TEXT DEFAULT 'General Medicine'
        """)

    conn.commit()
    conn.close()


if __name__ == '__main__':
    create_tables()
    print("Database and tables updated successfully!")





