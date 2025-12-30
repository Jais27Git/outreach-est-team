## form edit link gpt + FInal Working scrpit that checks for dupliates too
import requests
import time

API_KEY = "9325af147f76da4e263d7c7725d84654"  # updated API Key
FORM1_ID = "251590768630059"  # Source form
FORM2_ID = "252653470298060"  # Destination form

# --- Form1 Fields ---
FORM1_FIELDS = {
    "operation": '3',       # selectOperation
    "client_name": '15',
    "client_email": '17',
    "client_info": '26',
    "lead_code": '251',     # hidden field
    "account_team": '50'
}

# --- Form2 Fields ---
FORM2_FIELDS = {
    "lead_code": '3',
    "client_name": '5',
    "client_email": '12',
    "client_info": '8',
    "account_team": '15',
    "original_submission_date": '18'
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

# --- Form1 Data Extraction ---
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
        print(f"Error fetching Form1 submissions: {data.get('message', 'Unknown error') if data else ''}")
        return []

    extracted = []
    for submission in data.get("content", []):
        if len(extracted) >= num_records:
            break

        answers = submission.get("answers", {})
        operation = get_field_value(answers, FORM1_FIELDS["operation"])
        if not operation or "New VM Installation" not in operation:
            continue

        lead_code = get_field_value(answers, FORM1_FIELDS["lead_code"])
        if not lead_code or not lead_code.strip():
            continue

        extracted.append({
            "submission_id": submission.get("id"),
            "date": submission.get("created_at"),
            "operation": operation,
            "lead_code": lead_code.strip(),
            "client_name": (get_field_value(answers, FORM1_FIELDS["client_name"]) or "").strip(),
            "client_email": (get_field_value(answers, FORM1_FIELDS["client_email"]) or "").strip(),
            "client_info": (get_field_value(answers, FORM1_FIELDS["client_info"]) or "").strip(),
            "account_team": (get_field_value(answers, FORM1_FIELDS["account_team"]) or "").strip()
        })

    print(f"Fetched {len(extracted)} eligible Form1 records (latest first).")
    return extracted

# --- Form2 Submission ---
def submit_to_form2(record):
    url = f"https://api.jotform.com/form/{FORM2_ID}/submissions?apiKey={API_KEY}"
    date_parts = ["", "", ""]
    if record["date"]:
        try:
            date_parts = record["date"].split(' ')[0].split('-')
        except ValueError:
            pass

    data = {
        f"submission[{FORM2_FIELDS['lead_code']}]": record["lead_code"],
        f"submission[{FORM2_FIELDS['client_name']}]": record["client_name"],
        f"submission[{FORM2_FIELDS['client_email']}]": record["client_email"],
        f"submission[{FORM2_FIELDS['client_info']}]": record["client_info"],
        f"submission[{FORM2_FIELDS['account_team']}]": record["account_team"],
        f"submission[{FORM2_FIELDS['original_submission_date']}_day]": date_parts[2],
        f"submission[{FORM2_FIELDS['original_submission_date']}_month]": date_parts[1],
        f"submission[{FORM2_FIELDS['original_submission_date']}_year]": date_parts[0]
    }

    data = {k: v for k, v in data.items() if v}
    response = post_json(url, data)

    if response.get("responseCode") == 200:
        content = response.get("content", {})
        return True, content.get("id", content.get("submissionID", "Unknown"))
    else:
        return False, response.get("message") or response.get("error", "Unknown error")

# --- Update Edit Link in Form2 ---
def update_edit_link(submission_id):
    edit_link_field_id = "17"
    edit_link = f"https://www.jotform.com/edit/{submission_id}"
    url = f"https://api.jotform.com/submission/{submission_id}?apiKey={API_KEY}"
    data = {f"submission[{edit_link_field_id}]": edit_link}

    response = requests.post(url, data=data)
    try:
        response.raise_for_status()
        print(f"    🔗 Edit link updated: {edit_link}")
    except requests.exceptions.RequestException as e:
        print(f"    ❌ Failed to update edit link for submission {submission_id}: {e}")

# --- Fetch Existing Lead Codes in Form2 ---
def get_existing_form2_lead_codes(api_search_limit=1000):
    print("Fetching existing Lead Codes from Form2 (ignoring deleted/archived)...")
    url = f"https://api.jotform.com/form/{FORM2_ID}/submissions"
    params = {
        "apiKey": API_KEY,
        "limit": api_search_limit,
        "orderby": "created_at",
        "direction": "DESC"
    }
    data = fetch_json(url, params)
    lead_codes = set()
    if data and data.get("responseCode") == 200:
        for submission in data.get("content", []):
            if submission.get("status") != "ACTIVE":
                continue
            answers = submission.get("answers", {})
            lead_code = get_field_value(answers, FORM2_FIELDS["lead_code"])
            if lead_code:
                lead_codes.add(lead_code.strip())
    print(f"Found {len(lead_codes)} active Lead Codes in Form2.")
    return lead_codes

# --- Transfer Logic ---
def transfer_data(num_records=1):
    print(f"\nTransferring latest {num_records} 'New VM Installation' records...")

    existing_leads = get_existing_form2_lead_codes(api_search_limit=1000)
    form1_data = get_eligible_form1_data(num_records + 50, api_search_limit=200)  # extra buffer
    if not form1_data:
        print("No eligible Form1 records found.")
        return

    records_to_transfer = []
    skipped_duplicates = 0
    for record in form1_data:
        if record['lead_code'] in existing_leads:
            print(f"Duplicate found: Lead Code {record['lead_code']} already exists in Form2.")
            skipped_duplicates += 1
            print("Stopping further processing due to chronological order assumption.")
            break
        records_to_transfer.append(record)

    if not records_to_transfer:
        print("No new records to transfer after filtering duplicates.")
        return

    successful, failed = 0, 0
    for record in records_to_transfer:
        print(f"Processing Lead Code: {record['lead_code']} (Form1 ID: {record['submission_id']})")
        success, result = submit_to_form2(record)
        if success:
            print(f"  ✅ Success! New Form2 ID: {result}")
            update_edit_link(result)  # <-- NEW: Update edit link immediately
            successful += 1
        else:
            print(f"  ❌ Failed: {result}")
            failed += 1
        time.sleep(1)

    total = len(records_to_transfer)
    print(f"\nTRANSFER SUMMARY\n{'='*40}")
    print(f"Total processed: {total}")
    print(f"Successfully transferred: {successful}")
    print(f"Failed: {failed}")
    print(f"Skipped duplicates (and stopped early): {skipped_duplicates}")
    print(f"Success rate: {(successful/total)*100:.1f}%")

# --- Preview ---
def preview_data(num_records=1):
    print(f"\nPREVIEW - Latest {num_records} records (no transfer)")

    existing_leads = get_existing_form2_lead_codes(api_search_limit=1000)
    form1_data = get_eligible_form1_data(num_records + 50, api_search_limit=200)

    if not form1_data:
        print("No eligible records found for preview.")
        return

    records_to_preview = []
    for record in form1_data:
        if record['lead_code'] in existing_leads:
            print(f"Duplicate found: Lead Code {record['lead_code']} already exists in Form2.")
            break
        records_to_preview.append(record)

    for i, record in enumerate(records_to_preview, 1):
        print(f"\nRecord {i}")
        print(f"  Lead Code: {record['lead_code']}")
        print(f"  Client Name: {record['client_name']}")
        print(f"  Client Email: {record['client_email']}")
        print(f"  Client Info: {record['client_info']}")
        print(f"  Account Team: {record['account_team']}")
        print(f"  Original Submission Date: {record['date'].split(' ')[0] if record['date'] else ''}")

# --- Main Execution ---
if __name__ == "__main__":
    print("JotForm Data Transfer Tool\n" + "="*60)
    RECORDS_TO_PROCESS = 300

    transfer_data(RECORDS_TO_PROCESS)
    preview_data(RECORDS_TO_PROCESS)
