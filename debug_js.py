from bs4 import BeautifulSoup
import urllib.request
import json

resp = urllib.request.urlopen('http://localhost:5000/login').read()
# I need a valid session to access /school_results.
