from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
import sqlite3, os, random
import qrcode
import io
import base64
from PIL import Image
app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_NAME = "database.db"
trainer_profile = {
    "trainer_id": "TR12345",
    "expertise": ["Sprint Coach", "Strength Trainer", "Endurance Coach", "Yoga Instructor"],
    "experience": "10 yrs"
}

upcoming = [
    {"athlete_id": "AT12345", "date": "2025-08-20, 08:00 AM", "session": "Sprint Training"},
    {"athlete_id": "AT67890", "date": "2025-08-22, 05:00 PM", "session": "Strength Session"}
]

history = [
    {"athlete_id": "AT11111", "date": "2025-07-30, 07:00 AM", "session": "Yoga Training"},
    {"athlete_id": "AT22222", "date": "2025-07-25, 06:00 PM", "session": "Endurance Training"}
]

# ---------------- DATABASE ---------------- #
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL,
                    govt_id TEXT NOT NULL
                )''')

    # Athlete profiles
    c.execute('''CREATE TABLE IF NOT EXISTS athlete_profiles (
                    athlete_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    sport TEXT,
                    level TEXT,
                    blood_group TEXT,
                    emergency_contact TEXT,
                    medical_notes TEXT,
                    photo TEXT,   -- NEW COLUMN
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )''')

    # Medical records
    c.execute('''CREATE TABLE IF NOT EXISTS medical_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    athlete_id TEXT,
                    date TEXT,
                    description TEXT,
                    doctor TEXT,
                    FOREIGN KEY(athlete_id) REFERENCES athlete_profiles(athlete_id)
                )''')

    # Doctor appointments (with status)
    c.execute('''CREATE TABLE IF NOT EXISTS doctor_appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    athlete_id TEXT,
                    date TEXT,
                    doctor TEXT,
                    notes TEXT,
                    status TEXT DEFAULT 'Pending',
                    FOREIGN KEY(athlete_id) REFERENCES athlete_profiles(athlete_id)
                )''')

    # Trainer appointments (with status)
    c.execute('''CREATE TABLE IF NOT EXISTS trainer_appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    athlete_id TEXT,
                    date TEXT,
                    trainer TEXT,
                    session TEXT,
                    status TEXT DEFAULT 'Pending',
                    FOREIGN KEY(athlete_id) REFERENCES athlete_profiles(athlete_id)
                )''')

    # Achievements
    c.execute('''CREATE TABLE IF NOT EXISTS achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    athlete_id TEXT,
                    year TEXT,
                    title TEXT,
                    FOREIGN KEY(athlete_id) REFERENCES athlete_profiles(athlete_id)
                )''')

    conn.commit()
    conn.close()

init_db()


# ---------------- AUTH ---------------- #
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        govt_id = request.form["govt_id"]

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (name,email,password,role,govt_id) VALUES (?,?,?,?,?)",
                      (name,email,password,role,govt_id))
            user_id = c.lastrowid

            if role == "Athlete":
                athlete_id = f"AT{random.randint(10000,99999)}"
                c.execute("INSERT INTO athlete_profiles (athlete_id,user_id,sport,level,blood_group,emergency_contact,medical_notes) VALUES (?,?,?,?,?,?,?)",
                          (athlete_id,user_id,None,None,None,None,None))

            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already exists!", "danger")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form["email"]
        password=request.form["password"]
        conn=sqlite3.connect(DB_NAME)
        c=conn.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND password=?",(email,password))
        user=c.fetchone()
        conn.close()
        if user:
            session["user_id"]=user[0]
            session["name"]=user[1]
            session["role"]=user[4]
            flash("Login successful!","success")
            if session["role"]=="Athlete":
                return redirect(url_for("athlete_dashboard"))
            elif session["role"]=="Trainer":
                return redirect(url_for("trainer_dashboard"))
            elif session["role"]=="Doctor":
                return redirect(url_for("doctor_dashboard"))
            else:
                flash("Unknown role!","danger")
                return redirect(url_for("login"))
        else:
            flash("Invalid email or password","danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.","info")
    return redirect(url_for("home"))

@app.route("/")
def home():
    return render_template("index.html")

# ---------------- ATHLETE DASHBOARD ---------------- #
@app.route("/athlete_dashboard")
def athlete_dashboard():
    if "user_id" not in session or session["role"]!="Athlete":
        flash("Unauthorized access!","danger")
        return redirect(url_for("login"))

    conn=sqlite3.connect(DB_NAME)
    c=conn.cursor()

    # Fetch user
    c.execute("SELECT id,name,email FROM users WHERE id=?",(session["user_id"],))
    user_row=c.fetchone()

    # Fetch profile
    c.execute("SELECT athlete_id,sport,level,blood_group,emergency_contact,medical_notes FROM athlete_profiles WHERE user_id=?",(session["user_id"],))
    profile_row=c.fetchone()
    athlete_id = profile_row[0] if profile_row else None

    # Fetch medical records
    medical_records=[]
    if athlete_id:
        c.execute("SELECT date,description,doctor FROM medical_records WHERE athlete_id=?",(athlete_id,))
        medical_records=[{"date":r[0],"description":r[1],"doctor":r[2]} for r in c.fetchall()]

    # Fetch doctor appointments
    doctor_appointments=[]
    if athlete_id:
        c.execute("SELECT date,doctor,notes FROM doctor_appointments WHERE athlete_id=?",(athlete_id,))
        doctor_appointments=[{"date":r[0],"doctor":r[1],"notes":r[2]} for r in c.fetchall()]

    # Fetch trainer appointments
    trainer_appointments=[]
    if athlete_id:
        c.execute("SELECT date,trainer,session FROM trainer_appointments WHERE athlete_id=?",(athlete_id,))
        trainer_appointments=[{"date":r[0],"trainer":r[1],"session":r[2]} for r in c.fetchall()]

    # Fetch achievements
    achievements=[]
    if athlete_id:
        c.execute("SELECT year,title FROM achievements WHERE athlete_id=?",(athlete_id,))
        achievements=[{"year":r[0],"title":r[1]} for r in c.fetchall()]

    conn.close()

    user={"id":user_row[0],"name":user_row[1],"email":user_row[2]} if user_row else None
    profile=None
    if profile_row:
        profile={
            "athlete_id":profile_row[0],
            "sport":profile_row[1],
            "level":profile_row[2],
            "blood_group":profile_row[3],
            "emergency_contact":profile_row[4],
            "medical_notes":profile_row[5]
        }

    return render_template("athlete_dash.html",
                           user=user,
                           profile=profile,
                           medical_records=medical_records,
                           doctor_appointments=doctor_appointments,
                           trainer_appointments=trainer_appointments,
                           achievements=achievements)
import qrcode
import io
import base64
from flask import send_file, render_template, redirect, url_for, flash, request
import sqlite3
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from textwrap import wrap

IDCARD_SIZE = (85.6*mm, 54*mm)  # Standard credit card size

@app.route("/view_id_card/<athlete_id>")
def view_id_card(athlete_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT u.name,u.email,p.sport,p.level,p.photo FROM users u JOIN athlete_profiles p ON u.id=p.user_id WHERE p.athlete_id=?",(athlete_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        flash("Athlete not found","danger")
        return redirect(url_for("athlete_dashboard"))

    name,email,sport,level,photo=row

    # Generate QR Code (points to athlete profile link)
    qr_data = f"{request.host_url}athlete/{athlete_id}"
    qr_img = qrcode.make(qr_data)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    qr_img_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    return render_template("id_card.html",
                           athlete_id=athlete_id,
                           name=name,email=email,
                           sport=sport,level=level,
                           photo=photo,
                           qr_img=qr_img_b64)



@app.route("/download_id_card/<athlete_id>")
def download_id_card(athlete_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT u.name, u.email, p.sport, p.level 
        FROM users u 
        JOIN athlete_profiles p ON u.id = p.user_id 
        WHERE p.athlete_id = ?
    """, (athlete_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        flash("Athlete not found", "danger")
        return redirect(url_for("athlete_dashboard"))

    name, email, sport, level = row

    # Generate QR Code
    qr_data = f"{request.host_url}athlete/{athlete_id}"
    qr_img = qrcode.make(qr_data)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    # Create PDF
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=IDCARD_SIZE)

    # Card border
    border_margin = 5 * mm
    c.roundRect(border_margin, border_margin, 75*mm, 44*mm, 4*mm)

    # Inner margins
    margin_x = 8 * mm
    margin_y = 8 * mm

    # Title
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin_x, 46*mm, "Athlete ID Card")

    # Profile Picture (use sample if real one not available)
    try:
        pfp = ImageReader("static/pfp.jpg")  # sample picture
        c.drawImage(pfp, margin_x, 28*mm, 15*mm, 15*mm, mask='auto')
    except:
        pass

    # Details
    c.setFont("Helvetica", 8.5)
    c.drawString(28*mm, 42*mm, f"ID: {athlete_id}")
    c.drawString(28*mm, 37*mm, f"Name: {name}")
    c.drawString(28*mm, 32*mm, f"Sport: {sport if sport else 'N/A'}")
    c.drawString(28*mm, 27*mm, f"Level: {level if level else 'N/A'}")

    # Email (wrap if too long)
    email_lines = wrap("Email: " + email, 30)
    y = 22*mm
    for line in email_lines:
        c.drawString(margin_x, y, line)
        y -= 4*mm

    # QR Code — slightly smaller and moved inward
    qr_reader = ImageReader(qr_buf)
    c.drawImage(qr_reader, 55*mm, 15*mm, 22*mm, 22*mm)

    c.showPage()
    c.save()
    pdf_buf.seek(0)

    return send_file(
        pdf_buf,
        as_attachment=True,
        download_name=f"athlete_{athlete_id}_idcard.pdf",
        mimetype="application/pdf"
    )


@app.route("/athlete/<athlete_id>")
def athlete_profile(athlete_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT u.name, u.email, p.sport, p.level
        FROM users u
        JOIN athlete_profiles p ON u.id = p.user_id
        WHERE p.athlete_id = ?
    """, (athlete_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        abort(404)

    name, email, sport, level = row

    # Generate QR Code as base64 for web display
    qr_data = f"{request.host_url}athlete/{athlete_id}"
    qr_img = qrcode.make(qr_data)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format='PNG')
    qr_base64 = base64.b64encode(qr_buf.getvalue()).decode("ascii")

    return render_template("athlete_profile.html",
                           athlete_id=athlete_id,
                           name=name,
                           email=email,
                           sport=sport,
                           level=level,
                           qr_base64=qr_base64)


# ---------------- UPDATE PROFILE ---------------- #
@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "user_id" not in session or session["role"]!="Athlete":
        flash("Unauthorized access!","danger")
        return redirect(url_for("login"))

    athlete_id=request.form.get("athlete_id")
    sport=request.form.get("sport")
    level=request.form.get("level")
    blood_group=request.form.get("blood_group")
    emergency_contact=request.form.get("emergency_contact")
    medical_notes=request.form.get("medical_notes")

    updates=[]
    params=[]
    if sport:
        updates.append("sport=?"); params.append(sport)
    if level:
        updates.append("level=?"); params.append(level)
    if blood_group:
        updates.append("blood_group=?"); params.append(blood_group)
    if emergency_contact:
        updates.append("emergency_contact=?"); params.append(emergency_contact)
    if medical_notes:
        updates.append("medical_notes=?"); params.append(medical_notes)

    if updates:
        params.append(athlete_id)
        query=f"UPDATE athlete_profiles SET {','.join(updates)} WHERE athlete_id=?"
        conn=sqlite3.connect(DB_NAME)
        c=conn.cursor()
        c.execute(query,params)
        conn.commit()
        conn.close()
        flash("Profile updated!","success")
    else:
        flash("No updates provided.","info")

    return redirect(url_for("athlete_dashboard"))

@app.route("/update_trainer_profile", methods=["POST"])
def update_trainer_profile():
    if "user_id" not in session or session["role"] != "Trainer":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    expertise = request.form.get("expertise")
    experience = request.form.get("experience")

    # For demo we just store in session (since trainer_profiles table isn’t defined)
    session["expertise"] = expertise.split(",") if expertise else ["Sprint Coach"]
    session["experience"] = experience if experience else "10 yrs"

    flash("Trainer profile updated!", "success")
    return redirect(url_for("trainer_dashboard"))


# ---------------- RECORDS ---------------- #
@app.route("/add_medical_record", methods=["POST"])
def add_medical_record():
    if "user_id" not in session or session["role"]!="Athlete":
        flash("Unauthorized access!","danger")
        return redirect(url_for("login"))

    athlete_id=request.form.get("athlete_id")
    date=request.form.get("date")
    description=request.form.get("description")
    doctor=request.form.get("doctor")

    if not (date and description and doctor):
        flash("All fields required for medical record.","danger")
        return redirect(url_for("athlete_dashboard"))

    conn=sqlite3.connect(DB_NAME)
    c=conn.cursor()
    c.execute("INSERT INTO medical_records (athlete_id,date,description,doctor) VALUES (?,?,?,?)",
              (athlete_id,date,description,doctor))
    conn.commit()
    conn.close()
    flash("Medical record added!","success")
    return redirect(url_for("athlete_dashboard"))

# ---------------- ACHIEVEMENTS ---------------- #
@app.route("/add_achievement", methods=["POST"])
def add_achievement():
    if "user_id" not in session or session["role"]!="Athlete":
        flash("Unauthorized access!","danger")
        return redirect(url_for("login"))

    athlete_id=request.form.get("athlete_id")
    year=request.form.get("year")
    title=request.form.get("title")

    if not (year and title):
        flash("All fields required for achievement.","danger")
        return redirect(url_for("athlete_dashboard"))

    conn=sqlite3.connect(DB_NAME)
    c=conn.cursor()
    c.execute("INSERT INTO achievements (athlete_id,year,title) VALUES (?,?,?)",
              (athlete_id,year,title))
    conn.commit()
    conn.close()
    flash("Achievement added!","success")
    return redirect(url_for("athlete_dashboard"))

# ---------------- BOOK APPOINTMENT ---------------- #
@app.route("/book_appointment", methods=["POST"])
def book_appointment():
    if "user_id" not in session or session["role"] != "Athlete":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    athlete_id = request.form.get("athlete_id")
    role = request.form.get("role")  # Doctor or Trainer
    date = request.form.get("date")
    person = request.form.get("person")  # doctor/trainer name
    notes = request.form.get("notes")

    if not (date and person):
        flash("Date and name are required!", "danger")
        return redirect(url_for("athlete_dashboard"))

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if role == "Doctor":
        c.execute("INSERT INTO doctor_appointments (athlete_id,date,doctor,notes) VALUES (?,?,?,?)",
                  (athlete_id, date, person, notes))
    elif role == "Trainer":
        c.execute("INSERT INTO trainer_appointments (athlete_id,date,trainer,session) VALUES (?,?,?,?)",
                  (athlete_id, date, person, notes))
    conn.commit()
    conn.close()

    flash(f"Appointment booked with {role}!", "success")
    return redirect(url_for("athlete_dashboard"))

# ---------------- OTHER DASHBOARDS ---------------- #
@app.route("/trainer_dashboard")
def trainer_dashboard():
    if "user_id" not in session or session["role"] != "Trainer":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    trainer_profile = {
        "trainer_id": "TR12345",
        "expertise": ["Sprint Coach", "Strength Trainer", "Endurance Coach", "Yoga Instructor"],
        "experience": "10 yrs"
    }

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id,athlete_id,date,session,status FROM trainer_appointments ORDER BY date LIMIT 5")
    upcoming = [{"id": r[0], "athlete_id": r[1], "date": r[2], "session": r[3], "status": r[4]} for r in c.fetchall()]
    conn.close()

    # Hardcoded fallback data if DB is empty
    if not upcoming:
        upcoming = [
            {"id": 1, "athlete_id": "AT12345", "date": "20 Aug 2025, 8:00 AM", "session": "Sprint Training", "status": "Pending"},
            {"id": 2, "athlete_id": "AT67890", "date": "22 Aug 2025, 5:00 PM", "session": "Strength Training", "status": "Pending"},
            {"id": 3, "athlete_id": "AT54321", "date": "25 Aug 2025, 7:30 AM", "session": "Endurance Session", "status": "Pending"}
        ]

    history = upcoming[::-1]

    return render_template("trainer_dash.html",
                           name=session["name"],
                           profile=trainer_profile,
                           upcoming=upcoming,
                           history=history)


    return render_template("trainer_dash.html",
                           name=session["name"],
                           profile=trainer_profile,
                           upcoming=upcoming,
                           history=history)


@app.route("/doctor_dashboard")
def doctor_dashboard():
    if "user_id" not in session or session["role"] != "Doctor":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    doctor_profile = {
        "doctor_id": "DR45678",
        "specialization": ["Physiotherapist", "Orthopedic", "Sports Medicine", "Nutritionist"],
        "experience": "15 yrs"
    }

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Pending (upcoming)
    c.execute("SELECT id,athlete_id,date,notes,status FROM doctor_appointments WHERE status='Pending' ORDER BY date")
    upcoming = [{"id": r[0], "athlete_id": r[1], "date": r[2], "notes": r[3], "status": r[4]} for r in c.fetchall()]

    # History (approved or rejected)
    c.execute("SELECT id,athlete_id,date,notes,status FROM doctor_appointments WHERE status!='Pending' ORDER BY date DESC")
    history = [{"id": r[0], "athlete_id": r[1], "date": r[2], "notes": r[3], "status": r[4]} for r in c.fetchall()]

    conn.close()

    # Fallback sample data if empty
    if not upcoming and not history:
        upcoming = [
            {"id": 1, "athlete_id": "AT12345", "date": "15 Aug 2025, 10:00 AM", "notes": "Physiotherapy Session", "status": "Pending"},
            {"id": 2, "athlete_id": "AT67890", "date": "16 Aug 2025, 3:00 PM", "notes": "Consultation", "status": "Pending"}
        ]
        history = []

    return render_template("doctor_dash.html",
                           name=session["name"],
                           profile=doctor_profile,
                           upcoming=upcoming,
                           history=history)

@app.route("/update_appointment_status/<role>/<int:appt_id>/<string:action>")
def update_appointment_status(role, appt_id, action):
    if "user_id" not in session or session["role"] not in ["Trainer", "Doctor"]:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    status = "Approved" if action == "approve" else "Rejected"

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if role == "Trainer":
        c.execute("UPDATE trainer_appointments SET status=? WHERE id=?", (status, appt_id))
    elif role == "Doctor":
        c.execute("UPDATE doctor_appointments SET status=? WHERE id=?", (status, appt_id))

    conn.commit()
    conn.close()

    flash(f"Appointment {status}!", "success" if status == "Approved" else "danger")

    if role == "Trainer":
        return redirect(url_for("trainer_dashboard"))
    else:
        return redirect(url_for("doctor_dashboard"))

# ---------------- RUN ---------------- #
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))  # Default to 5000 for local dev
    app.run(host="0.0.0.0", port=port, debug=True)
