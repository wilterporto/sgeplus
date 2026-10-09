import urllib.request
from bs4 import BeautifulSoup
import re
import json

def get_results_data():
    with open('c:/Users/pc/source/sgeplus/app/templates/external_evaluations/school_results.html', 'r', encoding='utf-8') as f:
        html = f.read()
    # Check if there's any weird JS stuff
    print("Found script references:", len(re.findall(r'<script', html)))

if __name__ == '__main__':
    get_results_data()
