from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database.database import get_db, create_tables

app = Flask(__name__)
app.secret_key = "hotel-secret-key"

create_tables()


@app.template_filter("nice_date")
def nice_date(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError):
        return text


INACTIVE_STATUSES = ("Checked-out", "Cancelled")


def split_rooms(text):
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip() != ""]


def clean_rooms(text):
    return sorted(set(split_rooms(text)))


@app.template_filter("room_list")
def room_list(text):
    return ", ".join(split_rooms(text))


@app.template_filter("rooms_label")
def rooms_label(text):
    rooms = split_rooms(text)
    if len(rooms) == 1:
        return "Room " + rooms[0]
    return "Rooms " + ", ".join(rooms)


FLOORS = 5
ROOMS_PER_FLOOR = 9
TOTAL_ROOMS = FLOORS * ROOMS_PER_FLOOR


def get_all_rooms():
    floors = []
    for floor in range(1, FLOORS + 1):
        rooms = []
        for number in range(1, ROOMS_PER_FLOOR + 1):
            rooms.append(str(floor * 100 + number))
        floors.append({"floor": floor, "rooms": rooms})
    return floors


def get_occupied_rooms(ignore_customer_id=0):
    db = get_db()
    rows = db.execute("""SELECT room_number FROM customers
                         WHERE booking_status NOT IN ('Checked-out', 'Cancelled')
                         AND id != ?""", (ignore_customer_id,)).fetchall()
    db.close()
    occupied = []
    for row in rows:
        occupied.extend(split_rooms(row["room_number"]))
    return occupied


def check_rooms(rooms, booking_status, ignore_customer_id=0):
    if len(rooms) == 0:
        return "Please select at least one room."

    all_rooms = []
    for floor in get_all_rooms():
        all_rooms = all_rooms + floor["rooms"]
    for room in rooms:
        if room not in all_rooms:
            return "Please select rooms from the list."

    if booking_status in INACTIVE_STATUSES:
        return None

    occupied = get_occupied_rooms(ignore_customer_id)
    taken = [room for room in rooms if room in occupied]
    if len(taken) == 1:
        return "Room " + taken[0] + " is already occupied. Please choose a green room."
    if len(taken) > 1:
        return "Rooms " + ", ".join(taken) + " are already occupied. Please choose green rooms."
    return None


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip().lower()
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if full_name == "" or email == "" or username == "" or password == "":
            flash("Please fill in all the fields.", "error")
            return redirect(url_for("register"))

        if "@" not in email or "." not in email:
            flash("Please enter a valid email.", "error")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        db = get_db()
        old_user = db.execute("SELECT id FROM users WHERE username = ? OR email = ?",
                              (username, email)).fetchone()
        if old_user:
            db.close()
            flash("That username or email is already used.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password, method="pbkdf2:sha256")
        db.execute("INSERT INTO users (full_name, email, username, password_hash) VALUES (?, ?, ?, ?)",
                   (full_name, email, username, password_hash))
        db.commit()
        db.close()

        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form["login_name"].strip()
        password = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ? OR email = ?",
                          (name, name.lower())).fetchone()
        db.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            return redirect(url_for("dashboard"))

        flash("Wrong username/email or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You are logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    total_customers = db.execute("SELECT COALESCE(SUM(number_of_guests), 0) FROM customers").fetchone()[0]
    total_employees = db.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    total_bookings = db.execute("SELECT COUNT(*) FROM customers WHERE booking_status != 'Cancelled'").fetchone()[0]

    recent_bookings = db.execute("""SELECT * FROM customers
                                    WHERE booking_status NOT IN ('Checked-out', 'Cancelled')
                                    ORDER BY id DESC LIMIT 4""").fetchall()
    db.close()

    valid_rooms = []
    for floor in get_all_rooms():
        valid_rooms = valid_rooms + floor["rooms"]
    occupied = len([room for room in set(get_occupied_rooms()) if room in valid_rooms])
    available = TOTAL_ROOMS - occupied
    available_percent = round(available * 100 / TOTAL_ROOMS)

    first_name = session["full_name"].split()[0]
    today = datetime.now().strftime("%A, %d %B %Y")

    return render_template("dashboard.html",
                           first_name=first_name,
                           today=today,
                           total_customers=total_customers,
                           total_employees=total_employees,
                           total_rooms=TOTAL_ROOMS,
                           available=available,
                           occupied=occupied,
                           available_percent=available_percent,
                           total_bookings=total_bookings,
                           recent_bookings=recent_bookings)


@app.route("/rooms")
def rooms():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    rows = db.execute("""SELECT room_number, full_name, booking_status, check_out_date FROM customers
                         WHERE booking_status NOT IN ('Checked-out', 'Cancelled')
                         ORDER BY id""").fetchall()
    db.close()

    guests = {}
    for row in rows:
        for room in split_rooms(row["room_number"]):
            guests[room] = row

    floors = get_all_rooms()
    occupied = 0
    for floor in floors:
        for room in floor["rooms"]:
            if room in guests:
                occupied = occupied + 1

    return render_template("rooms.html", floors=floors, guests=guests,
                           total_rooms=TOTAL_ROOMS, occupied=occupied,
                           available=TOTAL_ROOMS - occupied)


@app.route("/customers")
def customers():
    if "user_id" not in session:
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()

    sql = "SELECT * FROM customers WHERE 1 = 1"
    values = []
    if search != "":
        like = "%" + search + "%"
        sql = sql + " AND (full_name LIKE ? OR email LIKE ? OR phone LIKE ? OR room_number LIKE ?)"
        values.extend([like, like, like, like])
    sql = sql + " ORDER BY id DESC"

    db = get_db()
    rows = db.execute(sql, values).fetchall()
    db.close()

    return render_template("customers.html", customers=rows, search=search,
                           inactive=INACTIVE_STATUSES)


@app.route("/customers/add", methods=["GET", "POST"])
def add_customer():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        address = request.form["address"].strip()
        gender = request.form["gender"]
        date_of_birth = request.form["date_of_birth"]
        id_proof_type = request.form["id_proof_type"]
        id_proof_number = request.form["id_proof_number"].strip()
        check_in_date = request.form["check_in_date"]
        check_out_date = request.form["check_out_date"]
        room_number = request.form["room_number"].strip()
        number_of_guests = request.form["number_of_guests"]
        booking_status = request.form["booking_status"]
        payment_status = request.form["payment_status"]

        if full_name == "" or email == "" or phone == "" or address == "" or room_number == "" \
                or id_proof_number == "" or check_in_date == "" or check_out_date == "" \
                or date_of_birth == "" or number_of_guests == "":
            flash("Please fill in all the fields.", "error")
            return redirect(url_for("add_customer"))

        if "@" not in email or "." not in email:
            flash("Please enter a valid email.", "error")
            return redirect(url_for("add_customer"))

        if check_out_date < check_in_date:
            flash("Check-out date cannot be before check-in date.", "error")
            return redirect(url_for("add_customer"))

        rooms = clean_rooms(room_number)
        room_error = check_rooms(rooms, booking_status)
        if room_error:
            flash(room_error, "error")
            return redirect(url_for("add_customer"))
        room_number = ",".join(rooms)

        db = get_db()
        db.execute("""INSERT INTO customers
            (full_name, email, phone, address, gender, date_of_birth, id_proof_type, id_proof_number,
             check_in_date, check_out_date, room_number, number_of_guests, booking_status, payment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   (full_name, email, phone, address, gender, date_of_birth, id_proof_type, id_proof_number,
                    check_in_date, check_out_date, room_number, number_of_guests, booking_status, payment_status))
        db.commit()
        db.close()

        flash("Customer added successfully!", "success")
        return redirect(url_for("customers"))

    return render_template("add_customer.html", floors=get_all_rooms(),
                           occupied=get_occupied_rooms(), selected_rooms=[])


@app.route("/customers/edit/<int:id>", methods=["GET", "POST"])
def edit_customer(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id = ?", (id,)).fetchone()

    if customer is None:
        db.close()
        flash("Customer not found.", "error")
        return redirect(url_for("customers"))

    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        address = request.form["address"].strip()
        gender = request.form["gender"]
        date_of_birth = request.form["date_of_birth"]
        id_proof_type = request.form["id_proof_type"]
        id_proof_number = request.form["id_proof_number"].strip()
        check_in_date = request.form["check_in_date"]
        check_out_date = request.form["check_out_date"]
        room_number = request.form["room_number"].strip()
        number_of_guests = request.form["number_of_guests"]
        booking_status = request.form["booking_status"]
        payment_status = request.form["payment_status"]

        if full_name == "" or email == "" or phone == "" or address == "" or room_number == "" \
                or id_proof_number == "" or check_in_date == "" or check_out_date == "" \
                or date_of_birth == "" or number_of_guests == "":
            db.close()
            flash("Please fill in all the fields.", "error")
            return redirect(url_for("edit_customer", id=id))

        if "@" not in email or "." not in email:
            db.close()
            flash("Please enter a valid email.", "error")
            return redirect(url_for("edit_customer", id=id))

        if check_out_date < check_in_date:
            db.close()
            flash("Check-out date cannot be before check-in date.", "error")
            return redirect(url_for("edit_customer", id=id))

        rooms = clean_rooms(room_number)
        room_error = check_rooms(rooms, booking_status, id)
        if room_error:
            db.close()
            flash(room_error, "error")
            return redirect(url_for("edit_customer", id=id))
        room_number = ",".join(rooms)

        db.execute("""UPDATE customers SET
            full_name = ?, email = ?, phone = ?, address = ?, gender = ?, date_of_birth = ?,
            id_proof_type = ?, id_proof_number = ?, check_in_date = ?, check_out_date = ?,
            room_number = ?, number_of_guests = ?, booking_status = ?, payment_status = ?
            WHERE id = ?""",
                   (full_name, email, phone, address, gender, date_of_birth, id_proof_type, id_proof_number,
                    check_in_date, check_out_date, room_number, number_of_guests, booking_status,
                    payment_status, id))
        db.commit()
        db.close()

        flash("Customer updated successfully!", "success")
        return redirect(url_for("customers"))

    db.close()
    return render_template("edit_customer.html", customer=customer, floors=get_all_rooms(),
                           occupied=get_occupied_rooms(id),
                           selected_rooms=split_rooms(customer["room_number"]))


@app.route("/customers/checkout/<int:id>", methods=["POST"])
def checkout_customer(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id = ?", (id,)).fetchone()

    if customer is None:
        db.close()
        flash("Customer not found.", "error")
        return redirect(url_for("customers"))

    if customer["booking_status"] in INACTIVE_STATUSES:
        db.close()
        flash(customer["full_name"] + " is already " + customer["booking_status"] + ".", "error")
        return redirect(url_for("customers"))

    today = datetime.now().strftime("%Y-%m-%d")
    if customer["check_in_date"] and today < customer["check_in_date"]:
        today = customer["check_in_date"]

    db.execute("UPDATE customers SET booking_status = 'Checked-out', check_out_date = ? WHERE id = ?",
               (today, id))
    db.commit()
    db.close()

    flash(customer["full_name"] + " checked out. " + rooms_label(customer["room_number"])
          + " can be booked again.", "success")
    return redirect(url_for("customers"))


@app.route("/customers/delete/<int:id>", methods=["POST"])
def delete_customer(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    db.execute("DELETE FROM customers WHERE id = ?", (id,))
    db.commit()
    db.close()

    flash("Customer deleted.", "success")
    return redirect(url_for("customers"))


@app.route("/employees")
def employees():
    if "user_id" not in session:
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    db = get_db()
    if search != "":
        like = "%" + search + "%"
        rows = db.execute("""SELECT * FROM employees
                             WHERE full_name LIKE ? OR email LIKE ? OR phone LIKE ?
                             OR department LIKE ? OR position LIKE ?
                             ORDER BY id DESC""", (like, like, like, like, like)).fetchall()
    else:
        rows = db.execute("SELECT * FROM employees ORDER BY id DESC").fetchall()
    db.close()

    return render_template("employees.html", employees=rows, search=search)


@app.route("/employees/add", methods=["GET", "POST"])
def add_employee():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        address = request.form["address"].strip()
        gender = request.form["gender"]
        date_of_birth = request.form["date_of_birth"]
        department = request.form["department"]
        position = request.form["position"]
        salary = request.form["salary"].strip()
        joining_date = request.form["joining_date"]
        employee_status = request.form["employee_status"]

        if full_name == "" or email == "" or phone == "" or address == "" \
                or date_of_birth == "" or salary == "" or joining_date == "":
            flash("Please fill in all the fields.", "error")
            return redirect(url_for("add_employee"))

        if "@" not in email or "." not in email:
            flash("Please enter a valid email.", "error")
            return redirect(url_for("add_employee"))

        try:
            salary = float(salary)
        except ValueError:
            flash("Salary must be a number.", "error")
            return redirect(url_for("add_employee"))

        db = get_db()
        db.execute("""INSERT INTO employees
            (full_name, email, phone, address, gender, date_of_birth, department, position,
             salary, joining_date, employee_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   (full_name, email, phone, address, gender, date_of_birth, department, position,
                    salary, joining_date, employee_status))
        db.commit()
        db.close()

        flash("Employee added successfully!", "success")
        return redirect(url_for("employees"))

    return render_template("add_employee.html")


@app.route("/employees/edit/<int:id>", methods=["GET", "POST"])
def edit_employee(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    employee = db.execute("SELECT * FROM employees WHERE id = ?", (id,)).fetchone()

    if employee is None:
        db.close()
        flash("Employee not found.", "error")
        return redirect(url_for("employees"))

    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        address = request.form["address"].strip()
        gender = request.form["gender"]
        date_of_birth = request.form["date_of_birth"]
        department = request.form["department"]
        position = request.form["position"]
        salary = request.form["salary"].strip()
        joining_date = request.form["joining_date"]
        employee_status = request.form["employee_status"]

        if full_name == "" or email == "" or phone == "" or address == "" \
                or date_of_birth == "" or salary == "" or joining_date == "":
            db.close()
            flash("Please fill in all the fields.", "error")
            return redirect(url_for("edit_employee", id=id))

        if "@" not in email or "." not in email:
            db.close()
            flash("Please enter a valid email.", "error")
            return redirect(url_for("edit_employee", id=id))

        try:
            salary = float(salary)
        except ValueError:
            db.close()
            flash("Salary must be a number.", "error")
            return redirect(url_for("edit_employee", id=id))

        db.execute("""UPDATE employees SET
            full_name = ?, email = ?, phone = ?, address = ?, gender = ?, date_of_birth = ?,
            department = ?, position = ?, salary = ?, joining_date = ?, employee_status = ?
            WHERE id = ?""",
                   (full_name, email, phone, address, gender, date_of_birth, department, position,
                    salary, joining_date, employee_status, id))
        db.commit()
        db.close()

        flash("Employee updated successfully!", "success")
        return redirect(url_for("employees"))

    db.close()
    return render_template("edit_employee.html", employee=employee)


@app.route("/employees/delete/<int:id>", methods=["POST"])
def delete_employee(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    db.execute("DELETE FROM employees WHERE id = ?", (id,))
    db.commit()
    db.close()

    flash("Employee deleted.", "success")
    return redirect(url_for("employees"))


if __name__ == "__main__":
    app.run(debug=True)
