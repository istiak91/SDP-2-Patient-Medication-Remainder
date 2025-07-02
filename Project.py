import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from PIL import Image, ImageTk
from datetime import datetime, timedelta
import time
import threading
from win10toast import ToastNotifier
import winsound
import bcrypt
import base64
import mysql.connector

COLORS = {
    "background": "#F8F9FA",
    "primary": "#007BFF",
    "accent": "#17A2B8",
    "success": "#28A745",
    "danger": "#DC3545",
    "text": "#343A40",
    "card_bg": "#FFFFFF",
    "card_shadow": "#E9ECEF"
}

FONTS = {
    "title": ("Poppins", 24, "bold"),
    "heading": ("Poppins", 18, "bold"),
    "subheading": ("Poppins", 14),
    "body": ("Segoe UI", 12),
    "button": ("Poppins", 12, "bold")
}

# Database connection
def connect_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="patient_reminder"
    )

# Tables
def setup_database():
    db = connect_db()
    cursor = db.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        full_name VARCHAR(255),
        email VARCHAR(255) UNIQUE,
        phone VARCHAR(20),
        password VARCHAR(255),
        age INT,
        gender VARCHAR(10)
    )
""")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            message TEXT,
            sent_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            name VARCHAR(255),
            phone VARCHAR(20),
            relationship VARCHAR(50),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            name VARCHAR(255),
            dosage VARCHAR(50),
            times VARCHAR(255),
            start_date DATE,
            end_date DATE,
            notes TEXT,
            stock INT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            medicine_id INT,
            reminder_time DATETIME,
            status ENUM('Pending', 'Taken', 'Missed') DEFAULT 'Pending',
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ambulance (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255),
        area VARCHAR(255),
        phone VARCHAR(50)
    )
""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255),
        education VARCHAR(255),
        department VARCHAR(255),
        chamber VARCHAR(255),
        chamber_time VARCHAR(255)
    )
""")
    cursor.execute("""
        UPDATE reminders SET status = 'Missed' 
        WHERE status = 'Pending' AND reminder_time < NOW()
    """)
    
    cursor.execute("SELECT COUNT(*) FROM ambulance")
    if cursor.fetchone()[0] == 0:
        ambulance_data = [
            ("Dhaka Medical College Ambulance", "Puran Dhaka", "01713-377104"),
            ("Square Hospital Ambulance", "Mirpur Road", "10616"),
            ("Apollo Hospitals Ambulance", "Bashundhara", "10678"),
            ("Popular Diagnostic Ambulance", "Dhanmondi", "01716-602626"),
            ("Ibn Sina Ambulance", "Dhanmondi", "01714-001122"),
            ("Labaid Ambulance", "Gulshan", "10666"),
            ("United Hospital Ambulance", "Gulshan", "01714-001122"),
            ("Al Helal Ambulance", "Mirpur", "01711-998877"),
            ("Anwar Khan Modern Hospital Ambulance", "Dhanmondi", "01730-222555"),
            ("Samorita Hospital Ambulance", "Panthapath", "01755-665544"),
            ("National Emergency Service", "Countrywide", "999")
        ]
        cursor.executemany("INSERT INTO ambulance (name, area, phone) VALUES (%s, %s, %s)", ambulance_data)

    cursor.execute("SELECT COUNT(*) FROM doctors")
    if cursor.fetchone()[0] == 0:
        doctors_data = [
            ("Dr. A.B.M. Abdullah", "FCPS, MD (Medicine)", "Medicine", "Popular Diagnostic Center, Dhanmondi", "4PM-9PM (Sat-Thu)"),
            ("Dr. Prof. A.K.M. Mosharraf Hossain", "MBBS, FCPS (Surgery)", "Surgery", "Bangabandhu Sheikh Mujib Medical University", "10AM-4PM (Sat-Wed)"),
            ("Dr. Syed Atiqul Haq", "FCPS (Medicine)", "Cardiology", "Ibn Sina Hospital, Dhanmondi", "5PM-9PM (Sat-Thu)"),
            ("Dr. Laila Arjumand Banu", "MBBS, DGO, MCPS", "Gynecology", "Labaid Specialized Hospital, Gulshan", "9AM-1PM (Sat-Wed)"),
            ("Dr. Md. Habibe Millat", "FRCS (UK)", "Cardiac Surgery", "Square Hospital, Mirpur Road", "3PM-8PM (Sat-Thu)"),
            ("Dr. M. Muin Uddin", "MBBS, MD (Neurology)", "Neurology", "National Institute of Neuroscience", "10AM-4PM (Sun-Thu)"),
            ("Dr. Kazi Shafiqul Halim", "MBBS, DDV (Dermatology)", "Dermatology", "Apollo Hospitals, Bashundhara", "4PM-9PM (Sat-Thu)"),
            ("Dr. Md. Abdul Wadud Chowdhury", "MBBS, FCPS (Child)", "Pediatrics", "Shishu Hospital, Sher-e-Bangla Nagar", "9AM-1PM (Sat-Wed)"),
            ("Dr. Farhana Dewan", "MBBS, FCPS (Medicine)", "Endocrinology", "BIRDEM Hospital, Shahbagh", "2PM-6PM (Sat-Thu)"),
            ("Dr. Md. Abdul Aziz", "BDS, FCPS (Dental Surgery)", "Dentistry", "Dhaka Dental College", "10AM-4PM (Sat-Wed)")
        ]
        cursor.executemany("""
            INSERT INTO doctors (name, education, department, chamber, chamber_time) 
            VALUES (%s, %s, %s, %s, %s)
        """, doctors_data)
    db.commit()
    db.close()

# Reminder Notification Thread
def reminder_thread(app_instance):
    while True:
        db = connect_db()
        cursor = db.cursor()
        now = datetime.now()
        next_minute = now + timedelta(minutes=1)
        
        cursor.execute("""
            SELECT r.id, m.name, r.reminder_time, m.times, m.dosage
            FROM reminders r
            JOIN medicines m ON r.medicine_id = m.id
            WHERE r.status = 'Pending' 
            AND r.reminder_time BETWEEN %s AND %s
        """, (now.strftime("%Y-%m-%d %H:%M:%S"), next_minute.strftime("%Y-%m-%d %H:%M:%S")))
        
        reminders = cursor.fetchall()
        
        for reminder in reminders:
            reminder_id, medicine_name, reminder_time, times_str, dosage = reminder
            
            # Use the app's notification method
            notification_msg = f"Medicine: {medicine_name}\nDosage: {dosage}"
            app_instance.root.after(0, lambda: app_instance.show_notification("Time to take your medicine", notification_msg))
            
            cursor.execute("UPDATE reminders SET status = 'Taken' WHERE id = %s", (reminder_id,))

            times = [t.strip() for t in times_str.split(",")]
            for time_str in times:
                time_obj = datetime.strptime(time_str, "%H:%M").time()
                next_reminder = datetime.combine(datetime.now().date() + timedelta(days=1), time_obj)
                cursor.execute("""
                    INSERT INTO reminders (medicine_id, reminder_time, status)
                    VALUES (%s, %s, 'Pending')
                """, (reminder_id, next_reminder.strftime("%Y-%m-%d %H:%M:%S")))
        
        db.commit()
        db.close()
        time.sleep(60)

# Main Application Class
class PatientMedicationReminderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MediNex")
        self.root.geometry("1000x700")
        self.root.configure(bg=COLORS["background"])
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TButton', 
                        font=FONTS["button"],
                        padding=6,
                        background=COLORS["primary"],
                        foreground="white")
        self.style.map('TButton',
                  background=[('active', COLORS["accent"])])
    
        self.style.configure('TEntry', 
                        font=FONTS["body"],
                        padding=5)
    
        self.style.configure('TLabel',
                       font=FONTS["body"],
                       background=COLORS["background"])
    
        self.current_user = None
        self.toaster = ToastNotifier()
        self.notification_icon = "./Images/medicine.ico"

    def show_notification(self, title, message):
        """Thread-safe notification display"""
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        
            self.toaster.show_toast(
                title,
                message,
                icon_path=self.notification_icon,
                duration=10,
                threaded=True
            )
        except Exception as e:
            print(f"Notification error: {e}")
            self.root.after(0, lambda: messagebox.showinfo(title, message))

    def login_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        container = tk.Frame(self.root, bg="#f5f5f5")
        container.pack(expand=True, fill=tk.BOTH)

        left_frame = tk.Frame(container, bg="#ffffff", width=400)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
        try:
            image_path = "images/Patient.png"
            login_image = Image.open(image_path)
            login_image = login_image.resize((400, 500), Image.LANCZOS)
            self.login_photo = ImageTk.PhotoImage(login_image)
            image_label = tk.Label(left_frame, image=self.login_photo, bg="#ffffff")
            image_label.pack(expand=True, fill=tk.BOTH)
        except Exception as e:
            print(f"Error loading image: {e}")
            # Fallback if image fails to load
            tk.Label(left_frame, 
                    text="Medicine Reminder", 
                    font=("Poppins", 24, "bold"),
                    bg="#ffffff",
                    fg="#4CAF50").pack(expand=True)

        right_frame = tk.Frame(container, bg="#ffffff", padx=50, pady=80)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(right_frame, 
                text="Login", 
                font=("Poppins", 24, "bold"),
                bg="#ffffff",
                fg="#333333").pack(pady=(0, 40))

        tk.Label(right_frame, 
                text="Email or Phone", 
                font=("Poppins", 12),
                bg="#ffffff",
                fg="#555555").pack(anchor="w", pady=(0, 5))
    
        self.email_entry = ttk.Entry(right_frame, font=("Poppins", 12))
        self.email_entry.pack(fill=tk.X, pady=(0, 20))

        tk.Label(right_frame, 
                text="Password", 
                font=("Poppins", 12),
                bg="#ffffff",
                fg="#555555").pack(anchor="w", pady=(0, 5))
    
        self.password_entry = ttk.Entry(right_frame, show="*", font=("Poppins", 12))
        self.password_entry.pack(fill=tk.X, pady=(0, 10))

        login_btn = tk.Button(right_frame, 
                             text="Login",
                             command=self.login,
                             bg="#007BFF",
                             fg="white",
                             font=("Poppins", 12, "bold"),
                             bd=0,
                             padx=20,
                             pady=10,
                             width=15)
        login_btn.pack(pady=(10, 15))

        forgot_link = tk.Label(right_frame, 
                         text="Forgot password?",
                         font=("Poppins", 10, "underline"),
                         bg="#ffffff",
                         fg="#555555",
                         cursor="hand2")
        forgot_link.pack(pady=(0, 30))
        forgot_link.bind("<Button-1>", lambda e: self.forgot_password_screen())

        tk.Label(right_frame, 
                text="New here?",
                font=("Poppins", 10),
                bg="#ffffff",
                fg="#555555").pack(side=tk.LEFT, padx=(0, 5))
    
        register_link = tk.Label(right_frame, 
                               text="Register",
                               font=("Poppins", 10, "bold", "underline"),
                               bg="#ffffff",
                               fg="#007BFF",
                               cursor="hand2")
        register_link.pack(side=tk.LEFT)
        register_link.bind("<Button-1>", lambda e: self.register_screen())

        footer = tk.Frame(self.root, bg="#f5f5f5", padx=20, pady=10)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
    
        tk.Label(footer, 
                text="Patient Medication Reminder v2.0",
                font=("Poppins", 9),
                bg="#f5f5f5",
                fg="#777777").pack()

    def register_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        container = tk.Frame(self.root, bg=COLORS["background"])
        container.pack(expand=True, fill=tk.BOTH, padx=50, pady=50)

        card = tk.Frame(container, 
               bg=COLORS["card_bg"],
               padx=30, 
               pady=30,
               highlightbackground=COLORS["card_shadow"],
               highlightthickness=1)
        card.pack(expand=True)

        tk.Label(card, 
        text="Create Account", 
        font=FONTS["title"],
        bg=COLORS["card_bg"],
        fg=COLORS["text"]).pack(pady=(0, 20))

        form_frame = tk.Frame(card, bg=COLORS["card_bg"])
        form_frame.pack()

        fields = [
            ("Full Name", "full_name_entry"),
            ("Email", "reg_email_entry"),
            ("Phone", "phone_entry"),
            ("Password", "reg_password_entry"),
            ("Age", "age_entry"),
            ("Gender", "gender_var")
        ]

        for label_text, attr_name in fields:
            row_frame = tk.Frame(form_frame, bg=COLORS["card_bg"])
            row_frame.pack(fill=tk.X, pady=5)

            tk.Label(row_frame, 
            text=label_text, 
            font=FONTS["subheading"],
            bg=COLORS["card_bg"],
            fg=COLORS["text"],
            width=12, anchor="w").pack(side=tk.LEFT, padx=5)

            if label_text == "Gender":
                self.gender_var = tk.StringVar()
                gender_combo = ttk.Combobox(row_frame, 
                                     textvariable=self.gender_var,
                                     values=["Male", "Female", "Other"], 
                                     state="readonly",
                                     font=FONTS["body"],
                                     width=22)
                gender_combo.pack(side=tk.RIGHT, padx=5)
            else:
                entry = tk.Entry(row_frame, font=FONTS["body"], width=25, bg="white", fg="black", insertbackground="black")
                if label_text == "Password":
                    entry.config(show="*")
                entry.pack(side=tk.RIGHT, padx=5)
                setattr(self, attr_name, entry)

        button_frame = tk.Frame(card, bg=COLORS["card_bg"])
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, 
              text="Register", 
              command=self.register).pack(side=tk.LEFT, padx=5, ipadx=10)

        ttk.Button(button_frame, 
              text="Back to Login", 
              command=self.login_screen).pack(side=tk.RIGHT, padx=5, ipadx=10)

        tk.Label(container, 
        text="Patient Medication Reminder v2.0",
        font=("Segoe UI", 9),
        bg=COLORS["background"],
        fg="#6C757D").pack(side=tk.BOTTOM, pady=10)


    def login(self):
        email = self.email_entry.get()
        password = self.password_entry.get().encode('utf-8')

        db = connect_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        db.close()

        if user:
            stored_hashed_password = base64.b64decode(user[4])
        
            if bcrypt.checkpw(password, stored_hashed_password):
                self.current_user = user
                self.dashboard()
            else:
                messagebox.showerror("Error", "Invalid email or password")
        else:
            messagebox.showerror("Error", "Invalid email or password")
  
  
    def register(self):
        full_name = self.full_name_entry.get()
        email = self.reg_email_entry.get().strip()
        phone = self.phone_entry.get().replace(" ", "").replace("-", "")
        password = self.reg_password_entry.get().encode('utf-8')
        age = self.age_entry.get()
        gender = self.gender_var.get()

        if not self.validate_email(email):
            messagebox.showerror("Error", "Please enter a valid email address (e.g., user@example.com)")
            return

        valid_prefixes = ["017", "018", "019", "015", "014", "016", "013"]
        if (len(phone) != 11 or 
            not any(phone.startswith(prefix) for prefix in valid_prefixes) or 
            not phone.isdigit()):
            messagebox.showerror("Error", "Please enter a valid 11-digit phone number")
            return

        if len(password) < 8:
            messagebox.showerror("Error", "Password must be at least 8 characters long")
            return

        try:
            age = int(age)
            if age <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid age (positive number)")
            return

        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
        hashed_password_b64 = base64.b64encode(hashed_password).decode('utf-8')
    
        formatted_phone = f"+88{phone}"
    
        db = connect_db()
        cursor = db.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (full_name, email, phone, password, age, gender) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (full_name, email, formatted_phone, hashed_password_b64, age, gender))
            db.commit()
            messagebox.showinfo("Success", "Registration successful")
            self.login_screen()
        except mysql.connector.IntegrityError:
            messagebox.showerror("Error", "Email or phone number already exists")
        finally:
            db.close()


    def forgot_password_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        frame = tk.Frame(self.root, bg=COLORS["background"], padx=50, pady=50)
        frame.pack(expand=True, fill=tk.BOTH)

        card = tk.Frame(frame, bg=COLORS["card_bg"], padx=30, pady=30)
        card.pack(expand=True)

        tk.Label(card, text="Reset Password", font=FONTS["title"], bg=COLORS["card_bg"]).pack(pady=(0, 20))

        tk.Label(card, text="Enter your registered Email:", bg=COLORS["card_bg"], font=FONTS["body"]).pack(anchor="w")
        self.reset_email_entry = tk.Entry(card, font=FONTS["body"])
        self.reset_email_entry.pack(fill=tk.X, pady=5)

        tk.Label(card, text="Enter new Password:", bg=COLORS["card_bg"], font=FONTS["body"]).pack(anchor="w", pady=(10, 0))
        self.reset_password_entry = tk.Entry(card, show="*", font=FONTS["body"])
        self.reset_password_entry.pack(fill=tk.X, pady=5)

        tk.Button(card, text="Reset Password", command=self.reset_password, font=FONTS["button"],
                  bg=COLORS["primary"], fg="white").pack(pady=20)

        tk.Button(card, text="Back to Login", command=self.login_screen, font=FONTS["button"],
                  bg=COLORS["accent"], fg="white").pack()
        
    def reset_password(self):
        email = self.reset_email_entry.get().strip()
        new_password = self.reset_password_entry.get().strip()

        if not self.validate_email(email):
            messagebox.showerror("Error", "Enter a valid email address.")
            return

        if len(new_password) < 8:
            messagebox.showerror("Error", "Password must be at least 8 characters.")
            return

        hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
        hashed_b64 = base64.b64encode(hashed).decode()

        db = connect_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            messagebox.showerror("Error", "No account found with this email.")
            db.close()
            return

        cursor.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_b64, email))
        db.commit()
        db.close()
    
        messagebox.showinfo("Success", "Password has been reset. Please log in.")
        self.login_screen()


    def validate_email(self, email):
        """
        Enhanced email validation with regex pattern
        Validates email format according to RFC 5322 standard
        """
        import re
        pattern = r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
    
        if not email or '@' not in email or '.' not in email:
            return False
    
        if '..' in email or '@@' in email:
            return False
    
        parts = email.split('@')
        if len(parts) != 2:
            return False
    
        local_part, domain = parts
    
        if len(local_part) > 64 or len(domain) > 255:
            return False
    
        if '.' not in domain:
            return False
    
        tld = domain.split('.')[-1]
        if len(tld) < 2:
            return False
    
        return bool(re.fullmatch(pattern, email))

    def dashboard(self):
        for widget in self.root.winfo_children():
            widget.destroy()
    
        header = tk.Frame(self.root, bg=COLORS["primary"], padx=20, pady=15)
        header.pack(fill=tk.X)
    
        tk.Label(header, 
            text=f"Welcome, {self.current_user[1]}", 
            font=FONTS["heading"],
            bg=COLORS["primary"],
            fg="white").pack(side=tk.LEFT)
    
        profile_btn = ttk.Button(header, 
                       text="👤 Profile", 
                       command=self.show_profile_screen,
                       style="TButton")
        profile_btn.pack(side=tk.RIGHT, padx=5)
    
        self.main_content = tk.Frame(self.root, bg=COLORS["background"])
        self.main_content.pack(expand=True, fill=tk.BOTH)
        footer = tk.Frame(self.root, bg=COLORS["background"], padx=20, pady=10)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
    
        ttk.Button(footer, text="About Us", command=self.about_us).pack(side=tk.LEFT)
        ttk.Button(footer, text="Logout", command=self.logout).pack(side=tk.RIGHT)
    
        self.show_dashboard_buttons(self.main_content)

    def show_dashboard_buttons(self, parent_frame):
        for widget in parent_frame.winfo_children():
            widget.destroy()
    
        medicine_frame = tk.LabelFrame(parent_frame, 
                                text="Medicine Section", 
                                font=FONTS["subheading"],
                                bg=COLORS["card_bg"],
                                padx=10, pady=10)
        medicine_frame.pack(fill=tk.X, padx=10, pady=5)
    
        emergency_frame = tk.LabelFrame(parent_frame, 
                                 text="Emergency Contact Section", 
                                 font=FONTS["subheading"],
                                 bg=COLORS["card_bg"],
                                 padx=10, pady=10)
        emergency_frame.pack(fill=tk.X, padx=10, pady=5)
    
        other_frame = tk.LabelFrame(parent_frame, 
                             text="Other Services", 
                             font=FONTS["subheading"],
                             bg=COLORS["card_bg"],
                             padx=10, pady=10)
        other_frame.pack(fill=tk.X, padx=10, pady=5)


        medicine_buttons = [
            ("💊 Add Medicine", self.add_medicine_screen),
            ("📋 View Medicines", self.view_medicines_screen)
        ]
    
        for i, (text, command) in enumerate(medicine_buttons):
            btn = tk.Button(medicine_frame,
                     text=text,
                     command=command,
                     font=FONTS["button"],
                     bg=COLORS["card_bg"],
                     fg=COLORS["text"],
                     activebackground=COLORS["accent"],
                     activeforeground="white",
                     relief=tk.FLAT,
                     borderwidth=0,
                     padx=20,
                     pady=10)
            btn.grid(row=0, column=i, padx=5, pady=5, sticky="ew")  # Using grid for 2-column layout
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=COLORS["accent"], fg="white"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=COLORS["card_bg"], fg=COLORS["text"]))
    

        emergency_buttons = [
            ("🆘 Add Emergency", self.add_emergency_contact_screen),
            ("📞 View Contacts", self.view_emergency_contacts_screen)
        ]
    
        for i, (text, command) in enumerate(emergency_buttons):
            btn = tk.Button(emergency_frame,
                     text=text,
                     command=command,
                     font=FONTS["button"],
                     bg=COLORS["card_bg"],
                     fg=COLORS["text"],
                     activebackground=COLORS["accent"],
                     activeforeground="white",
                     relief=tk.FLAT,
                     borderwidth=0,
                     padx=20,
                     pady=10)
            btn.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=COLORS["accent"], fg="white"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=COLORS["card_bg"], fg=COLORS["text"]))
    

        other_buttons = [
            ("🚑 Ambulance", self.view_ambulance_screen),
            ("👨⚕ Doctors", self.view_doctor_screen),
            ("🏥 Hospital Ticket", self.hospital_ticket_screen)
        ]
    
        for i, (text, command) in enumerate(other_buttons):
            btn = tk.Button(other_frame,
                     text=text,
                     command=command,
                     font=FONTS["button"],
                     bg=COLORS["card_bg"],
                     fg=COLORS["text"],
                     activebackground=COLORS["accent"],
                     activeforeground="white",
                     relief=tk.FLAT,
                     borderwidth=0,
                     padx=20,
                     pady=10)
            
            if i < 2:
                btn.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            else:
                btn.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=COLORS["accent"], fg="white"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=COLORS["card_bg"], fg=COLORS["text"]))
    
        for frame in [medicine_frame, emergency_frame, other_frame]:
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_columnconfigure(1, weight=1)


    def show_profile_screen(self):
        for widget in self.root.winfo_children()[1:-1]:
            widget.destroy()

        container = tk.Frame(self.root, bg=COLORS["background"])
        container.pack(expand=True, fill=tk.BOTH, padx=50, pady=50)

        card = tk.Frame(container, 
           bg=COLORS["card_bg"],
           padx=30, 
           pady=30,
           highlightbackground=COLORS["card_shadow"],
           highlightthickness=1)
        card.pack(expand=True)

        header_frame = tk.Frame(card, bg=COLORS["card_bg"])
        header_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(header_frame, 
            text="Your Profile", 
            font=FONTS["title"],
            bg=COLORS["card_bg"],
            fg=COLORS["text"]).pack(side=tk.LEFT)

        ttk.Button(header_frame, 
              text="← Back", 
              command=self.dashboard).pack(side=tk.RIGHT)

        db = connect_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", (self.current_user[0],))
        user_data = cursor.fetchone()
        db.close()

        form_frame = tk.Frame(card, bg=COLORS["card_bg"])
        form_frame.pack()

        fields = [
            ("Full Name", "profile_name_entry", user_data[1]),
            ("Email", "profile_email_entry", user_data[2]),
            ("Phone", "profile_phone_entry", user_data[3]),
            ("Age", "profile_age_entry", user_data[5]),
            ("Gender", "profile_gender_var", user_data[6])
        ]

        self.profile_entries = {}
        self.edit_mode = False
    
        for label_text, attr_name, current_value in fields:
            row_frame = tk.Frame(form_frame, bg=COLORS["card_bg"])
            row_frame.pack(fill=tk.X, pady=5)

            tk.Label(row_frame, 
                text=label_text, 
                font=FONTS["subheading"],
                bg=COLORS["card_bg"],
                fg=COLORS["text"],
                width=25, anchor="w").pack(side=tk.LEFT, padx=5)

            if label_text == "Gender":
                self.profile_gender_var = tk.StringVar(value=current_value if current_value else "")
                gender_combo = ttk.Combobox(row_frame, 
                                 textvariable=self.profile_gender_var,
                                 values=["Male", "Female", "Other"], 
                                 state="readonly",
                                 font=FONTS["body"],
                                 width=22)
                gender_combo.pack(side=tk.RIGHT, padx=5)
                gender_combo.config(state="disabled")
            else:
                entry = tk.Entry(row_frame, font=FONTS["body"], width=25, bg="white", fg="black", insertbackground="black")
                entry.insert(0, current_value if current_value else "")
                entry.pack(side=tk.RIGHT, padx=5)
                entry.config(state="disabled") 
                setattr(self, attr_name, entry)
                self.profile_entries[attr_name] = entry

        password_frame = tk.Frame(form_frame, bg=COLORS["card_bg"])
        password_frame.pack(fill=tk.X, pady=5)

        tk.Label(password_frame, 
            text="New Password", 
            font=FONTS["subheading"],
            bg=COLORS["card_bg"],
            fg=COLORS["text"],
            width=25, anchor="w").pack(side=tk.LEFT, padx=5)

        self.profile_password_entry = tk.Entry(password_frame, show="*", font=FONTS["body"], width=25, bg="white", fg="black", insertbackground="black")
        self.profile_password_entry.pack(side=tk.RIGHT, padx=5)
        self.profile_password_entry.config(state="disabled")
        self.profile_entries["profile_password_entry"] = self.profile_password_entry
    
        button_frame = tk.Frame(card, bg=COLORS["card_bg"])
        button_frame.pack(fill=tk.X, pady=(20, 0))
    
        self.edit_save_button = ttk.Button(button_frame, 
                                text="Edit Profile", 
                                command=self.toggle_edit_mode)
        self.edit_save_button.pack(side=tk.RIGHT, padx=5, ipadx=10)

        self.update_button = ttk.Button(button_frame, 
                              text="Update Profile", 
                              command=self.update_profile)
        self.update_button.pack_forget()

        tk.Label(container, 
            text="Patient Medication Reminder v2.0",
            font=("Segoe UI", 9),
            bg=COLORS["background"],
            fg="#6C757D").pack(side=tk.BOTTOM, pady=10)

    def toggle_edit_mode(self):
        """Toggle between edit and view mode"""
        self.edit_mode = not self.edit_mode
    
        if self.edit_mode:
            self.edit_save_button.config(text="Cancel")
            self.update_button.pack(side=tk.RIGHT, padx=5, ipadx=10)  # Show update button
        
            for entry in self.profile_entries.values():
                entry.config(state="normal")
        
            for widget in self.root.winfo_children():
                if isinstance(widget, ttk.Combobox):
                    widget.config(state="readonly")
        else:
            self.edit_save_button.config(text="Edit Profile")
            self.update_button.pack_forget()
        
            for entry in self.profile_entries.values():
                entry.config(state="disabled")
        
            for widget in self.root.winfo_children():
                if isinstance(widget, ttk.Combobox):
                    widget.config(state="disabled")

    def update_profile(self):
        full_name = self.profile_name_entry.get()
        email = self.profile_email_entry.get()
        phone = self.profile_phone_entry.get()
        age = self.profile_age_entry.get()
        gender = self.profile_gender_var.get()
        new_password = self.profile_password_entry.get()

        try:
            age = int(age)
            if age <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid age (positive number)")
            return

        if not self.validate_email(email):
            messagebox.showerror("Error", "Please enter a valid email address")
            return

        if new_password and len(new_password) < 8:
            messagebox.showerror("Error", "Password must be at least 8 characters long")
            return

        db = connect_db()
        cursor = db.cursor()

        try:
            if new_password:
                hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute("""
                    UPDATE users 
                    SET full_name=%s, email=%s, phone=%s, age=%s, gender=%s, password=%s
                    WHERE id=%s
                """, (full_name, email, phone, age, gender, hashed_password, self.current_user[0]))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET full_name=%s, email=%s, phone=%s, age=%s, gender=%s
                    WHERE id=%s
                """, (full_name, email, phone, age, gender, self.current_user[0]))

            db.commit()
            messagebox.showinfo("Success", "Profile updated successfully")
    
            cursor.execute("SELECT * FROM users WHERE id = %s", (self.current_user[0],))
            self.current_user = cursor.fetchone()
    
            self.toggle_edit_mode()
        except mysql.connector.IntegrityError:
            messagebox.showerror("Error", "Email already exists")
        finally:
           db.close()
   
    def add_medicine_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        container = tk.Frame(self.root, bg=COLORS["background"])
        container.pack(expand=True, fill=tk.BOTH, padx=50, pady=50)

        card = tk.Frame(container, 
           bg=COLORS["card_bg"],
           padx=30, 
           pady=30,
           highlightbackground=COLORS["card_shadow"],
           highlightthickness=1)
        card.pack(expand=True)

        header_frame = tk.Frame(card, bg=COLORS["card_bg"])
        header_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(header_frame, 
            text="Add Medicine", 
            font=FONTS["title"],
            bg=COLORS["card_bg"],
            fg=COLORS["text"]).pack(side=tk.LEFT)

        ttk.Button(header_frame, 
              text="← Back", 
              command=self.dashboard).pack(side=tk.RIGHT)

        form_frame = tk.Frame(card, bg=COLORS["card_bg"])
        form_frame.pack()

        fields = [
            ("Medicine Name", "med_name_entry"),
            ("Dosage", "dosage_entry"),
            ("Times (HH:MM,HH:MM)", "times_entry"),
            ("Start Date (YYYY-MM-DD)", "start_date_entry"),
            ("End Date (YYYY-MM-DD)", "end_date_entry"),
            ("Notes", "notes_entry"),
            ("Stock Count", "stock_entry")
        ]

        for label_text, attr_name in fields:
            row_frame = tk.Frame(form_frame, bg=COLORS["card_bg"])
            row_frame.pack(fill=tk.X, pady=5)

            tk.Label(row_frame, 
                text=label_text, 
                font=FONTS["subheading"],
                bg=COLORS["card_bg"],
                fg=COLORS["text"],
                width=25, anchor="w").pack(side=tk.LEFT, padx=5)

            entry = tk.Entry(row_frame, font=FONTS["body"], width=25, bg="white", fg="black", insertbackground="black")
            entry.pack(side=tk.RIGHT, padx=5)
            setattr(self, attr_name, entry)

        button_frame = tk.Frame(card, bg=COLORS["card_bg"])
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, 
              text="Save Medicine", 
              command=self.save_medicine).pack(side=tk.RIGHT, padx=5, ipadx=10)

        tk.Label(container, 
            text="Patient Medication Reminder v2.0",
            font=("Segoe UI", 9),
            bg=COLORS["background"],
            fg="#6C757D").pack(side=tk.BOTTOM, pady=10)

    def save_medicine(self):
        name = self.med_name_entry.get()
        dosage = self.dosage_entry.get()
        times_str = self.times_entry.get()
        start_date = self.start_date_entry.get()
        end_date = self.end_date_entry.get()
        notes = self.notes_entry.get()
        stock = self.stock_entry.get()

        try:
            times = [t.strip() for t in times_str.split(",")]
            for t in times:
                datetime.strptime(t, "%H:%M")
        except ValueError:
            messagebox.showerror("Error", "Invalid time format. Please use HH:MM 24-hour format (e.g., 08:00,14:30,20:00)")
            return
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Please use YYYY-MM-DD format")
            return
        try:
            stock = int(stock)
            if stock < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Stock count must be a positive number")
            return

        db = connect_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO medicines (user_id, name, dosage, times, start_date, end_date, notes, stock)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (self.current_user[0], name, dosage, times_str, start_date, end_date, notes, stock))
    
        medicine_id = cursor.lastrowid
        for time_str in times:
            now = datetime.now()
            time_obj = datetime.strptime(time_str, "%H:%M").time()
            reminder_datetime = datetime.combine(now.date(), time_obj)
        
            if reminder_datetime < now:
                reminder_datetime += timedelta(days=1)
            
            cursor.execute("""
                INSERT INTO reminders (medicine_id, reminder_time, status)
                VALUES (%s, %s, 'Pending')
            """, (medicine_id, reminder_datetime.strftime("%Y-%m-%d %H:%M:%S")))
    
        db.commit()
        db.close()

        messagebox.showinfo("Success", "Medicine added successfully")
        self.dashboard()

    def view_medicines_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()
    
        header = tk.Frame(self.root, bg=COLORS["primary"], padx=20, pady=15)
        header.pack(fill=tk.X)
    
        tk.Label(header, text="Your Medicines", font=FONTS["heading"], bg=COLORS["primary"], fg="white").pack(side=tk.LEFT)
        ttk.Button(header, text="← Back", command=self.dashboard).pack(side=tk.RIGHT)
       
        main_frame = tk.Frame(self.root, bg=COLORS["background"], padx=20, pady=20)
        main_frame.pack(expand=True, fill=tk.BOTH)
    
        db = connect_db()
        cursor = db.cursor()
        cursor.execute("""
        SELECT name, dosage, times, start_date, end_date, notes, stock 
        FROM medicines 
        WHERE user_id = %s
    """, (self.current_user[0],))
        medicines = cursor.fetchall()
        db.close()
    
        style = ttk.Style()
        style.configure("Treeview.Heading", font=FONTS["subheading"], background=COLORS["primary"], foreground="white")
        style.configure("Treeview", font=FONTS["body"], rowheight=25)
    
        tree = ttk.Treeview(main_frame, columns=("name", "dosage", "times", "start", "end", "notes", "stock"), show="headings")
    
        tree.heading("name", text="Name")
        tree.heading("dosage", text="Dosage")
        tree.heading("times", text="Times")
        tree.heading("start", text="Start Date")
        tree.heading("end", text="End Date")
        tree.heading("notes", text="Notes")
        tree.heading("stock", text="Stock")
    
        for col in tree["columns"]:
            tree.column(col, width=120, anchor=tk.W)
    
        for med in medicines:
            tree.insert("", tk.END, values=med)
    
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(expand=True, fill=tk.BOTH)
        
    def add_emergency_contact_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        container = tk.Frame(self.root, bg=COLORS["background"])
        container.pack(expand=True, fill=tk.BOTH, padx=50, pady=50)

        card = tk.Frame(container, 
           bg=COLORS["card_bg"],
           padx=30, 
           pady=30,
           highlightbackground=COLORS["card_shadow"],
           highlightthickness=1)
        card.pack(expand=True)

        header_frame = tk.Frame(card, bg=COLORS["card_bg"])
        header_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(header_frame, 
            text="Add Emergency Contact", 
            font=FONTS["title"],
            bg=COLORS["card_bg"],
            fg=COLORS["text"]).pack(side=tk.LEFT)

        ttk.Button(header_frame, 
              text="← Back", 
              command=self.dashboard).pack(side=tk.RIGHT)

        form_frame = tk.Frame(card, bg=COLORS["card_bg"])
        form_frame.pack()
        fields = [
        ("Name", "emergency_name_entry"),
        ("Phone", "emergency_phone_entry"),
        ("Relationship", "emergency_relationship_entry")
        ]

        for label_text, attr_name in fields:
            row_frame = tk.Frame(form_frame, bg=COLORS["card_bg"])
            row_frame.pack(fill=tk.X, pady=5)

            tk.Label(row_frame, 
                text=label_text, 
                font=FONTS["subheading"],
                bg=COLORS["card_bg"],
                fg=COLORS["text"],
                width=25, anchor="w").pack(side=tk.LEFT, padx=5)
            
            entry = tk.Entry(row_frame, font=FONTS["body"], width=25, bg="white", fg="black", insertbackground="black")
            entry.pack(side=tk.RIGHT, padx=5)
            setattr(self, attr_name, entry)

        button_frame = tk.Frame(card, bg=COLORS["card_bg"])
        button_frame.pack(fill=tk.X, pady=(20, 0))
        ttk.Button(button_frame, 
              text="Save Contact", 
              command=self.save_emergency_contact).pack(side=tk.RIGHT, padx=5, ipadx=10)

        tk.Label(container, 
            text="Patient Medication Reminder v2.0",
            font=("Segoe UI", 9),
            bg=COLORS["background"],
            fg="#6C757D").pack(side=tk.BOTTOM, pady=10)

    def save_emergency_contact(self):
        name = self.emergency_name_entry.get()
        phone = self.emergency_phone_entry.get()
        relationship = self.emergency_relationship_entry.get()

        if not name or not phone or not relationship:
            messagebox.showerror("Error", "All fields are required")
            return

        db = connect_db()
        cursor = db.cursor()
        cursor.execute("""
        INSERT INTO emergency_contacts (user_id, name, phone, relationship)
        VALUES (%s, %s, %s, %s)
    """, (self.current_user[0], name, phone, relationship))
        db.commit()
        db.close()

        messagebox.showinfo("Success", "Emergency contact added successfully")
        self.dashboard()


    def view_emergency_contacts_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        header = tk.Frame(self.root, bg=COLORS["primary"], padx=20, pady=15)
        header.pack(fill=tk.X)

        tk.Label(header, 
            text="Your Emergency Contacts", 
            font=FONTS["heading"],
            bg=COLORS["primary"],
            fg="white").pack(side=tk.LEFT)
    
        ttk.Button(header, text="← Back", command=self.dashboard).pack(side=tk.RIGHT)

        main_frame = tk.Frame(self.root, bg=COLORS["background"], padx=20, pady=20)
        main_frame.pack(expand=True, fill=tk.BOTH)

        db = connect_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT name, phone, relationship 
            FROM emergency_contacts 
            WHERE user_id = %s
        """, (self.current_user[0],))
        contacts = cursor.fetchall()
        db.close()

        style = ttk.Style()
        style.configure("Treeview.Heading", 
                  font=FONTS["subheading"], 
                  background=COLORS["primary"], 
                  foreground="white")
        style.configure("Treeview", 
                  font=FONTS["body"], 
                  rowheight=25,
                  background=COLORS["card_bg"],
                  fieldbackground=COLORS["card_bg"])

        tree = ttk.Treeview(main_frame, 
                       columns=("Name", "Phone", "Relationship"), 
                       show="headings")

        tree.heading("Name", text="Name")
        tree.heading("Phone", text="Phone")
        tree.heading("Relationship", text="Relationship")

        for col in tree["columns"]:
            tree.column(col, width=200, anchor=tk.W)

        for contact in contacts:
            tree.insert("", tk.END, values=contact)

        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(expand=True, fill=tk.BOTH)
        tk.Frame(self.root, height=20, bg=COLORS["background"]).pack()
        
    def view_ambulance_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        header = tk.Frame(self.root, bg=COLORS["primary"], padx=20, pady=15)
        header.pack(fill=tk.X)
    
        tk.Label(header, 
        text="Ambulance Directory", 
        font=FONTS["heading"],
        bg=COLORS["primary"],
        fg="white").pack(side=tk.LEFT)
        
        ttk.Button(header, text="← Back", command=self.dashboard).pack(side=tk.RIGHT)

        filter_container = tk.Frame(self.root, bg=COLORS["background"])
        filter_container.pack(pady=10)
    
        filter_frame = tk.Frame(filter_container, bg=COLORS["background"])
        filter_frame.pack()
    
        tk.Label(filter_frame, 
        text="Area:", 
        font=FONTS["subheading"],
        bg=COLORS["background"]).grid(row=0, column=0, padx=5, sticky="e")
    
        self.ambulance_area_filter_entry = ttk.Entry(filter_frame, font=FONTS["body"], width=30)
        self.ambulance_area_filter_entry.grid(row=0, column=1, padx=5)
    
        ttk.Button(filter_frame, 
        text="Filter", 
        command=self.filter_ambulances).grid(row=0, column=2, padx=10)

        result_frame = tk.Frame(self.root, bg=COLORS["background"], padx=20, pady=10)
        result_frame.pack(expand=True, fill=tk.BOTH)
    
        self.ambulance_tree = ttk.Treeview(result_frame, columns=("Name", "Area", "Phone"), show="headings")
    
        for col in self.ambulance_tree["columns"]:
            self.ambulance_tree.heading(col, text=col)
            self.ambulance_tree.column(col, width=200, anchor=tk.W)
    
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.ambulance_tree.yview)
        self.ambulance_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ambulance_tree.pack(expand=True, fill=tk.BOTH)
        self.filter_ambulances()

    def filter_ambulances(self):
        area_filter = self.ambulance_area_filter_entry.get().lower()
    
        for item in self.ambulance_tree.get_children():
            self.ambulance_tree.delete(item)
    
        db = connect_db()
        cursor = db.cursor()
        query = "SELECT name, area, phone FROM ambulance WHERE 1=1"
        params = []
    
        if area_filter:
            query += " AND LOWER(area) LIKE %s"
            params.append(f"%{area_filter}%")

        cursor.execute(query, tuple(params))
        ambulances = cursor.fetchall()
        db.close()
    
        for ambulance in ambulances:
            self.ambulance_tree.insert("", tk.END, values=ambulance)

    def view_doctor_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        header = tk.Frame(self.root, bg=COLORS["primary"], padx=20, pady=15)
        header.pack(fill=tk.X)
    
        tk.Label(header, 
        text="Doctor Directory", 
        font=FONTS["heading"],
        bg=COLORS["primary"],
        fg="white").pack(side=tk.LEFT)
    
        ttk.Button(header, text="← Back", command=self.dashboard).pack(side=tk.RIGHT)

        filter_frame = tk.Frame(self.root, bg=COLORS["background"], padx=20, pady=10)
        filter_frame.pack(fill=tk.X)
    
        tk.Label(filter_frame, 
        text="Area:", 
        font=FONTS["subheading"],
        bg=COLORS["background"]).grid(row=0, column=0, padx=5, sticky="e")
    
        self.area_filter_entry = ttk.Entry(filter_frame, font=FONTS["body"])
        self.area_filter_entry.grid(row=0, column=1, padx=5, sticky="ew")
    
        tk.Label(filter_frame, 
        text="Department:", 
        font=FONTS["subheading"],
        bg=COLORS["background"]).grid(row=0, column=2, padx=5, sticky="e")
    
        self.dept_filter_entry = ttk.Entry(filter_frame, font=FONTS["body"])
        self.dept_filter_entry.grid(row=0, column=3, padx=5, sticky="ew")
    
        ttk.Button(filter_frame, 
        text="Filter", 
        command=self.filter_doctors).grid(row=0, column=4, padx=10)
    
        filter_frame.grid_columnconfigure(1, weight=1)
        filter_frame.grid_columnconfigure(3, weight=1)

        result_frame = tk.Frame(self.root, bg=COLORS["background"], padx=20, pady=10)
        result_frame.pack(expand=True, fill=tk.BOTH)
    
        self.doctor_tree = ttk.Treeview(result_frame, columns=("Name", "Education", "Department", "Chamber", "Chamber Time"), show="headings")
    
        for col in self.doctor_tree["columns"]:
            self.doctor_tree.heading(col, text=col)
            self.doctor_tree.column(col, width=150, anchor=tk.W)
    
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.doctor_tree.yview)
        self.doctor_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.doctor_tree.pack(expand=True, fill=tk.BOTH)
        self.filter_doctors()

    def filter_doctors(self):
        area_filter = self.area_filter_entry.get().lower()
        dept_filter = self.dept_filter_entry.get().lower()
    
        for item in self.doctor_tree.get_children():
            self.doctor_tree.delete(item)
    
        db = connect_db()
        cursor = db.cursor()
    
        query = "SELECT name, education, department, chamber, chamber_time FROM doctors WHERE 1=1"
        params = []
    
        if area_filter:
            query += " AND LOWER(chamber) LIKE %s"
            params.append(f"%{area_filter}%")
    
        if dept_filter:
            query += " AND LOWER(department) LIKE %s"
            params.append(f"%{dept_filter}%")
    
        cursor.execute(query, tuple(params))
        doctors = cursor.fetchall()
        db.close()
    
        for doctor in doctors:
            self.doctor_tree.insert("", tk.END, values=doctor)

    def hospital_ticket_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        header = tk.Frame(self.root, bg=COLORS["primary"], padx=20, pady=15)
        header.pack(fill=tk.X)
    
        tk.Label(header, 
                text="Hospital Ticket Booking", 
                font=FONTS["heading"], 
                bg=COLORS["primary"],
                fg="white").pack(side=tk.LEFT)
    
        ttk.Button(header, 
                  text="← Back", 
                  command=self.dashboard).pack(side=tk.RIGHT)

        main_frame = tk.Frame(self.root, bg=COLORS["background"], padx=20, pady=20)
        main_frame.pack(expand=True, fill=tk.BOTH)

        hospitals = [
            ("Dhaka Medical College", "https://dmch.bindu.health/"),
            ("Kurmitola General Hospital", "https://kgh.bindu.health/"),
            ("250 BEDDED TB HOSPITAL", "https://tbhs.bindu.health/patient/booking"),
            ("NICRH", "https://nicrh.bindu.health/patient/booking"),
            ("NIDCH", "https://nidch.bindu.health/patient/booking"),
            ("IBN Sina", "https://www.ibnsinatrust.com/find_a_doctor.php"),
            ("LabAid", "https://appointment.labaid.com.bd/"),
            ("Popular Diagnostic Center", "https://appointment.populardiagnostic.com/appointment")
        ]

        for i, (name, url) in enumerate(hospitals):
            btn = tk.Button(main_frame, 
                       text=name, 
                       command=lambda u=url: self.open_hospital_website(u),
                       font=FONTS["button"],
                       bg=COLORS["card_bg"],
                       fg=COLORS["text"],
                       activebackground=COLORS["accent"],
                       activeforeground="white",
                       relief=tk.FLAT,
                       borderwidth=0,
                       padx=20,
                       pady=10)
            btn.grid(row=i//2, column=i%2, padx=10, pady=10, sticky="nsew")
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=COLORS["accent"], fg="white"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=COLORS["card_bg"], fg=COLORS["text"]))
            main_frame.grid_columnconfigure(i%2, weight=1)
    
        footer = tk.Frame(self.root, bg=COLORS["background"], padx=20, pady=10)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
    
        tk.Label(footer, 
                text="Patient Medication Reminder v2.0",
                font=("Poppins", 9),
                bg=COLORS["background"],
                fg="#777777").pack()

    def open_hospital_website(self, url):
        import webbrowser
        webbrowser.open_new(url)
        
                 
    def about_us(self):
        for widget in self.root.winfo_children()[1:-1]:
            widget.destroy()

        main_frame = tk.Frame(self.root, bg=COLORS["background"])
        main_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        back_btn = ttk.Button(main_frame, 
                text="← Back to Dashboard", 
                command=self.dashboard)
        back_btn.pack(anchor="nw", pady=(0, 20))

        about_card = tk.Frame(main_frame, 
              bg=COLORS["card_bg"],
              padx=30, 
              pady=30,
              highlightbackground=COLORS["card_shadow"],
              highlightthickness=1)
        about_card.pack(fill=tk.BOTH, expand=True)

        title_frame = tk.Frame(about_card, bg=COLORS["card_bg"])
        title_frame.pack(pady=20)
        tk.Label(title_frame, text="NexaData Team", 
                font=("Poppins", 28, "bold"), bg=COLORS["card_bg"]).pack()
        tk.Label(title_frame, text="Patient Medication Reminder System", 
                font=("Poppins", 14), bg=COLORS["card_bg"]).pack(pady=5)
    
        team_container = tk.Frame(about_card, bg=COLORS["card_bg"])
        team_container.pack(fill=tk.BOTH, expand=True)
    
        canvas = tk.Canvas(team_container, bg=COLORS["card_bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(team_container, orient="horizontal", command=canvas.xview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS["card_bg"])
    
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
    
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(xscrollcommand=scrollbar.set)
    
        scrollbar.pack(side="bottom", fill="x")
        canvas.pack(side="top", fill="both", expand=True)
    
        team_members = [
            {
            "name": "Istiak Hossain",
            "position": "Team Lead",
            "education": "BSc in CSE",
            "image": "images/Istiak.jpg"
            },
            {
            "name": "Thanvir Hossen Niloy",
            "position": "Database Developer",
            "education": "BSc in CSE",
            "image": "images/Niloy.jpg"
            },
            {
            "name": "Mostafizur Rahman",
            "position": "Backend Developer",
            "education": "BSc in CSE",
            "image": "images/Mostafiz.jpg"
            },
            {
            "name": "Nayeem Hassan Noyon",
            "position": "Backend Developer",
            "education": "BSc in CSE",
            "image": "images/Nehal.jpg"
            },
            {
            "name": "Tarek Monwar",
            "position": "Backend Developer",
            "education": "BSc in CSE",
            "image": "images/Tarek.jpg"
            }
        ]
    
        for i, member in enumerate(team_members):
            card = tk.Frame(scrollable_frame, bg="white", bd=2, relief=tk.RAISED, 
                          padx=20, pady=20, width=250, height=400)
            card.pack(side="left", padx=20, pady=10, fill="y", expand=False)
        
            # Image section
            img_frame = tk.Frame(card, bg="white")
            img_frame.pack(pady=(0, 15))
        
            try:
                img = Image.open(member["image"])
                img = img.resize((180, 180), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                img_label = tk.Label(img_frame, image=photo, bg="white")
                img_label.image = photo
                img_label.pack()
            except:
                tk.Label(img_frame, text="No Image", bg="white", 
                        font=("Arial", 10), width=20, height=8).pack()
        
            info_frame = tk.Frame(card, bg="white")
            info_frame.pack(fill="both", expand=True)
        
            tk.Label(info_frame, text=member["name"], bg="white", 
                    font=("Poppins", 14, "bold")).pack(pady=(0, 5))
            tk.Label(info_frame, text=member["position"], bg="white", 
                    font=("Poppins", 12)).pack(pady=(0, 5))
            tk.Label(info_frame, text=f"Education: {member['education']}", bg="white", 
                    font=("Poppins", 11)).pack()
    
    def logout(self):   
        self.current_user = None
        self.login_screen()

# Main Execution
if __name__ == "__main__":
    setup_database()
    root = tk.Tk()
    splash = tk.Toplevel(root)
    splash.geometry("800x500")
    splash.title("Loading...")
    splash.configure(bg=COLORS["primary"])
    splash.overrideredirect(True)
    
    window_width = 800
    window_height = 500
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    splash.geometry(f"{window_width}x{window_height}+{x}+{y}")

    main_frame = tk.Frame(splash, bg=COLORS["primary"])
    main_frame.pack(expand=True, fill=tk.BOTH, padx=50, pady=50)

    tk.Label(main_frame, 
            text="MediNex", 
            font=("Poppins", 32, "bold"), 
            bg=COLORS["primary"],
            fg="white").pack(pady=(50, 10))

    tk.Label(main_frame, 
            text="Stay Healthy. Stay On Time.", 
            font=("Poppins", 16), 
            bg=COLORS["primary"],
            fg="#E9ECEF").pack(pady=(0, 50))
    # Loading bar
    progress_frame = tk.Frame(main_frame, bg=COLORS["primary"])
    progress_frame.pack(fill=tk.X, pady=20)

    progress = ttk.Progressbar(progress_frame, 
                             orient="horizontal", 
                             length=400, 
                             mode="determinate")
    progress.pack()
    progress.start(10)

    tk.Label(main_frame, 
            text="Initializing application...", 
            font=("Poppins", 10), 
            bg=COLORS["primary"],
            fg="#E9ECEF").pack()

    app = PatientMedicationReminderApp(root)
    def close_splash():
        splash.destroy()
        app.login_screen()
        root.deiconify()
        threading.Thread(target=reminder_thread, args=(app,), daemon=True).start()
    root.withdraw()
    splash.after(3000, close_splash)
    root.mainloop()