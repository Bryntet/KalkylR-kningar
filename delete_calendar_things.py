import os


from gcsa.google_calendar import GoogleCalendar

api_key = os.environ["api_key"]
base_id = os.environ["base_id"]
gcal_id = os.environ["gcal_id"]

gc = GoogleCalendar(gcal_id, credentials_path='credentials.json')

for event in gc:
    gc.delete_event(event.id)