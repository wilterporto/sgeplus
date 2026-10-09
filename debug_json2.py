from bs4 import BeautifulSoup
import json
import urllib.request
from urllib.error import HTTPError
import urllib.parse
from app import create_app, db
from app.models import User, Tenant

app = create_app()

with app.app_context():
    # create a test client
    client = app.test_client()
    # login
    user = User.query.first()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
    
    # get the page
    resp = client.get('/external_evaluations/school_results?evaluation_id=4&year=1%C2%BA+Ano+EF')
    html = resp.data.decode('utf-8')
    
    soup = BeautifulSoup(html, 'html.parser')
    scripts = soup.find_all('script')
    
    for s in scripts:
        if s.string and 'const resultsData = ' in s.string:
            lines = s.string.split('\n')
            for line in lines:
                if 'const resultsData = ' in line:
                    json_str = line.split('const resultsData = ')[1].strip().rstrip(';')
                    try:
                        data = json.loads(json_str)
                        print("RESULTS DATA KEYS:", list(data.keys())[:5])
                        first_key = list(data.keys())[0]
                        print("FIRST KEY DETAILS:", json.dumps(data[first_key], indent=2)[:500])
                    except Exception as e:
                        print("JSON PARSE ERROR:", e)
                        print("SNIPPET:", json_str[:200])
