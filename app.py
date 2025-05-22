from flask import Flask, request, jsonify
import os
import requests
from urllib.parse import urlencode, unquote
from dotenv import load_dotenv
import json

load_dotenv()

app = Flask(__name__)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://localhost:5000/callback"
SCOPE = "ZohoCRM.modules.ALL,ZohoCRM.settings.modules.READ,ZohoCRM.settings.fields.READ"
TOKEN_FILE = "tokens.json"


def save_tokens(data):
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)


def load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return {}


def refresh_access_token():
    token_store = load_tokens()
    refresh_token = token_store.get("refresh_token")

    if not refresh_token:
        return None, "No refresh token found. Please authenticate via /auth first."

    token_url = "https://accounts.zoho.in/oauth/v2/token"
    refresh_params = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token
    }

    resp = requests.post(token_url, data=refresh_params)
    refresh_data = resp.json()

    if "access_token" not in refresh_data or "api_domain" not in refresh_data:
        return None, refresh_data.get("error", "Failed to refresh access token.")

    token_store["access_token"] = refresh_data["access_token"]
    token_store["api_domain"] = refresh_data["api_domain"]
    save_tokens(token_store)

    return refresh_data["access_token"], None


@app.route("/auth")
def authorize():
    base_url = "https://accounts.zoho.in/oauth/v2/auth"
    params = {
        "scope": SCOPE,
        "client_id": CLIENT_ID,
        "response_type": "code",
        "access_type": "offline",
        "redirect_uri": REDIRECT_URI,
        "prompt": "consent"
    }
    auth_url = f"{base_url}?{urlencode(params)}"
    readable_url = unquote(auth_url)
    return jsonify({"auth_url": readable_url})


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Authorization code not found"}), 400

    token_url = "https://accounts.zoho.in/oauth/v2/token"
    auth_params = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }

    try:
        auth_response = requests.post(token_url, data=auth_params)
        auth_data = auth_response.json()

        refresh_token = auth_data.get("refresh_token")
        access_token = auth_data.get("access_token")
        api_domain = auth_data.get("api_domain")

        if not refresh_token or not access_token or not api_domain:
            return jsonify({
                "auth_response": auth_data,
                "note": "Missing refresh_token, access_token or api_domain in auth response."
            }), 400

        token_store = {
            "refresh_token": refresh_token,
            "access_token": access_token,
            "api_domain": api_domain,
        }
        save_tokens(token_store)

        return jsonify({
            "auth_response": auth_data,
            "note": "Tokens fetched and saved successfully."
        })

    except Exception as e:
        return jsonify({"error": "Failed to process callback", "details": str(e)}), 500


def get_module_fields(access_token, api_domain, module_api_name):
    url = f"{api_domain}/crm/v3/settings/fields"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }
    params = {
        "module": module_api_name
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        return None, response.text
    data = response.json()
    if "fields" not in data:
        return None, "No fields info found"
    field_names = [field["api_name"] for field in data["fields"]]
    return field_names, None


@app.route("/create_customer", methods=["GET", "POST"])
def create_customer():
    access_token, err = refresh_access_token()
    if err:
        return jsonify({"error": err}), 401

    token_store = load_tokens()
    api_domain = token_store.get("api_domain")
    if not api_domain:
        return jsonify({"error": "API domain missing. Please authenticate again."}), 401

    customer_data = {
        "Name": "Rajalakshmi",
        "Phone": "+919999999999",
        "Email": "raji@example.com",
        "Customer_ID": "1234",
        "Cart_ID": 7890,
        "Order_Date": "2025-05-22",
        "Address": "123 Main Street, Chennai",
        "Known_languages": "Tamil",
        "Order_Status": "Order Placed"
    }

    zoho_url = f"{api_domain}/crm/v3/Customers"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    payload = {"data": [customer_data]}

    response = requests.post(zoho_url, headers=headers, json=payload)

    if response.status_code not in [200, 201]:
        return jsonify({
            "error": "Failed to create customer",
            "details": response.text,
            "status_code": response.status_code
        }), response.status_code

    return jsonify({
        "message": "Customer created successfully",
        "zoho_response": response.json()
    })


@app.route("/customers")
def get_customers():
    access_token, err = refresh_access_token()
    if err:
        return jsonify({"error": err}), 401

    token_store = load_tokens()
    api_domain = token_store.get("api_domain")
    if not api_domain:
        return jsonify({"error": "API domain missing. Please authenticate again."}), 401

    fields, err = get_module_fields(access_token, api_domain, "Customers")
    if err:
        return jsonify({"error": "Failed to fetch fields", "details": err}), 500

    fields_param = ",".join(fields)

    zoho_url = f"{api_domain}/crm/v3/Customers"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }
    params = {
        "fields": fields_param,
        "per_page": 10
    }

    response = requests.get(zoho_url, headers=headers, params=params)

    if response.status_code != 200:
        return jsonify({
            "error": "Failed to fetch customers",
            "details": response.text,
            "status_code": response.status_code
        }), response.status_code

    return jsonify(response.json())


@app.route("/create_order", methods=["GET", "POST"])
def create_order():
    access_token, err = refresh_access_token()
    if err:
        return jsonify({"error": err}), 401

    token_store = load_tokens()
    api_domain = token_store.get("api_domain")
    if not api_domain:
        return jsonify({"error": "API domain missing. Please authenticate again."}), 401

    order_data = {
        "Name": "Test Order Alpha",
        "Order_Date": "2025-05-21",
        "Total_Amount": 199.99,
        "Prescription_Added": True,
        "Items_in_Cart": "Sample Item A, Sample Item B",
        "Cart_ID_1": 12345,
        "Lookup": {
            "id": "839146000000568002" 
        }
    }

    zoho_url = f"{api_domain}/crm/v3/Cart_Orders"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    payload = {"data": [order_data]}

    response = requests.post(zoho_url, headers=headers, json=payload)

    if response.status_code not in [200, 201]:
        return jsonify({
            "error": "Failed to create order",
            "details": response.text,
            "status_code": response.status_code
        }), response.status_code

    return jsonify({
        "message": "Dummy order created successfully",
        "zoho_response": response.json()
    })


@app.route("/orders")
def get_orders():
    access_token, err = refresh_access_token()
    if err:
        return jsonify({"error": err}), 401

    token_store = load_tokens()
    api_domain = token_store.get("api_domain")
    if not api_domain:
        return jsonify({"error": "API domain missing. Please authenticate again."}), 401

    fields, err = get_module_fields(access_token, api_domain, "Cart_Orders")
    if err:
        return jsonify({"error": "Failed to fetch fields", "details": err}), 500

    fields_param = ",".join(fields)

    zoho_url = f"{api_domain}/crm/v3/Cart_Orders"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }
    params = {
        "fields": fields_param,
        "per_page": 10
    }

    response = requests.get(zoho_url, headers=headers, params=params)

    if response.status_code != 200:
        return jsonify({
            "error": "Failed to fetch orders",
            "details": response.text,
            "status_code": response.status_code
        }), response.status_code

    return jsonify(response.json())


if __name__ == "__main__":
    app.run(debug=True)
