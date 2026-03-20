################# By Ankit.Kumar ################
# Jotform Bulk Transfer Script v5
# Purpose: Transfer eligible submissions from Form 1 (251590768630059) to Form 2 (252653470298060)
# Filters: Operation = "New VM Installation" AND select_current in allowed stages
#          AND status = ACTIVE only (skips DELETED and ARCHIVED submissions)
# Behavior:
#   Case 1: Lead code NOT in Form 2 → CREATE full new submission with all fields
#   Case 2: Lead code EXISTS in Form 2 → Check if any of the 5 new fields are empty
#           → If any are missing AND Form 1 has data → UPDATE only those missing fields
#   Note: If a field is empty in Form 1, it is never written to Form 2 (kept blank)
# Fix: 'text' removed from get_field_value — it is the field label, not the answer
# API: Jotform REST API with pagination (200 records/batch)
# Output: Creates new submissions OR patches missing fields in existing ones
#################################################################################################

import requests
import time

API_KEY = "9325af147f76da4e263d7c7725d84654"
FORM1_ID = "251590768630059"
FORM2_ID = "252653470298060"

# --- Form1 Fields ---
FORM1_FIELDS = {
    "operation": '3',
    "client_name": '15',
    "client_email": '17',
    "client_info": '26',
    "lead_code": '251',
    "account_team": '50',
    "select_current": '9',
    "form_filled_by": '84',
    "spoc_name": '85',
    "spoc_email": '86',
    "commercial_model": '51',    # Radio button field (51_0, 51_1, 51_2, 51_3 - single selection)
    "rental_amount": '89'
}

ALLOWED_SELECT_CURRENT_VALUES = {
    "Stage - Update Refilling Status",
    "Stage - Ads-Cohort Update (Growth)"
}

# --- Form2 Fields ---
FORM2_FIELDS = {
    "lead_code": '3',
    "client_name": '5',
    "client_email": '12',
    "client_info": '8',
    "account_team": '15',
    "original_submission_date": '18',
    "edit_link_field": '17',
    "form_filled_by": '26',
    "spoc_name": '27',
    "spoc_email": '28',
    "commercial_model": '30',
    "rental_amount": '31'
}

NEW_FIELDS = ["form_filled_by", "spoc_name", "spoc_email", "commercial_model", "rental_amount"]

# --- Helper Functions ---
def fetch_json(url, params=None):
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None

def post_json(url, data):
    try:
        resp = requests.post(url, data=data)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def get_field_value(answers, field_id):
    """
    Extract field value from Jotform submission answers.
    'text' is NOT used as fallback — it is the field label, not the answer.
    When a field has no answer, Jotform returns metadata dict without 'answer' key → returns None.
    """
    field_data = answers.get(field_id)
    if not field_data:
        return None
    if isinstance(field_data, list):
        return field_data[0] if field_data else None
    if isinstance(field_data, dict):
        return field_data.get('answer') or field_data.get('prettyFormat')
    return str(field_data)

def update_edit_link(submission_id):
    edit_link = f"https://www.jotform.com/edit/{submission_id}"
    url = f"https://api.jotform.com/submission/{submission_id}?apiKey={API_KEY}"
    data = {f"submission[{FORM2_FIELDS['edit_link_field']}]": edit_link}
    try:
        resp = requests.post(url, data=data)
        resp.raise_for_status()
        print(f"    🔗 Edit link updated: {edit_link}")
    except Exception as e:
        print(f"    ❌ Failed to update edit link: {e}")

# --- Data Extraction ---
def get_eligible_form1_data():
    """Fetch ALL eligible ACTIVE Form1 submissions using pagination (200 records/batch)"""
    url = f"https://api.jotform.com/form/{FORM1_ID}/submissions"
    extracted = []
    offset = 0
    limit = 200

    print("\n📥 Fetching Form1 submissions...")

    while True:
        params = {
            "apiKey": API_KEY,
            "limit": limit,
            "offset": offset,
            "orderby": "created_at",
            "direction": "DESC"
        }

        print(f"  Batch: offset={offset}, limit={limit}")
        data = fetch_json(url, params)

        if not data or data.get("responseCode") != 200:
            print("  ❌ Error fetching Form1 submissions")
            break

        submissions = data.get("content", [])
        if not submissions:
            print("  ✅ No more submissions")
            break

        for submission in submissions:

            # Skip deleted or archived
            if submission.get("status") != "ACTIVE":
                continue

            answers = submission.get("answers", {})

            # Operation filter
            operation = get_field_value(answers, FORM1_FIELDS["operation"])
            if not operation or "New VM Installation" not in operation:
                continue

            # Stage filter
            select_current = get_field_value(answers, FORM1_FIELDS["select_current"])
            if not select_current or select_current.strip() not in ALLOWED_SELECT_CURRENT_VALUES:
                continue

            # Lead code required
            lead_code = get_field_value(answers, FORM1_FIELDS["lead_code"])
            if not lead_code or not lead_code.strip():
                continue

            extracted.append({
                "submission_id":    submission.get("id"),
                "date":             submission.get("created_at"),
                "lead_code":        lead_code.strip(),
                "client_name":      (get_field_value(answers, FORM1_FIELDS["client_name"]) or "").strip(),
                "client_email":     (get_field_value(answers, FORM1_FIELDS["client_email"]) or "").strip(),
                "client_info":      (get_field_value(answers, FORM1_FIELDS["client_info"]) or "").strip(),
                "account_team":     (get_field_value(answers, FORM1_FIELDS["account_team"]) or "").strip(),
                "form_filled_by":   (get_field_value(answers, FORM1_FIELDS["form_filled_by"]) or "").strip(),
                "spoc_name":        (get_field_value(answers, FORM1_FIELDS["spoc_name"]) or "").strip(),
                "spoc_email":       (get_field_value(answers, FORM1_FIELDS["spoc_email"]) or "").strip(),
                "commercial_model": (get_field_value(answers, FORM1_FIELDS["commercial_model"]) or "").strip(),
                "rental_amount":    (get_field_value(answers, FORM1_FIELDS["rental_amount"]) or "").strip()
            })

        print(f"  📊 {len(submissions)} fetched, {len(extracted)} eligible so far")

        if len(submissions) < limit:
            print("  ✅ Reached end of Form1")
            break

        offset += limit
        time.sleep(0.5)

    print(f"\n✅ Total eligible Form1 records: {len(extracted)}")
    return extracted


def get_existing_form2_data():
    """
    Fetch ALL ACTIVE Form2 submissions using pagination (200 records/batch).
    Returns: { lead_code: { "submission_id": ..., "answers": ... } }
    """
    url = f"https://api.jotform.com/form/{FORM2_ID}/submissions"
    lead_map = {}
    offset = 0
    limit = 200

    print("\n📥 Fetching Form2 submissions...")

    while True:
        params = {
            "apiKey": API_KEY,
            "limit": limit,
            "offset": offset
        }

        print(f"  Batch: offset={offset}, limit={limit}")
        data = fetch_json(url, params)

        if not data or data.get("responseCode") != 200:
            print("  ❌ Error fetching Form2 submissions")
            break

        submissions = data.get("content", [])
        if not submissions:
            print("  ✅ No more submissions")
            break

        for submission in submissions:
            # Skip deleted or archived
            if submission.get("status") != "ACTIVE":
                continue

            answers = submission.get("answers", {})
            lc = get_field_value(answers, FORM2_FIELDS["lead_code"])
            if lc:
                lead_map[lc.strip()] = {
                    "submission_id": submission.get("id"),
                    "answers": answers
                }

        print(f"  📊 {len(submissions)} fetched, {len(lead_map)} unique lead codes so far")

        if len(submissions) < limit:
            print("  ✅ Reached end of Form2")
            break

        offset += limit
        time.sleep(0.5)

    print(f"\n✅ Total existing lead codes in Form2: {len(lead_map)}")
    return lead_map


# --- Transfer Logic ---
def run_transfer():
    print("\n" + "=" * 60)
    print("JOTFORM BULK TRANSFER & UPDATE v5")
    print("=" * 60)

    existing_form2 = get_existing_form2_data()
    form1_data = get_eligible_form1_data()

    created_success = 0
    created_failed  = 0
    updated_success = 0
    updated_failed  = 0
    skipped         = 0

    print("\n--- STARTING TRANSFER ---")

    for record in form1_data:
        lead_code = record["lead_code"]

        # -----------------------------------------------------------
        # CASE 1: Lead not in Form 2 → CREATE new submission
        # -----------------------------------------------------------
        if lead_code not in existing_form2:
            date_parts = ["", "", ""]
            if record["date"]:
                date_parts = record["date"].split(' ')[0].split('-')

            data_to_send = {
                f"submission[{FORM2_FIELDS['lead_code']}]":                      record["lead_code"],
                f"submission[{FORM2_FIELDS['client_name']}]":                    record["client_name"],
                f"submission[{FORM2_FIELDS['client_email']}]":                   record["client_email"],
                f"submission[{FORM2_FIELDS['client_info']}]":                    record["client_info"],
                f"submission[{FORM2_FIELDS['account_team']}]":                   record["account_team"],
                f"submission[{FORM2_FIELDS['original_submission_date']}_year]":  date_parts[0],
                f"submission[{FORM2_FIELDS['original_submission_date']}_month]": date_parts[1],
                f"submission[{FORM2_FIELDS['original_submission_date']}_day]":   date_parts[2],
            }

            # New fields — only add if non-empty
            for field in NEW_FIELDS:
                if record[field]:
                    data_to_send[f"submission[{FORM2_FIELDS[field]}]"] = record[field]

            print(f"\n[CREATE] Lead Code: {lead_code}")
            print(f"  Client          : {record['client_name']}")
            print(f"  Form Filled By  : {record['form_filled_by'] or '(empty)'}")
            print(f"  SPOC            : {record['spoc_name'] or '(empty)'} / {record['spoc_email'] or '(empty)'}")
            print(f"  Commercial Model: {record['commercial_model'] or '(empty)'}")
            print(f"  Rental Amount   : {record['rental_amount'] or '(empty)'}")

            url = f"https://api.jotform.com/form/{FORM2_ID}/submissions?apiKey={API_KEY}"
            response = post_json(url, data_to_send)

            if response.get("responseCode") == 200:
                new_id = response.get("content", {}).get("submissionID")
                print(f"  ✅ CREATED: Submission ID {new_id}")
                update_edit_link(new_id)
                created_success += 1
            else:
                print(f"  ❌ CREATE FAILED: {response.get('message', 'Unknown error')}")
                created_failed += 1

        # -----------------------------------------------------------
        # CASE 2: Lead exists in Form 2 → Patch only missing fields
        # -----------------------------------------------------------
        else:
            existing = existing_form2[lead_code]
            submission_id = existing["submission_id"]
            existing_answers = existing["answers"]

            fields_to_patch = {}
            for field in NEW_FIELDS:
                form2_value = (get_field_value(existing_answers, FORM2_FIELDS[field]) or "").strip()
                form1_value = record[field]
                if not form2_value and form1_value:
                    fields_to_patch[field] = form1_value

            if not fields_to_patch:
                print(f"\n[SKIP] Lead Code: {lead_code} — nothing to update")
                skipped += 1
                continue

            update_data = {}
            for field, value in fields_to_patch.items():
                update_data[f"submission[{FORM2_FIELDS[field]}]"] = value

            print(f"\n[UPDATE] Lead Code: {lead_code} (Submission ID: {submission_id})")
            for field, value in fields_to_patch.items():
                print(f"  Patching {field}: {value}")

            url = f"https://api.jotform.com/submission/{submission_id}?apiKey={API_KEY}"
            response = post_json(url, update_data)

            if response.get("responseCode") == 200:
                print(f"  ✅ UPDATED")
                updated_success += 1
            else:
                print(f"  ❌ UPDATE FAILED: {response.get('message', 'Unknown error')}")
                updated_failed += 1

        time.sleep(1)

    print("\n" + "=" * 60)
    print("PROCESS COMPLETE")
    print("=" * 60)
    print(f"  🆕 Created  : {created_success}  (Failed: {created_failed})")
    print(f"  🔄 Updated  : {updated_success}  (Failed: {updated_failed})")
    print(f"  ⏭️  Skipped  : {skipped}")
    print(f"  📊 Total processed: {created_success + updated_success}")
    print("=" * 60)


if __name__ == "__main__":
    print("JotForm Transfer Tool v5\n" + "=" * 60)
    run_transfer()
