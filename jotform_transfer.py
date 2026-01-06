#################################  From GEMINI - Finally Working code #################################
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
    "select_current": '9'   # Filter Field
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
    "edit_link_field": '17' # Field ID for the Edit Link in Form 2
}

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
    field_data = answers.get(field_id)
    if not field_data:
        return None
    if isinstance(field_data, dict):
        return field_data.get('answer') or field_data.get('text') or field_data.get('prettyFormat')
    return str(field_data)

def update_edit_link(submission_id):
    """Generates the Jotform edit link and updates the submission field."""
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
def get_eligible_form1_data(num_records=1, api_search_limit=100):
    url = f"https://api.jotform.com/form/{FORM1_ID}/submissions"
    params = {
        "apiKey": API_KEY,
        "limit": api_search_limit,
        "orderby": "created_at",
        "direction": "DESC"
    }

    data = fetch_json(url, params)
    if not data or data.get("responseCode") != 200:
        print("Error fetching Form1 submissions")
        return []

    extracted = []
    for submission in data.get("content", []):
        if len(extracted) >= num_records:
            break

        answers = submission.get("answers", {})

        # Operation filter
        operation = get_field_value(answers, FORM1_FIELDS["operation"])
        if not operation or "New VM Installation" not in operation:
            continue

        # Select Current Stage filter
        select_current = get_field_value(answers, FORM1_FIELDS["select_current"])
        if not select_current or select_current.strip() not in ALLOWED_SELECT_CURRENT_VALUES:
            continue

        # Lead Code
        lead_code = get_field_value(answers, FORM1_FIELDS["lead_code"])
        if not lead_code or not lead_code.strip():
            continue

        extracted.append({
            "submission_id": submission.get("id"),
            "date": submission.get("created_at"),
            "operation": operation,
            "select_current": select_current.strip(),
            "lead_code": lead_code.strip(),
            "client_name": (get_field_value(answers, FORM1_FIELDS["client_name"]) or "").strip(),
            "client_email": (get_field_value(answers, FORM1_FIELDS["client_email"]) or "").strip(),
            "client_info": (get_field_value(answers, FORM1_FIELDS["client_info"]) or "").strip(),
            "account_team": (get_field_value(answers, FORM1_FIELDS["account_team"]) or "").strip()
        })

    print(f"Fetched {len(extracted)} eligible Form1 records.")
    return extracted

def get_existing_form2_lead_codes(api_search_limit=100):
    url = f"https://api.jotform.com/form/{FORM2_ID}/submissions"
    params = {"apiKey": API_KEY, "limit": api_search_limit}
    data = fetch_json(url, params)
    lead_codes = set()

    if data and data.get("responseCode") == 200:
        for submission in data.get("content", []):
            if submission.get("status") == "ACTIVE":
                answers = submission.get("answers", {})
                lc = get_field_value(answers, FORM2_FIELDS["lead_code"])
                if lc: lead_codes.add(lc.strip())
    return lead_codes

# --- Transfer Logic ---
def preview_and_transfer(num_records=1):
    print(f"\nPREVIEW & TRANSFER - Latest {num_records} records")
    existing_leads = get_existing_form2_lead_codes()
    form1_data = get_eligible_form1_data(num_records)

    eligible_for_transfer = [r for r in form1_data if r["lead_code"] not in existing_leads]

    print(f"Total Eligible Records for Transfer: {len(eligible_for_transfer)}")

    print("\n--- STARTING DATA TRANSFER ---")
    for record in eligible_for_transfer:
        # Correctly split date for Jotform Date field (YYYY-MM-DD)
        date_parts = ["", "", ""]
        if record["date"]:
            date_parts = record["date"].split(' ')[0].split('-')

        # DATA WRAPPED IN submission[...] ARRAY
        data_to_send = {
            f"submission[{FORM2_FIELDS['lead_code']}]": record["lead_code"],
            f"submission[{FORM2_FIELDS['client_name']}]": record["client_name"],
            f"submission[{FORM2_FIELDS['client_email']}]": record["client_email"],
            f"submission[{FORM2_FIELDS['client_info']}]": record["client_info"],
            f"submission[{FORM2_FIELDS['account_team']}]": record["account_team"],
            f"submission[{FORM2_FIELDS['original_submission_date']}_year]": date_parts[0],
            f"submission[{FORM2_FIELDS['original_submission_date']}_month]": date_parts[1],
            f"submission[{FORM2_FIELDS['original_submission_date']}_day]": date_parts[2]
        }

        print(f"\n[TRANSFERRING] Lead Code: {record['lead_code']}")
        url = f"https://api.jotform.com/form/{FORM2_ID}/submissions?apiKey={API_KEY}"
        response = post_json(url, data_to_send)

        if response.get("responseCode") == 200:
            new_id = response.get("content", {}).get("submissionID")
            print(f"  ✅ SUCCESS: New Submission ID {new_id}")
            update_edit_link(new_id)
        else:
            print(f"  ❌ ERROR: {response.get('message', 'Unknown error')}")
        
        time.sleep(1) # Safety delay

if __name__ == "__main__":
    print("JotForm Transfer Tool (Fixed Logic)\n" + "=" * 60)
    preview_and_transfer(100)
