import json, os, zipfile, datetime

BASE_URL = "http://127.0.0.1:8000/api"
DATE = datetime.datetime.now().isoformat()

headers = [
    {"key": "Authorization", "value": "Bearer {{accessToken}}", "type": "text"},
    {"key": "Content-Type", "value": "application/json", "type": "text"},
]

# Define example collections
collections = {
    "Users – Profiles": [
        {"name": "List Profiles", "method": "GET", "url": f"{BASE_URL}/users/profiles/"},
        {"name": "Retrieve Profile", "method": "GET", "url": f"{BASE_URL}/users/profiles/{{id}}/"},
        {"name": "My Profile", "method": "GET", "url": f"{BASE_URL}/users/profiles/me/"},
        {"name": "Follow User", "method": "POST", "url": f"{BASE_URL}/users/profiles/{{id}}/follow/"},
        {"name": "Followers", "method": "GET", "url": f"{BASE_URL}/users/profiles/{{id}}/followers/"},
    ],
    "Users – Membership": [
        {"name": "List Plans", "method": "GET", "url": f"{BASE_URL}/users/plans/"},
        {"name": "My Memberships", "method": "GET", "url": f"{BASE_URL}/users/memberships/"},
        {"name": "Cancel Membership", "method": "POST", "url": f"{BASE_URL}/users/memberships/{{id}}/cancel/"},
        {"name": "Next Due", "method": "GET", "url": f"{BASE_URL}/users/memberships/due/"},
    ],
    "Users – Groups": [
        {"name": "List Groups", "method": "GET", "url": f"{BASE_URL}/users/groups/"},
        {"name": "Create Group", "method": "POST", "url": f"{BASE_URL}/users/groups/", "body": {"name": "My Group"}},
        {"name": "Join Group", "method": "POST", "url": f"{BASE_URL}/users/groups/{{id}}/join/"},
        {"name": "Leave Group", "method": "POST", "url": f"{BASE_URL}/users/groups/{{id}}/leave/"},
        {"name": "List Members", "method": "GET", "url": f"{BASE_URL}/users/groups/{{id}}/members/"},
    ],
    "Users – Events": [
        {"name": "List Events", "method": "GET", "url": f"{BASE_URL}/users/events/"},
        {"name": "Create Event", "method": "POST", "url": f"{BASE_URL}/users/events/", "body": {"title": "Launch Party", "start": "2025-10-20T12:00:00Z", "end": "2025-10-20T14:00:00Z"}},
        {"name": "RSVP", "method": "POST", "url": f"{BASE_URL}/users/events/{{id}}/rsvp/", "body": {"status": "going"}},
        {"name": "Check-In", "method": "POST", "url": f"{BASE_URL}/users/events/{{id}}/checkin/"},
        {"name": "My RSVPs", "method": "GET", "url": f"{BASE_URL}/users/rsvps/"},
    ],
    "Users – Calendar": [
        {"name": "List Calendar Items", "method": "GET", "url": f"{BASE_URL}/users/calendar/"},
        {"name": "Add Calendar Item", "method": "POST", "url": f"{BASE_URL}/users/calendar/", "body": {"title": "Meeting", "start": "2025-10-21T10:00:00Z", "end": "2025-10-21T11:00:00Z"}},
        {"name": "FullCalendar Feed", "method": "GET", "url": f"{BASE_URL}/users/calendar/fullcalendar/"},
    ],
    "Users – Notifications": [
        {"name": "List Notifications", "method": "GET", "url": f"{BASE_URL}/users/notifications/"},
        {"name": "Mark All Read", "method": "POST", "url": f"{BASE_URL}/users/notifications/mark_all_read/"},
        {"name": "Mark Single Read", "method": "POST", "url": f"{BASE_URL}/users/notifications/{{id}}/mark_read/"},
    ],
    "Users – Chat": [
        {"name": "List Threads", "method": "GET", "url": f"{BASE_URL}/users/threads/"},
        {"name": "Create Thread", "method": "POST", "url": f"{BASE_URL}/users/threads/", "body": {"participants": [1, 2]}},
        {"name": "Add Participant", "method": "POST", "url": f"{BASE_URL}/users/threads/{{id}}/add_participant/", "body": {"user_id": 2}},
        {"name": "Remove Participant", "method": "POST", "url": f"{BASE_URL}/users/threads/{{id}}/remove_participant/", "body": {"user_id": 2}},
        {"name": "List Messages", "method": "GET", "url": f"{BASE_URL}/users/messages/?thread={{thread_id}}"},
        {"name": "Send Message", "method": "POST", "url": f"{BASE_URL}/users/messages/", "body": {"thread": 1, "body": "Hello!"}},
        {"name": "Mark Message Read", "method": "POST", "url": f"{BASE_URL}/users/messages/{{id}}/mark_read/"},
    ],
    "Users – Webhooks": [
        {"name": "Stripe Webhook", "method": "POST", "url": f"{BASE_URL}/users/webhooks/stripe/", "body": {"type": "checkout.session.completed"}},
        {"name": "PayPal Webhook", "method": "POST", "url": f"{BASE_URL}/users/webhooks/paypal/", "body": {"event_type": "PAYMENT.SALE.COMPLETED"}},
    ],
}

os.makedirs("users_postman_collections", exist_ok=True)

for name, endpoints in collections.items():
    data = {
        "info": {"name": name, "_postman_id": name.lower().replace(" ", "-"), "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
        "item": [
            {"name": e["name"], "request": {"method": e["method"], "header": headers, "url": e["url"], "body": {"mode": "raw", "raw": json.dumps(e.get("body", {}), indent=2)}}, "response": [
                {"name": "Example Response", "originalRequest": {}, "status": "OK", "code": 200, "body": json.dumps({"detail": f"Example response for {e['name']}."}, indent=2)}
            ]} for e in endpoints
        ]
    }
    path = f"users_postman_collections/{name}.postman_collection.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# Environment file
env = {
    "name": "Local Django Auth Template",
    "values": [
        {"key": "base_url", "value": BASE_URL, "enabled": True},
        {"key": "jwt_token", "value": "", "enabled": True},
    ],
    "_postman_variable_scope": "environment",
    "_postman_exported_at": DATE,
    "_postman_exported_using": "Postman/10.22.3"
}
with open("users_postman_collections/Local_Django_Auth_Template.postman_environment.json", "w") as f:
    json.dump(env, f, indent=2)

# Bundle everything
with zipfile.ZipFile("users_postman_collections.zip", "w") as z:
    for file in os.listdir("users_postman_collections"):
        z.write(os.path.join("users_postman_collections", file), file)

print("✅ users_postman_collections.zip generated successfully.")
