"""
Seed the database with sample candidates and firms for testing.
Usage: python seed.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import init_db, get_db
from auth import hash_password
from app import generate_candidate_code
import random

SAMPLE_CANDIDATES = [
    {
        "email": "ahmed.h@example.com", "name": "Ahmed Hassan", "phone": "+201001234567",
        "dept": "trading", "seniority": "Senior Specialist", "years": 7,
        "title": "Senior Equity Dealer", "company": "Pharos Holding",
        "desc": "Execute equity orders for retail and institutional clients, monitor trading screen, coordinate with operations.",
        "functions": [
            ("trading", "Execute buy/sell orders for clients"),
            ("trading", "Execute retail orders"),
            ("trading", "Execute institutional orders"),
            ("trading", "Monitor trading screen"),
            ("trading", "Record client orders"),
            ("trading", "Verify client limits before execution"),
            ("sales", "Coordinate between client and dealer"),
        ],
    },
    {
        "email": "mona.k@example.com", "name": "Mona Kamal", "phone": "+201112345678",
        "dept": "operations", "seniority": "Manager", "years": 11,
        "title": "Back Office Manager", "company": "EFG Hermes",
        "desc": "Manage back office team, oversee settlements, coordinate with clearing house and custody firms.",
        "functions": [
            ("operations", "Record executed trades"),
            ("operations", "Settle trades"),
            ("operations", "Clearing follow-up"),
            ("operations", "EGX operations follow-up"),
            ("operations", "Issue client statements"),
            ("operations", "Manage operations team"),
            ("operations", "Supervise back office"),
            ("operations", "Coordinate with clearing & custody firms"),
        ],
    },
    {
        "email": "youssef.m@example.com", "name": "Youssef Mohamed", "phone": "+201223456789",
        "dept": "margin", "seniority": "Specialist", "years": 4,
        "title": "Margin Officer", "company": "Beltone",
        "desc": "Monitor margin clients, calculate ratios, issue margin calls, follow up coverage.",
        "functions": [
            ("margin", "Track margin clients"),
            ("margin", "Calculate margin ratios"),
            ("margin", "Monitor margin limits"),
            ("margin", "Issue margin calls"),
            ("margin", "Follow up on margin call coverage"),
            ("margin", "Prepare margin reports"),
            ("risk", "Coordinate with margin team"),
        ],
    },
    {
        "email": "sara.a@example.com", "name": "Sara Ahmed", "phone": "+201334567890",
        "dept": "research", "seniority": "Senior Specialist", "years": 6,
        "title": "Equity Research Analyst", "company": "CI Capital",
        "desc": "Cover banking and real estate sectors. Build valuation models, write fundamental analysis reports.",
        "functions": [
            ("research", "Prepare fundamental analysis reports"),
            ("research", "Analyze listed companies"),
            ("research", "Analyze sectors"),
            ("research", "Build valuation models"),
            ("research", "Read financial statements"),
            ("research", "Prepare investment recommendations"),
            ("research", "Prepare daily market reports"),
        ],
    },
    {
        "email": "khaled.s@example.com", "name": "Khaled Samir", "phone": "+201445678901",
        "dept": "compliance", "seniority": "Section Head", "years": 9,
        "title": "Compliance Section Head", "company": "HC Securities",
        "desc": "Lead compliance team. Review account openings, monitor staff trading, liaise with FRA.",
        "functions": [
            ("compliance", "Monitor compliance with laws & regulations"),
            ("compliance", "Review account opening procedures"),
            ("compliance", "Review staff trading activity"),
            ("compliance", "Prepare reports for regulators"),
            ("compliance", "Track FRA observations"),
            ("compliance", "Supervise compliance function"),
            ("aml", "Apply KYC procedures"),
        ],
    },
    {
        "email": "nour.r@example.com", "name": "Nour Reda", "phone": "+201556789012",
        "dept": "sales", "seniority": "Manager", "years": 8,
        "title": "Senior Account Manager", "company": "Naeem Brokerage",
        "desc": "Manage VIP clients portfolio worth EGP 500M+. Direct relationship with HNW individuals.",
        "functions": [
            ("sales", "Manage VIP / high-net-worth clients"),
            ("sales", "Manage institutional clients"),
            ("sales", "Attract new clients"),
            ("sales", "Monitor client portfolios"),
            ("sales", "Track client investment needs"),
            ("sales", "Achieve sales targets"),
            ("sales", "Manage sales team"),
        ],
    },
]

SAMPLE_FIRMS = [
    {"email": "hr@pharos.com.eg", "name": "Pharos HR", "company": "Pharos Holding"},
    {"email": "hr@efghermes.com", "name": "EFG Recruitment", "company": "EFG Hermes"},
]


def seed():
    init_db()
    with get_db() as conn:
        # Wipe existing
        conn.execute("DELETE FROM candidate_functions")
        conn.execute("DELETE FROM nominations")
        conn.execute("DELETE FROM searches")
        conn.execute("DELETE FROM candidates")
        conn.execute("DELETE FROM firms")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM users")

        # Insert candidates
        for c in SAMPLE_CANDIDATES:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, role, full_name, phone) VALUES (?, ?, 'candidate', ?, ?)",
                (c["email"], hash_password("password123"), c["name"], c["phone"])
            )
            uid = cur.lastrowid
            code = generate_candidate_code()
            cur = conn.execute(
                """INSERT INTO candidates (user_id, code, primary_department, seniority,
                   company_job_title, current_company, work_description, years_total, availability)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'available')""",
                (uid, code, c["dept"], c["seniority"], c["title"], c["company"], c["desc"], c["years"])
            )
            cid = cur.lastrowid
            for dept_id, fn_name in c["functions"]:
                conn.execute(
                    """INSERT INTO candidate_functions (candidate_id, department_id, function_name, years_in_function)
                       VALUES (?, ?, ?, ?)""",
                    (cid, dept_id, fn_name, max(1, c["years"] - random.randint(0, 3)))
                )

        # Insert firms
        for f in SAMPLE_FIRMS:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, role, full_name) VALUES (?, ?, 'hr', ?)",
                (f["email"], hash_password("password123"), f["name"])
            )
            uid = cur.lastrowid
            conn.execute(
                "INSERT INTO firms (user_id, company_name, verified) VALUES (?, ?, 1)",
                (uid, f["company"])
            )

    print("✓ Seeded database")
    print(f"  - {len(SAMPLE_CANDIDATES)} candidates")
    print(f"  - {len(SAMPLE_FIRMS)} firms")
    print("\nLogin credentials (password for all: password123):")
    print("\nCandidates:")
    for c in SAMPLE_CANDIDATES:
        print(f"  {c['email']}  |  {c['name']}")
    print("\nFirms:")
    for f in SAMPLE_FIRMS:
        print(f"  {f['email']}  |  {f['company']}")


if __name__ == "__main__":
    seed()
