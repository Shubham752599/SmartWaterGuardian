from flask import make_response
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from io import BytesIO
from email.mime import image
from openpyxl import Workbook
from flask import flash
from werkzeug.security import generate_password_hash, check_password_hash

from flask import Flask, render_template, request, redirect,session,flash
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config['MYSQL_HOST'] = 'mysql-5336d3f-shubhamkushwaha7525-4c26.i.aivencloud.com'
app.config['MYSQL_PORT'] = 15992
app.config['MYSQL_USER'] = 'avnadmin'
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD")
app.config['MYSQL_DB'] = 'smart_water_guardian'
app.config['MYSQL_SSL_CA'] = 'ca.pem'
app.secret_key = "smartwaterguardian123"

mysql = MySQL(app)

@app.route("/")
def home():

    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM reports")
    total_reports = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM reports WHERE status='Pending'")
    pending_reports = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM reports WHERE status='Resolved'")
    resolved_reports = cur.fetchone()[0]

    cur.close()

    return render_template(
        "index.html",
        total_reports=total_reports,
        total_users=total_users,
        pending_reports=pending_reports,
        resolved_reports=resolved_reports
    )

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        cur = mysql.connection.cursor()

        cur.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )

        user = cur.fetchone()

        cur.close()

        if user and check_password_hash(user[3], password):

           session["user"] = user[1]

           return redirect("/dashboard")

        else:

           return render_template(
        "login.html",
        error="❌ Invalid Email or Password"
    )

    return render_template("login.html", error="")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        fullname = request.form["fullname"]
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)

        cur = mysql.connection.cursor()

        cur.execute("""
            INSERT INTO users(fullname, email,password)
            VALUES(%s, %s, %s)
        """, (fullname, email, hashed_password))

        mysql.connection.commit()
        cur.close()

        return render_template(
            "register.html",
            success="✅ Registration Successful!"
        )

    return render_template("register.html")

@app.route("/report", methods=["GET", "POST"])
def report():

    if request.method == "POST":

        fullname = request.form["fullname"]
        mobile = request.form["mobile"]
        address = request.form["address"]
        city = request.form["city"]
        leakage_type = request.form["leakage_type"]
        description = request.form["description"]
        image = request.files["image"]

        # ================= Validation =================

        # Mobile Number
        if not mobile.isdigit() or len(mobile) != 10:
            return render_template(
                "report.html",
                success="❌ Mobile Number must be exactly 10 digits."
            )

        # Name
        if len(fullname.strip()) < 3:
            return render_template(
                "report.html",
                success="❌ Name must be at least 3 characters."
            )

        # ================= Save Image =================

        filename = secure_filename(image.filename)

        image.save(
            os.path.join(app.config["UPLOAD_FOLDER"], filename)
        )

        # ================= Database =================

        cur = mysql.connection.cursor()

        cur.execute("""
        INSERT INTO reports
        (fullname, mobile, address, city, leakage_type, description, image)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            fullname,
            mobile,
            address,
            city,
            leakage_type,
            description,
            filename
        ))

        mysql.connection.commit()
        cur.close()

        flash("✅ Report Submitted Successfully!", "success")
        return redirect("/dashboard")

    return render_template("report.html", success="")

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/login")

    search = request.args.get("search", "")
    status = request.args.get("status", "")
    sort = request.args.get("sort", "desc")
    date = request.args.get("date", "")

    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    cur = mysql.connection.cursor()

    # Total Reports
    cur.execute("SELECT COUNT(*) FROM reports")
    total_reports = cur.fetchone()[0]

    # Total Users
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    # Pending Reports
    cur.execute("SELECT COUNT(*) FROM reports WHERE status='Pending'")
    pending_reports = cur.fetchone()[0]

    # In Progress Reports
    cur.execute("SELECT COUNT(*) FROM reports WHERE status='In Progress'")
    inprogress_reports = cur.fetchone()[0]

    # Resolved Reports
    cur.execute("SELECT COUNT(*) FROM reports WHERE status='Resolved'")
    resolved_reports = cur.fetchone()[0]

    # City Wise Reports
    cur.execute("""
        SELECT city, COUNT(*)
        FROM reports
        GROUP BY city
        ORDER BY COUNT(*) DESC
    """)
    city_data = cur.fetchall()

    # Dynamic Query
    query = """
        SELECT id, fullname, city, leakage_type, mobile, image, status,created_at
        FROM reports
        WHERE 1=1
    """

    params = []

    if search:
        query += " AND (fullname LIKE %s OR city LIKE %s)"
        params.append("%" + search + "%")
        params.append("%" + search + "%")

    if status:
        query += " AND status=%s"
        params.append(status)

    if date:
        query += " AND DATE(created_at)=%s"
        params.append(date)

    if sort == "asc":
       query += " ORDER BY id ASC"
    else:
        query += " ORDER BY id DESC"

    query += " LIMIT %s OFFSET %s"

    params.append(per_page)
    params.append(offset)

    cur.execute(query, tuple(params))
    reports = cur.fetchall()

    # Total Pages
    cur.execute("SELECT COUNT(*) FROM reports")
    total = cur.fetchone()[0]
    pages = (total + per_page - 1) // per_page

    cur.close()

    return render_template(
        "dashboard.html",
        username=session["user"],
        total_reports=total_reports,
        total_users=total_users,
        pending_reports=pending_reports,
        inprogress_reports=inprogress_reports,
        resolved_reports=resolved_reports,
        reports=reports,
        city_data=city_data,
        search=search,
        status=status,
        date=date,
        sort=sort,
        page=page,
        pages=pages
    ) 
@app.route("/view/<int:id>")
def view_report(id):

    if "user" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM reports WHERE id=%s", (id,))
    report = cur.fetchone()

    cur.close()

    return render_template(
        "view_report.html",
        report=report
    )

@app.route("/delete/<int:id>")
def delete(id):

    if "user" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()

    cur.execute("DELETE FROM reports WHERE id=%s", (id,))

    mysql.connection.commit()

    cur.close()
    flash("🗑 Report Deleted Successfully!", "success")

    return redirect("/dashboard")
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):

    if "user" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()

    # Update Data
    if request.method == "POST":

        fullname = request.form["fullname"]
        mobile = request.form["mobile"]
        address = request.form["address"]
        city = request.form["city"]
        leakage_type = request.form["leakage_type"]
        description = request.form["description"]

        cur.execute("""
            UPDATE reports
            SET fullname=%s,
                mobile=%s,
                address=%s,
                city=%s,
                leakage_type=%s,
                description=%s
            WHERE id=%s
        """, (
            fullname,
            mobile,
            address,
            city,
            leakage_type,
            description,
            id
        ))

        mysql.connection.commit()
        cur.close()
        flash("✏️ Report Updated Successfully!", "success")

        return redirect("/dashboard")

    # Show Existing Data
    cur.execute("SELECT * FROM reports WHERE id=%s", (id,))
    report = cur.fetchone()

    cur.close()

    return render_template("edit_report.html", report=report)

@app.route("/update_status/<int:id>")
def update_status(id):

    if "user" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()

    # Current Status
    cur.execute("SELECT status FROM reports WHERE id=%s", (id,))
    status = cur.fetchone()[0]

    # Change Status
    if status == "Pending":
        new_status = "In Progress"

    elif status == "In Progress":
        new_status = "Resolved"

    else:
        new_status = "Pending"

    cur.execute(
        "UPDATE reports SET status=%s WHERE id=%s",
        (new_status, id)
    )

    mysql.connection.commit()
    cur.close()
    flash("🔄 Status Updated Successfully!", "success")

    return redirect("/dashboard")

@app.route("/export_pdf")
def export_pdf():

    if "user" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT fullname, city, leakage_type, mobile, status
        FROM reports
        ORDER BY id DESC
    """)

    reports = cur.fetchall()
    
    cur.close()

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()

    data = []

    data.append([
        Paragraph("<b>Name</b>", styles["BodyText"]),
        Paragraph("<b>City</b>", styles["BodyText"]),
        Paragraph("<b>Leakage</b>", styles["BodyText"]),
        Paragraph("<b>Mobile</b>", styles["BodyText"]),
        Paragraph("<b>Status</b>", styles["BodyText"])
    ])

    for report in reports:
        data.append(list(report))

    table = Table(data)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.green),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
    ]))

    doc.build([table])

    pdf = buffer.getvalue()
    buffer.close()

    response = make_response(pdf)

    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=Water_Reports.pdf"

    return response

@app.route("/export_excel")
def export_excel():

    if "user" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT fullname, city, leakage_type, mobile, status
        FROM reports
        ORDER BY id DESC
    """)

    reports = cur.fetchall()
    cur.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Water Reports"

    # Header
    ws.append([
        "Full Name",
        "City",
        "Leakage Type",
        "Mobile",
        "Status"
    ])

    # Data
    for row in reports:
        ws.append(row)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = make_response(output.getvalue())

    response.headers[
        "Content-Disposition"
    ] = "attachment; filename=Smart_Water_Reports.xlsx"

    response.headers[
        "Content-Type"
    ] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    return response

@app.route("/logout")
def logout():

    session.pop("user", None)

    return redirect("/")

@app.route("/testdb")

def testdb():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return "✅ Database Connected Successfully!"
    except Exception as e:
        return f"❌ Error: {e}"
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form["email"]
        new_password = request.form["password"]

        cur = mysql.connection.cursor()

        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if user:

            cur.execute(
                "UPDATE users SET password=%s WHERE email=%s",
                (new_password, email)
            )

            mysql.connection.commit()
            cur.close()

            return render_template(
                "forgot_password.html",
                success="✅ Password Updated Successfully!"
            )

        else:

            cur.close()

            return render_template(
                "forgot_password.html",
                error="❌ Email Not Found!"
            )

    return render_template("forgot_password.html")     


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

    