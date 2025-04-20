import datetime
import requests
from google_auth_oauthlib.flow import InstalledAppFlow

# Скоуп для чтения активности (шагов)
SCOPES = ["https://www.googleapis.com/auth/fitness.activity.read"]

def get_credentials():
    # TODO: Путь к файлу лучше задавать через переменную окружения
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=9090, prompt='consent')
    return creds.token

def create_dataset_id():
    now = datetime.datetime.now()
    end = int(now.timestamp() * 1000)
    start = int((now - datetime.timedelta(days=7)).timestamp() * 1000)
    return start, end

def get_steps_data(token):
    headers = {"Authorization": f"Bearer {token}"}
    url = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"

    start, end = create_dataset_id()

    body = {
        "aggregateBy": [{
            "dataTypeName": "com.google.step_count.delta"
        }],
        "bucketByTime": { "durationMillis": 86400000 },  # каждый день
        "startTimeMillis": start,
        "endTimeMillis": end
    }

    response = requests.post(url, headers=headers, json=body)
    data = response.json()

    steps_per_day = []
    for bucket in data.get("bucket", []):
        total = 0
        for dataset in bucket.get("dataset", []):
            for point in dataset.get("point", []):
                for val in point.get("value", []):
                    total += val.get("intVal", 0)
        steps_per_day.append(total)

    return steps_per_day
