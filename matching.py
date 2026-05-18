"""
Brokerhaus — Match Scoring Algorithm

Score breakdown (total = 100):
  - Department match            : 20
  - Required functions overlap  : 35
  - Seniority match             : 15
  - Total years of experience   : 15
  - Function-specific years     : 10
  - Availability bonus          : 5
"""

import json
from data.catalog import SENIORITY_RANK


def score_candidate(candidate_row, candidate_functions, criteria):
    """
    Compute match score for a single candidate.

    candidate_row: dict-like with primary_department, seniority, years_total, availability
    candidate_functions: list of dicts with department_id, function_name, years_in_function
    criteria: dict with department, functions (list), seniority_levels (list),
              min_years, max_years, function_years (dict of function->required years)
    """

    # === 1. Department match (20) ===
    dept_score = 0
    if criteria.get("department"):
        if candidate_row["primary_department"] == criteria["department"]:
            dept_score = 20
        else:
            # Bonus: candidate has functions from that department even if it's not their primary
            cand_depts = {cf["department_id"] for cf in candidate_functions}
            if criteria["department"] in cand_depts:
                dept_score = 10
    else:
        dept_score = 20  # No department filter = full score

    # === 2. Required functions overlap (35) ===
    fn_score = 0
    required_fns = criteria.get("functions") or []
    if required_fns:
        cand_fn_names = {cf["function_name"] for cf in candidate_functions}
        matched = sum(1 for fn in required_fns if fn in cand_fn_names)
        fn_score = (matched / len(required_fns)) * 35
    else:
        fn_score = 35

    # === 3. Seniority match (15) ===
    sen_score = 0
    levels = criteria.get("seniority_levels") or []
    cand_sen = candidate_row["seniority"]
    if levels and cand_sen:
        if cand_sen in levels:
            sen_score = 15
        else:
            # Adjacent levels get partial credit
            cand_rank = SENIORITY_RANK.get(cand_sen, -10)
            min_dist = min(
                abs(cand_rank - SENIORITY_RANK.get(lvl, 100))
                for lvl in levels
            )
            if min_dist == 1:
                sen_score = 10
            elif min_dist == 2:
                sen_score = 6
            elif min_dist == 3:
                sen_score = 3
    else:
        sen_score = 15

    # === 4. Total years of experience (15) ===
    yrs_score = 0
    min_y = criteria.get("min_years", 0) or 0
    max_y = criteria.get("max_years", 100) or 100
    cand_yrs = candidate_row["years_total"] or 0
    if min_y <= cand_yrs <= max_y:
        yrs_score = 15
    else:
        # Soft scoring outside the band
        if cand_yrs < min_y:
            gap = min_y - cand_yrs
        else:
            gap = cand_yrs - max_y
        if gap <= 1:
            yrs_score = 10
        elif gap <= 2:
            yrs_score = 6
        elif gap <= 3:
            yrs_score = 3
        else:
            yrs_score = 0

    # === 5. Function-specific years (10) ===
    fn_yrs_score = 0
    fn_yrs_req = criteria.get("function_years") or {}
    if fn_yrs_req:
        cand_yrs_map = {cf["function_name"]: cf["years_in_function"] for cf in candidate_functions}
        per_req = 10 / len(fn_yrs_req)
        for fn_name, req_yrs in fn_yrs_req.items():
            cand_yrs_for_fn = cand_yrs_map.get(fn_name, 0)
            if cand_yrs_for_fn >= req_yrs:
                fn_yrs_score += per_req
            elif cand_yrs_for_fn >= req_yrs - 1:
                fn_yrs_score += per_req * 0.6
    else:
        fn_yrs_score = 10

    # === 6. Availability (5) ===
    avail_score = 5 if candidate_row["availability"] == "available" else 0

    total = dept_score + fn_score + sen_score + yrs_score + fn_yrs_score + avail_score
    return {
        "total": round(total, 1),
        "breakdown": {
            "department": round(dept_score, 1),
            "functions": round(fn_score, 1),
            "seniority": round(sen_score, 1),
            "years": round(yrs_score, 1),
            "function_years": round(fn_yrs_score, 1),
            "availability": round(avail_score, 1),
        },
    }
