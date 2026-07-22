import os, json, requests

KEYCLOAK_URL = 'http://localhost:8080/auth'
KEYCLOAK_REALM = 'production'

resp = requests.post(f'{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token', data={'grant_type': 'password', 'client_id': 'admin-cli', 'username': 'admin', 'password': 'admin'})
token = resp.json().get('access_token')

# Check realm event config
resp = requests.get(f'{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}', headers={'Authorization': f'Bearer {token}'})
realm = resp.json()
print('=== Realm Event Config ===')
print(f'eventsListeners: {realm.get("eventsListeners", [])}')
print(f'eventTypes: {realm.get("eventTypes", [])}')
print(f'adminEventsEnabled: {realm.get("adminEventsEnabled", False)}')
print(f'adminEventsDetailsEnabled: {realm.get("adminEventsDetailsEnabled", False)}')

# Enable events
update = {
    'eventsListeners': ['jboss-logging'],
    'eventTypes': ['LOGIN', 'LOGIN_ERROR', 'LOGOUT', 'INVALIDATE_SESSION', 'REFRESH_TOKEN', 'CLIENT_LOGIN'],
    'adminEventsEnabled': True,
    'adminEventsDetailsEnabled': True,
}
resp = requests.patch(f'{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}', json=update, headers={'Authorization': f'Bearer {token}'})
print(f'\nEnable events: HTTP {resp.status_code}')

# Get raw events
resp = requests.get(f'{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/events', params={'dateFrom': '2020-01-01', 'dateTo': '2030-12-31'}, headers={'Authorization': f'Bearer {token}'})
events = resp.json()
print(f'\nTotal events: {len(events)}')
print('\nFirst 3 events (full JSON):')
for i, e in enumerate(events[:3]):
    print(f'--- Event {i} ---')
    print(json.dumps(e, indent=2, default=str))

# Try admin-events endpoint
resp = requests.get(f'{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/admin-events', params={'dateFrom': '2020-01-01', 'dateTo': '2030-12-31'}, headers={'Authorization': f'Bearer {token}'})
print(f'\nAdmin events endpoint: HTTP {resp.status_code}')
if resp.status_code == 200:
    admin_events = resp.json()
    print(f'Total admin events: {len(admin_events)}')
    if admin_events:
        print('First admin event:')
        print(json.dumps(admin_events[0], indent=2, default=str))