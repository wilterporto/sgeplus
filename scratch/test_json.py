import urllib.request
import re

url = "https://raw.githubusercontent.com/joaobertacchi/bncc/master/base.json"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    raw_json = response.read().decode('utf-8')

matches = re.findall(r'"name":\s*"(EF.*?)".*?"description":\s*"(.*?)"', raw_json, re.DOTALL)
print(f"Total EF matches: {len(matches)}")
if matches:
    print(matches[:5])
