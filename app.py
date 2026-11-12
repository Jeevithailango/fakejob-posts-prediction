from flask import Flask, render_template, request, redirect, session,flash
import tensorflow as tf
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.preprocessing.text import Tokenizer
from database import db, init_db
import sqlite3

app = Flask(__name__)
app.secret_key = "secret"
init_db()

@app.route('/')
def index():
    return render_template("index.html")

# ---------------- ADMIN ----------------

@app.route('/admin_login', methods=['GET','POST'])
def admin_login():
    if request.method == "POST":
        if request.form['username']=="admin" and request.form['password']=="admin123":
            session['admin'] = True
            return redirect('/admin_dashboard')
        return "Invalid Admin Login"
    return render_template("admin_login.html")

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/admin_login')
    return render_template("admin_dashboard.html")


@app.route('/admin_recruiters')
def admin_recruiters():
    if 'admin' not in session:
        return redirect('/admin_login')

    con = sqlite3.connect('database.db')
    cur = con.cursor()

    cur.execute("SELECT * FROM recruiters")
    recruiters = cur.fetchall()

    con.close()

    return render_template('admin_recruiters.html', recruiters=recruiters)
    
@app.route('/admin_delete_recruiter/<int:id>')
def admin_delete_recruiter(id):
    if 'admin' not in session:
        return redirect('/admin_login')

    con = sqlite3.connect('database.db')
    cur = con.cursor()

    cur.execute("DELETE FROM recruiters WHERE id=?", (id,))
    con.commit()
    con.close()

    flash("Recruiter Deleted Successfully", "success")
    return redirect('/admin_recruiters')

@app.route('/block/<int:id>')
def block(id):
    con=db(); cur=con.cursor()
    cur.execute("UPDATE recruiters SET blocked=1 WHERE id=?", (id,))
    con.commit()
    return redirect('/admin_recruiters')

@app.route('/unblock/<int:id>')
def unblock(id):
    con=db(); cur=con.cursor()
    cur.execute("UPDATE recruiters SET blocked=0 WHERE id=?", (id,))
    con.commit()
    return redirect('/admin_recruiters')

@app.route('/admin_seekers')
def admin_seekers():
    con=db(); cur=con.cursor()
    cur.execute("SELECT * FROM seekers")
    data=cur.fetchall()
    return render_template("admin_seekers.html", data=data)

@app.route('/admin_jobs')
def admin_jobs():
    con=db(); cur=con.cursor()
    cur.execute("""SELECT jobs.*, recruiters.company_name 
                   FROM jobs JOIN recruiters 
                   ON jobs.recruiter_id=recruiters.id""")
    data=cur.fetchall()
    return render_template("admin_jobs.html", data=data)

@app.route('/admin_reports')
def admin_reports():
    con=db(); cur=con.cursor()
    cur.execute("SELECT COUNT(*) FROM jobs WHERE model_result='REAL'")
    real = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM jobs WHERE model_result='FAKE'")
    fake = cur.fetchone()[0]
    return render_template("admin_reports.html", real=real, fake=fake)

# ---------------- RECRUITER ----------------

@app.route('/recruiter_register', methods=['GET', 'POST'])
def recruiter_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']

        company_name = request.form['company_name']
        industry = request.form['industry']
        company_size = request.form['company_size']
        website = request.form['website']
        company_address = request.form['company_address']
     

        company_email = request.form['company_email']
        company_reg_no = request.form['company_reg_no']
        about_company = request.form['about_company']

        con = sqlite3.connect('database.db')
        cur = con.cursor()

        cur.execute("""
            INSERT INTO recruiters (
                name, email, phone, password,
                company_name, industry, company_size, website, company_address,
                company_email, company_reg_no, about_company
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, email, phone, password,
            company_name, industry, company_size, website, company_address,
            company_email, company_reg_no, about_company
        ))

        con.commit()
        con.close()

        flash("Recruiter Registered Successfully! Login Now.", "success")
        return redirect('/recruiter_login')

    return render_template('recruiter_register.html')


@app.route('/recruiter_login', methods=['GET','POST'])
def recruiter_login():
    if request.method=="POST":
        con=db(); cur=con.cursor()
        cur.execute("SELECT * FROM recruiters WHERE email=? AND password=?",
                    (request.form['email'], request.form['password']))
        user=cur.fetchone()
        if user and user['blocked']==0:
            session['recruiter']=user['id']
            return redirect('/recruiter_dashboard')
        return "Blocked or Invalid Login"
    return render_template("recruiter_login.html")
    
@app.route('/fake_recruiters')
def fake_recruiters():
    if 'admin' not in session:
        return redirect('/admin_login')

    import sqlite3
    con = sqlite3.connect("database.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT r.id as recruiter_id,
               r.name,
               r.blocked,
               j.description,
               j.employment_type
        FROM recruiters r
        JOIN jobs j ON r.id = j.recruiter_id
        WHERE j.model_result = "FAKE"
        ORDER BY j.created_at DESC
    """)

    data = cur.fetchall()
    con.close()

    return render_template("fake_recruiter.html", data=data)

@app.route('/toggle_block/<int:recruiter_id>')
def toggle_block(recruiter_id):
    if 'admin' not in session:
        return redirect('/admin_login')

    import sqlite3
    con = sqlite3.connect("database.db")
    cur = con.cursor()

    # Get current status
    cur.execute("SELECT blocked FROM recruiters WHERE id=?", (recruiter_id,))
    status = cur.fetchone()[0]

    new_status = 0 if status == 1 else 1

    cur.execute("UPDATE recruiters SET blocked=? WHERE id=?",
                (new_status, recruiter_id))

    con.commit()
    con.close()

    return redirect('/fake_recruiters')


@app.route('/recruiter_dashboard')
def recruiter_dashboard():
    if 'recruiter' not in session:
        return redirect('/recruiter_login')
    return render_template("recruiter_dashboard.html")

@app.route('/post_job', methods=['GET','POST'])
def post_job():
    if request.method == 'POST':
        form = request.form
        import pickle
        from scipy.sparse import hstack

        model = pickle.load(open("model/mlp_fake_job.pkl", "rb"))
        tfidf = pickle.load(open("model/tfidf.pkl", "rb"))
        encoder = pickle.load(open("model/encoder.pkl", "rb"))

        description = form["description"]

        text_vec = tfidf.transform([description])

        cat_data = [[
            form["employment_type"],
            form["required_experience"],
            form["required_education"],
            form["function"]
        ]]

        cat_vec = encoder.transform(cat_data)

        bin_data = [[
            int(form["telecommuting"]),
            int(form["has_company_logo"]),
            int(form["has_questions"])
        ]]

        final_input = hstack([text_vec, cat_vec, bin_data])

        prob = model.predict_proba(final_input)[0][1]
        result = "FAKE" if prob > 0.5 else "REAL"

        # -------------------------
        # SAVE ONLY REQUIRED FIELDS
        # -------------------------
        con = sqlite3.connect("database.db")
        cur = con.cursor()

        cur.execute("""
            INSERT INTO jobs (
                recruiter_id,
                description,
                employment_type,
                model_result,
                fake_score
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            session['recruiter'],
            form['description'],
            form['employment_type'],
            result,
            round(prob * 100, 2)
        ))

        con.commit()
        con.close()

        flash("Job posted successfully. Awaiting admin review.", "success")
        return redirect('/recruiter_dashboard')

    return render_template("post_job.html")



@app.route('/recruiter_jobs1')
def recruiter_jobs1():
    con=db(); cur=con.cursor()
    cur.execute("SELECT * FROM jobs WHERE recruiter_id=?", (session['recruiter'],))
    data=cur.fetchall()
    return render_template("recruiter_jobs1.html", data=data)
@app.route('/recruiter_jobs')
def recruiter_jobs():
    con=db(); cur=con.cursor()
    cur.execute("SELECT * FROM jobs WHERE recruiter_id=?", (session['recruiter'],))
    data=cur.fetchall()
    return render_template("recruiter_jobs.html", data=data)

@app.route('/view_applicants/<int:job_id>')
def view_applicants(job_id):
    con=db(); cur=con.cursor()
    cur.execute("""SELECT seekers.*, applications.id 
                   FROM applications 
                   JOIN seekers ON seekers.id=applications.seeker_id 
                   WHERE applications.job_id=?""", (job_id,))
    data=cur.fetchall()
    return render_template("view_applicants.html", data=data)

@app.route('/send_call/<int:seeker_id>')
def send_call(seeker_id):
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO inbox(seeker_id,message) VALUES(?,?)",
                (seeker_id, "You are shortlisted for interview."))
    con.commit()
    return redirect('/recruiter_dashboard')

# ---------------- JOB SEEKER ----------------

@app.route('/seeker_register', methods=['GET','POST'])
def seeker_register():
    if request.method=="POST":
        con=db(); cur=con.cursor()
        cur.execute("""
        INSERT INTO seekers(
            name,email,phone,school,school_year,
            college,degree,stream,skills,
            experience,certifications,password
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form['name'],
            request.form['email'],
            request.form['phone'],
            request.form['school'],
            request.form['school_year'],
            request.form['college'],
            request.form['degree'],
            request.form['stream'],
            request.form['skills'],
            request.form['experience'],
            request.form['certifications'],
            request.form['password']
        ))
        con.commit()
        return redirect('/seeker_login')

    return render_template("seeker_register.html")


@app.route('/seeker_login', methods=['GET','POST'])
def seeker_login():
    if request.method=="POST":
        con=db(); cur=con.cursor()
        cur.execute("SELECT * FROM seekers WHERE email=? AND password=?",
                    (request.form['email'], request.form['password']))
        user=cur.fetchone()
        if user:
            session['seeker']=user['id']
            return redirect('/seeker_dashboard')
        return "Invalid Login"
    return render_template("seeker_login.html")

@app.route('/seeker_dashboard')
def seeker_dashboard():
    if 'seeker' not in session:
        return redirect('/seeker_login')
    return render_template("seeker_dashboard.html")


@app.route('/seeker_jobs')
def seeker_jobs():
    con = db()
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT jobs.*
        FROM jobs
        JOIN recruiters ON recruiters.id = jobs.recruiter_id
        WHERE jobs.model_result = "REAL"
        AND recruiters.blocked = 0
        ORDER BY jobs.created_at DESC
    """)

    data = cur.fetchall()
    con.close()

    return render_template("seeker_jobs.html", data=data)

@app.route('/apply/<int:job_id>')
def apply(job_id):
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO applications(job_id,seeker_id) VALUES(?,?)",
                (job_id, session['seeker']))
    con.commit()
    return redirect('/seeker_jobs')
    
@app.route('/applied_jobs')
def applied_jobs():

    con = db()
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT jobs.description, jobs.employment_type,jobs.created_at
        FROM applications
        JOIN jobs ON jobs.id = applications.job_id
        WHERE applications.seeker_id = ?
    """, (session['seeker'],))

    data = cur.fetchall()

    return render_template("applied_jobs.html", data=data)

@app.route('/inbox')
def inbox():
    con=db(); cur=con.cursor()
    cur.execute("SELECT * FROM inbox WHERE seeker_id=?", (session['seeker'],))
    data=cur.fetchall()
    return render_template("inbox.html", data=data)
    
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == "__main__":
    app.run(debug=True)
