import urllib.request
import json
import time

all_questions = []

try:
    # Testing pagination 
    for page in range(1, 10):
        url = f"https://api.enem.dev/v1/exams/2023/questions?page={page}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            response = urllib.request.urlopen(req)
            data = json.loads(response.read().decode('utf-8'))
            qs = data.get('questions', data) if isinstance(data, dict) else data
            print(f"Page {page}: Fetched {len(qs)} questions")
            if not qs:
                break
        except Exception as e:
            print(f"Error on page {page}: {e}")
            break
        time.sleep(1)
except Exception as e:
    print(f"Error: {e}")
