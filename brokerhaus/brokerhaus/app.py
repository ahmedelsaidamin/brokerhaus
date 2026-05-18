"""
Brokerhaus — Main Flask Application

A private hiring network for Egyptian securities brokerage firms.
"""

import os
import sys
import json
import secrets
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, make_response, abort, g, send_from_directory

# Make sure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import init_db, get_db, expire_old_nominations
from auth import (
    hash_password, verify_password, create_session, delete_session,
    get_current_user, login_required
)
from matching import score_candidate
from data.catalog import (
    DEPARTMENTS, SENIORITY_LEVELS, get_department, get_functions_for_department
)


app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB


# === Startup: init DB and expire stale nominations ===
init_db()
expire_old_nominations()


def generate_candidate_code():
    """Generate a unique C-NNNN code."""
    with get_db() as conn:
        for _ in range(20):
            code = f"C-{random.randint(1000, 9999)}"
            existing = conn.execute("SELECT 1 FROM candidates WHERE code = ?", (code,)).fetchone()
            if not existing:
                return code
    # Fallback if 9000 numbers exhausted
    return f"C-{secrets.token_hex(3).upper()}"


# === Global template context ===
@app.context_processor
def inject_globals():
    return {
        "current_user": get_current_user(),
        "departments": DEPARTMENTS,
        "seniority_levels": SENIORITY_LEVELS,
        "current_year": datetime.now().year,
    }


# ============================================================================
# Public pages
# ============================================================================

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ============================================================================
# Authentication
# ============================================================================

@app.route("/signup", methods=["GET"])
def signup_page():
    if get_current_user():
        return redirect(url_for("dashboard"))
    return render_template("signup.html", role=request.args.get("role", "candidate"))


@app.route("/api/signup", methods=["POST"])
def signup_api():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    role = data.get("role")
    company_name = (data.get("company_name") or "").strip()

    # Validation
    if not email or "@" not in email:
        return jsonify({"error": "invalid_email"}), 400
    if len(password) < 8:
        return jsonify({"error": "weak_password", "message": "Password must be at least 8 characters"}), 400
    if not full_name:
        return jsonify({"error": "missing_name"}), 400
    if role not in ("candidate", "hr"):
        return jsonify({"error": "invalid_role"}), 400
    if role == "hr" and not company_name:
        return jsonify({"error": "missing_company"}), 400

    with get_db() as conn:
        existing = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return jsonify({"error": "email_taken"}), 400

        cur = conn.execute(
            "INSERT INTO users (email, password_hash, role, full_name, phone) VALUES (?, ?, ?, ?, ?)",
            (email, hash_password(password), role, full_name, phone)
        )
        user_id = cur.lastrowid

        if role == "candidate":
            code = generate_candidate_code()
            conn.execute(
                "INSERT INTO candidates (user_id, code) VALUES (?, ?)",
                (user_id, code)
            )
        else:
            conn.execute(
                "INSERT INTO firms (user_id, company_name) VALUES (?, ?)",
                (user_id, company_name)
            )

    token = create_session(user_id)
    resp = jsonify({"ok": True, "redirect": url_for("dashboard")})
    resp.set_cookie("bh_session", token, max_age=30 * 86400, httponly=True, samesite="Lax")
    return resp


@app.route("/login", methods=["GET"])
def login_page():
    if get_current_user():
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/api/login", methods=["POST"])
def login_api():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "invalid_credentials"}), 401

    with get_db() as conn:
        conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))

    token = create_session(user["id"])
    resp = jsonify({"ok": True, "redirect": url_for("dashboard")})
    resp.set_cookie("bh_session", token, max_age=30 * 86400, httponly=True, samesite="Lax")
    return resp


@app.route("/logout")
def logout():
    token = request.cookies.get("bh_session")
    if token:
        delete_session(token)
    resp = redirect(url_for("landing"))
    resp.set_cookie("bh_session", "", max_age=0)
    return resp


# ============================================================================
# Dashboard router
# ============================================================================

@app.route("/dashboard")
@login_required()
def dashboard():
    user = get_current_user()
    if user["role"] == "candidate":
        return redirect(url_for("candidate_dashboard"))
    elif user["role"] == "hr":
        return redirect(url_for("hr_dashboard"))
    return abort(403)


# ============================================================================
# Candidate routes
# ============================================================================

@app.route("/candidate")
@login_required(role="candidate")
def candidate_dashboard():
    user = get_current_user()
    with get_db() as conn:
        cand = conn.execute("SELECT * FROM candidates WHERE user_id = ?", (user["id"],)).fetchone()
        functions = conn.execute(
            "SELECT * FROM candidate_functions WHERE candidate_id = ?",
            (cand["id"],)
        ).fetchall()

        # Pending nominations for this candidate
        nominations = conn.execute("""
            SELECT n.*, f.company_name FROM nominations n
            JOIN firms f ON f.id = n.firm_id
            WHERE n.candidate_id = ?
            ORDER BY n.created_at DESC
        """, (cand["id"],)).fetchall()

    profile_complete = bool(
        cand["primary_department"] and cand["seniority"] and cand["company_job_title"] and functions
    )

    return render_template(
        "candidate/dashboard.html",
        candidate=dict(cand),
        functions=[dict(f) for f in functions],
        nominations=[dict(n) for n in nominations],
        profile_complete=profile_complete,
    )


@app.route("/candidate/profile")
@login_required(role="candidate")
def candidate_profile_page():
    user = get_current_user()
    with get_db() as conn:
        cand = conn.execute("SELECT * FROM candidates WHERE user_id = ?", (user["id"],)).fetchone()
        functions = conn.execute(
            "SELECT * FROM candidate_functions WHERE candidate_id = ?",
            (cand["id"],)
        ).fetchall()

    selected_fns = [dict(f) for f in functions]
    return render_template(
        "candidate/profile.html",
        candidate=dict(cand),
        selected_functions=selected_fns,
    )


@app.route("/api/candidate/profile", methods=["POST"])
@login_required(role="candidate")
def candidate_profile_api():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    primary_department = data.get("primary_department")
    seniority = data.get("seniority")
    company_job_title = (data.get("company_job_title") or "").strip()
    current_company = (data.get("current_company") or "").strip()
    work_description = (data.get("work_description") or "").strip()
    years_total = int(data.get("years_total") or 0)
    availability = data.get("availability", "available")
    functions = data.get("functions") or []  # list of {department_id, function_name, years_in_function}

    if availability not in ("available", "not_available"):
        availability = "available"

    with get_db() as conn:
        cand = conn.execute("SELECT * FROM candidates WHERE user_id = ?", (user["id"],)).fetchone()
        if not cand:
            return jsonify({"error": "no_profile"}), 404

        conn.execute("""
            UPDATE candidates
            SET primary_department = ?, seniority = ?, company_job_title = ?,
                current_company = ?, work_description = ?, years_total = ?,
                availability = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (primary_department, seniority, company_job_title, current_company,
              work_description, years_total, availability, cand["id"]))

        # Replace functions
        conn.execute("DELETE FROM candidate_functions WHERE candidate_id = ?", (cand["id"],))
        for fn in functions:
            if not fn.get("function_name") or not fn.get("department_id"):
                continue
            conn.execute("""
                INSERT INTO candidate_functions (candidate_id, department_id, function_name, years_in_function)
                VALUES (?, ?, ?, ?)
            """, (cand["id"], fn["department_id"], fn["function_name"], int(fn.get("years_in_function") or 0)))

    return jsonify({"ok": True})


@app.route("/api/candidate/availability", methods=["POST"])
@login_required(role="candidate")
def candidate_availability_api():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    availability = data.get("availability")
    if availability not in ("available", "not_available"):
        return jsonify({"error": "invalid"}), 400
    with get_db() as conn:
        conn.execute(
            "UPDATE candidates SET availability = ? WHERE user_id = ?",
            (availability, user["id"])
        )
    return jsonify({"ok": True})


@app.route("/api/nomination/<int:nom_id>/respond", methods=["POST"])
@login_required(role="candidate")
def nomination_respond_api(nom_id):
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    action = data.get("action")  # 'accept' or 'decline'

    if action not in ("accept", "decline"):
        return jsonify({"error": "invalid_action"}), 400

    with get_db() as conn:
        cand = conn.execute("SELECT * FROM candidates WHERE user_id = ?", (user["id"],)).fetchone()
        nom = conn.execute(
            "SELECT * FROM nominations WHERE id = ? AND candidate_id = ?",
            (nom_id, cand["id"])
        ).fetchone()
        if not nom:
            return jsonify({"error": "not_found"}), 404
        if nom["status"] != "sent":
            return jsonify({"error": "already_responded"}), 400

        new_status = "accepted" if action == "accept" else "declined"
        conn.execute("""
            UPDATE nominations
            SET status = ?, responded_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, nom_id))

    return jsonify({"ok": True, "status": new_status})


# ============================================================================
# HR routes
# ============================================================================

@app.route("/hr")
@login_required(role="hr")
def hr_dashboard():
    user = get_current_user()
    with get_db() as conn:
        firm = conn.execute("SELECT * FROM firms WHERE user_id = ?", (user["id"],)).fetchone()

        # Stats
        stats = {}
        stats["total_sent"] = conn.execute(
            "SELECT COUNT(*) FROM nominations WHERE firm_id = ?", (firm["id"],)
        ).fetchone()[0]
        stats["accepted"] = conn.execute(
            "SELECT COUNT(*) FROM nominations WHERE firm_id = ? AND status = 'accepted'", (firm["id"],)
        ).fetchone()[0]
        stats["pending"] = conn.execute(
            "SELECT COUNT(*) FROM nominations WHERE firm_id = ? AND status = 'sent'", (firm["id"],)
        ).fetchone()[0]
        stats["declined"] = conn.execute(
            "SELECT COUNT(*) FROM nominations WHERE firm_id = ? AND status = 'declined'", (firm["id"],)
        ).fetchone()[0]

        # Recent nominations
        recent = conn.execute("""
            SELECT n.*, c.code, c.primary_department, c.seniority, c.years_total
            FROM nominations n
            JOIN candidates c ON c.id = n.candidate_id
            WHERE n.firm_id = ?
            ORDER BY n.created_at DESC
            LIMIT 10
        """, (firm["id"],)).fetchall()

    return render_template(
        "hr/dashboard.html",
        firm=dict(firm),
        stats=stats,
        recent=[dict(r) for r in recent],
    )


@app.route("/hr/search")
@login_required(role="hr")
def hr_search_page():
    return render_template("hr/search.html")


@app.route("/api/search", methods=["POST"])
@login_required(role="hr")
def search_api():
    data = request.get_json(silent=True) or {}
    department = data.get("department")
    functions = data.get("functions") or []
    seniority_levels = data.get("seniority_levels") or []
    min_years = int(data.get("min_years") or 0)
    max_years = int(data.get("max_years") or 50)
    function_years = data.get("function_years") or {}

    criteria = {
        "department": department,
        "functions": functions,
        "seniority_levels": seniority_levels,
        "min_years": min_years,
        "max_years": max_years,
        "function_years": function_years,
    }

    with get_db() as conn:
        # CRITICAL: only show available candidates
        candidates = conn.execute("""
            SELECT * FROM candidates
            WHERE availability = 'available'
              AND primary_department IS NOT NULL
              AND seniority IS NOT NULL
        """).fetchall()

        results = []
        for cand in candidates:
            cand_dict = dict(cand)
            fns = conn.execute(
                "SELECT * FROM candidate_functions WHERE candidate_id = ?",
                (cand["id"],)
            ).fetchall()
            fn_list = [dict(f) for f in fns]

            score = score_candidate(cand_dict, fn_list, criteria)
            if score["total"] < 30:
                continue  # skip very weak matches

            # Get short function summary (first 3)
            short_fns = ", ".join(f["function_name"] for f in fn_list[:3])
            if len(fn_list) > 3:
                short_fns += f" +{len(fn_list) - 3}"

            results.append({
                "candidate_id": cand_dict["id"],
                "code": cand_dict["code"],
                "department": cand_dict["primary_department"],
                "seniority": cand_dict["seniority"],
                "years_total": cand_dict["years_total"],
                "functions_summary": short_fns,
                "score": score["total"],
                "breakdown": score["breakdown"],
            })

    results.sort(key=lambda r: r["score"], reverse=True)
    return jsonify({"results": results, "count": len(results)})


@app.route("/api/nominate", methods=["POST"])
@login_required(role="hr")
def nominate_api():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    candidate_ids = data.get("candidate_ids") or []
    criteria = data.get("criteria") or {}
    role_summary = (data.get("role_summary") or "").strip()

    if not candidate_ids:
        return jsonify({"error": "no_candidates"}), 400

    with get_db() as conn:
        firm = conn.execute("SELECT * FROM firms WHERE user_id = ?", (user["id"],)).fetchone()

        expires = datetime.now() + timedelta(days=30)
        sent = 0
        skipped = 0
        for cid in candidate_ids:
            # Don't send duplicate active nominations from the same firm
            existing = conn.execute("""
                SELECT 1 FROM nominations
                WHERE firm_id = ? AND candidate_id = ? AND status = 'sent'
            """, (firm["id"], cid)).fetchone()
            if existing:
                skipped += 1
                continue

            conn.execute("""
                INSERT INTO nominations (
                    firm_id, candidate_id, role_summary,
                    required_department, required_functions,
                    required_seniority, required_years,
                    expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                firm["id"], cid, role_summary,
                criteria.get("department"),
                json.dumps(criteria.get("functions") or []),
                json.dumps(criteria.get("seniority_levels") or []),
                criteria.get("min_years") or 0,
                expires
            ))
            sent += 1

    return jsonify({"ok": True, "sent": sent, "skipped": skipped})


@app.route("/hr/nominations")
@login_required(role="hr")
def hr_nominations_page():
    user = get_current_user()
    with get_db() as conn:
        firm = conn.execute("SELECT * FROM firms WHERE user_id = ?", (user["id"],)).fetchone()
        nominations = conn.execute("""
            SELECT n.*, c.code, c.primary_department, c.seniority, c.years_total, c.work_description,
                   CASE WHEN n.status = 'accepted' THEN u.full_name ELSE NULL END AS revealed_name,
                   CASE WHEN n.status = 'accepted' THEN u.email ELSE NULL END AS revealed_email,
                   CASE WHEN n.status = 'accepted' THEN u.phone ELSE NULL END AS revealed_phone,
                   CASE WHEN n.status = 'accepted' THEN c.company_job_title ELSE NULL END AS revealed_title,
                   CASE WHEN n.status = 'accepted' THEN c.current_company ELSE NULL END AS revealed_company
            FROM nominations n
            JOIN candidates c ON c.id = n.candidate_id
            JOIN users u ON u.id = c.user_id
            WHERE n.firm_id = ?
            ORDER BY
                CASE n.status WHEN 'accepted' THEN 1 WHEN 'sent' THEN 2 WHEN 'declined' THEN 3 ELSE 4 END,
                n.created_at DESC
        """, (firm["id"],)).fetchall()

    return render_template(
        "hr/nominations.html",
        firm=dict(firm),
        nominations=[dict(n) for n in nominations],
    )


# ============================================================================
# Catalog API (used by frontend forms)
# ============================================================================

@app.route("/api/catalog/departments")
def catalog_departments():
    return jsonify({"departments": DEPARTMENTS})


@app.route("/api/catalog/functions/<dept_id>")
def catalog_functions(dept_id):
    dept = get_department(dept_id)
    if not dept:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"functions": dept["functions"], "department": dept})


@app.route("/api/catalog/seniority")
def catalog_seniority():
    return jsonify({"levels": SENIORITY_LEVELS})


# ============================================================================
# Error handlers
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Forbidden"), 403


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Something went wrong"), 500


# ============================================================================
# Health
# ============================================================================

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
