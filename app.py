from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_mysqldb import MySQL
import MySQLdb.cursors
import os
from datetime import datetime, time, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'abineshpower007'
app.config['MYSQL_DB'] = 'hospital_db'

mysql = MySQL(app)

# Initialize database
def init_db():
    try:
        cursor = mysql.connection.cursor()
        # Create patients table
        cursor.execute('''CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        )''')
        # Create doctors table
        cursor.execute('''CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            specialty VARCHAR(100) NOT NULL
        )''')
        # Create appointments table
        cursor.execute('''CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            patient_id INTEGER,
            doctor_id INTEGER,
            appointment_date DATE NOT NULL,
            appointment_time TIME,
            treatment_details TEXT,
            diagnosis TEXT,
            fees DECIMAL(10,2),
            status VARCHAR(50) DEFAULT 'Scheduled',
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )''')
        # Create availability_slots table with date range and recurrence
        cursor.execute('''CREATE TABLE IF NOT EXISTS availability_slots (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            doctor_id INTEGER,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            is_recurring BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )''')
        # Insert sample doctors
        sample_doctors = [
            ('Dr. John Doe', 'john.doe@example.com', 'password123', 'Cardiology'),
            ('Dr. Jane Smith', 'jane.smith@example.com', 'password123', 'Pediatrics'),
            ('Dr. Alice Brown', 'alice.brown@example.com', 'password123', 'Neurology')
        ]
        for doctor in sample_doctors:
            cursor.execute('SELECT * FROM doctors WHERE email = %s', (doctor[1],))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO doctors (name, email, password, specialty) VALUES (%s, %s, %s, %s)', doctor)
        mysql.connection.commit()
        cursor.close()
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise

# Home route
@app.route('/')
def home():
    return render_template('index.html')

# Combined Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form['role']
        email = request.form['email']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        if role == 'patient':
            cursor.execute('SELECT * FROM patients WHERE email = %s AND password = %s', (email, password))
            user = cursor.fetchone()
            if user:
                session['patient_id'] = user['id']
                cursor.close()
                return redirect(url_for('patient_dashboard'))
        elif role == 'doctor':
            cursor.execute('SELECT * FROM doctors WHERE email = %s AND password = %s', (email, password))
            user = cursor.fetchone()
            if user:
                session['doctor_id'] = user['id']
                cursor.close()
                return redirect(url_for('doctor_dashboard'))
        
        cursor.close()
        return render_template('login.html', error='Invalid credentials or role')
    return render_template('login.html')

# Patient Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM patients WHERE email = %s', [email])
        existing_patient = cursor.fetchone()
        if existing_patient:
            cursor.close()
            return render_template('register.html', error='Email already registered')
        cursor.execute('INSERT INTO patients (name, email, password) VALUES (%s, %s, %s)', (name, email, password))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('login'))
    return render_template('register.html')

# Doctor Registration
@app.route('/doctor_register', methods=['GET', 'POST'])
def doctor_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        specialty = request.form['specialty']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM doctors WHERE email = %s', [email])
        existing_doctor = cursor.fetchone()
        if existing_doctor:
            cursor.close()
            return render_template('doctor_register.html', error='Email already registered')
        cursor.execute('INSERT INTO doctors (name, email, password, specialty) VALUES (%s, %s, %s, %s)', 
                       (name, email, password, specialty))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('login'))
    return render_template('doctor_register.html')

# Patient Edit Profile
@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'patient_id' not in session:
        return redirect(url_for('login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM patients WHERE id = %s', [session['patient_id']])
    patient = cursor.fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        
        cursor.execute('SELECT * FROM patients WHERE email = %s AND id != %s', (email, session['patient_id']))
        existing_patient = cursor.fetchone()
        if existing_patient:
            cursor.close()
            return render_template('edit_profile.html', patient=patient, error='Email already registered')
        
        cursor.execute('UPDATE patients SET name = %s, email = %s, password = %s WHERE id = %s', 
                       (name, email, password, session['patient_id']))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('patient_dashboard'))
    
    cursor.close()
    return render_template('edit_profile.html', patient=patient)

# Patient Dashboard
@app.route('/patient_dashboard')
def patient_dashboard():
    if 'patient_id' not in session:
        return redirect(url_for('login'))
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM patients WHERE id = %s', [session['patient_id']])
    patient = cursor.fetchone()
    cursor.execute('SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.treatment_details, d.name AS doctor_name FROM appointments a JOIN doctors d ON a.doctor_id = d.id WHERE a.patient_id = %s', [session['patient_id']])
    appointments = cursor.fetchall()
    cursor.close()
    return render_template('patient_dashboard.html', patient=patient, appointments=appointments)

# Doctor Dashboard
@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'doctor_id' not in session:
        return redirect(url_for('login'))
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM doctors WHERE id = %s', [session['doctor_id']])
    doctor = cursor.fetchone()
    cursor.execute('SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.treatment_details, p.name AS patient_name FROM appointments a JOIN patients p ON a.patient_id = p.id WHERE a.doctor_id = %s', [session['doctor_id']])
    appointments = cursor.fetchall()
    cursor.execute('SELECT start_date, end_date, start_time, end_time, is_recurring FROM availability_slots WHERE doctor_id = %s ORDER BY start_date, start_time', [session['doctor_id']])
    availability = cursor.fetchall()
    cursor.close()
    return render_template('doctor_dashboard.html', doctor=doctor, appointments=appointments, availability=availability)

# Book Appointment
@app.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'patient_id' not in session:
        return redirect(url_for('login'))
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        appointment_date = request.form['appointment_date']
        appointment_time = request.form['appointment_time']
        treatment_details = request.form['treatment_details']
        
        # Validate appointment time against availability
        cursor.execute('''SELECT start_time, end_time FROM availability_slots 
                          WHERE doctor_id = %s 
                          AND (
                              (start_date <= %s AND end_date >= %s)
                              OR (is_recurring = TRUE)
                          )''', (doctor_id, appointment_date, appointment_date))
        availability = cursor.fetchone()
        if not availability:
            cursor.execute('SELECT id, name, specialty FROM doctors')
            doctors = cursor.fetchall()
            cursor.close()
            return render_template('book_appointment.html', doctors=doctors, error='Doctor not available on selected date')
        
        start_time = datetime.strptime(str(availability['start_time']), '%H:%M:%S').time()
        end_time = datetime.strptime(str(availability['end_time']), '%H:%M:%S').time()
        selected_time = datetime.strptime(appointment_time, '%H:%M').time()
        
        if not (start_time <= selected_time <= end_time):
            cursor.execute('SELECT id, name, specialty FROM doctors')
            doctors = cursor.fetchall()
            cursor.close()
            return render_template('book_appointment.html', doctors=doctors, error='Selected time is outside doctor\'s availability')
        
        # Check for conflicting appointments
        cursor.execute('SELECT * FROM appointments WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s', 
                       (doctor_id, appointment_date, appointment_time))
        if cursor.fetchone():
            cursor.execute('SELECT id, name, specialty FROM doctors')
            doctors = cursor.fetchall()
            cursor.close()
            return render_template('book_appointment.html', doctors=doctors, error='Time slot already booked')
        
        cursor.execute('INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, status, treatment_details) VALUES (%s, %s, %s, %s, %s, %s)', 
                       (session['patient_id'], doctor_id, appointment_date, appointment_time, 'Scheduled', treatment_details))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('patient_dashboard'))
    
    cursor.execute('SELECT id, name, specialty FROM doctors')
    doctors = cursor.fetchall()
    
    # Pass appointment_date to fetch available time slots
    appointment_date = request.args.get('appointment_date')
    available_slots = []
    if appointment_date and request.args.get('doctor_id'):
        doctor_id = request.args.get('doctor_id')
        cursor.execute('''SELECT start_time, end_time FROM availability_slots 
                          WHERE doctor_id = %s 
                          AND (
                              (start_date <= %s AND end_date >= %s)
                              OR (is_recurring = TRUE)
                          )''', (doctor_id, appointment_date, appointment_date))
        availability = cursor.fetchone()
        if availability:
            start = datetime.strptime(str(availability['start_time']), '%H:%M:%S')
            end = datetime.strptime(str(availability['end_time']), '%H:%M:%S')
            current = start
            while current < end:
                slot = current.strftime('%H:%M')
                cursor.execute('SELECT * FROM appointments WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s', 
                               (doctor_id, appointment_date, slot))
                if not cursor.fetchone():
                    available_slots.append(slot)
                current += timedelta(minutes=30)
    
    cursor.close()
    return render_template('book_appointment.html', doctors=doctors, available_slots=available_slots, selected_date=appointment_date)

# Doctor Availability
@app.route('/doctor_availability', methods=['GET', 'POST'])
def doctor_availability():
    if 'doctor_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        is_recurring = 'is_recurring' in request.form
        
        # Validate dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        if end_dt < start_dt:
            return render_template('doctor_availability.html', error='End date cannot be before start date')
        
        # Validate times
        start_tm = datetime.strptime(start_time, '%H:%M').time()
        end_tm = datetime.strptime(end_time, '%H:%M').time()
        if end_tm <= start_tm:
            return render_template('doctor_availability.html', error='End time must be after start time')
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Check for overlapping availability
        cursor.execute('''SELECT * FROM availability_slots 
                          WHERE doctor_id = %s 
                          AND (
                              (start_date <= %s AND end_date >= %s)
                              OR (start_date <= %s AND end_date >= %s)
                              OR (is_recurring = TRUE)
                          )
                          AND ((start_time <= %s AND end_time > %s) OR (start_time < %s AND end_time >= %s))''', 
                       (session['doctor_id'], end_date, start_date, end_date, start_date, start_time, start_time, end_time, end_time))
        if cursor.fetchone():
            cursor.close()
            return render_template('doctor_availability.html', error='Overlapping availability slot')
        
        cursor.execute('INSERT INTO availability_slots (doctor_id, start_date, end_date, start_time, end_time, is_recurring) VALUES (%s, %s, %s, %s, %s, %s)', 
                       (session['doctor_id'], start_date, end_date, start_time, end_time, is_recurring))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('doctor_dashboard'))
    
    return render_template('doctor_availability.html')

# Download Invoice
@app.route('/download_invoice/<int:appointment_id>')
def download_invoice(appointment_id):
    if 'patient_id' not in session:
        return redirect(url_for('login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT a.id, a.appointment_date, a.appointment_time, a.diagnosis, a.fees, a.treatment_details, p.name AS patient_name, d.name AS doctor_name FROM appointments a JOIN patients p ON a.patient_id = p.id JOIN doctors d ON a.doctor_id = d.id WHERE a.id = %s AND a.patient_id = %s', 
                   (appointment_id, session['patient_id']))
    appointment = cursor.fetchone()
    cursor.close()
    
    if not appointment:
        return "Appointment not found or unauthorized", 404

    # Generate PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, "Hospital Invoice")
    p.drawString(100, 730, f"Patient: {appointment['patient_name']}")
    p.drawString(100, 710, f"Doctor: {appointment['doctor_name']}")
    p.drawString(100, 690, f"Date: {appointment['appointment_date']}")
    p.drawString(100, 670, f"Time: {appointment['appointment_time'] or 'N/A'}")
    p.drawString(100, 650, f"Treatment Details: {appointment['treatment_details'] or 'N/A'}")
    p.drawString(100, 630, f"Diagnosis: {appointment['diagnosis'] or 'N/A'}")
    p.drawString(100, 610, f"Fees: ${appointment['fees'] or '0.00'}")
    p.showPage()
    p.save()
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name=f"invoice_{appointment_id}.pdf", mimetype='application/pdf')

# Logout
@app.route('/logout')
def logout():
    session.pop('patient_id', None)
    session.pop('doctor_id', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)