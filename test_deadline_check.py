import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

# Test French page
french_url = "https://admission.umontreal.ca/programmes/doctorat-en-sciences-biomedicales/"
print(f"测试法语页面: {french_url}")
resp_fr = requests.get(french_url, verify=False, timeout=10)
soup_fr = BeautifulSoup(resp_fr.text, 'html.parser')
sit_fr = soup_fr.select('.situation-texte')
print(f"法语页面找到 {len(sit_fr)} 个 .situation-texte 元素")
for elem in sit_fr[:2]:
    txt = elem.get_text(separator=" ", strip=True)
    if "Du" in txt and "au" in txt:
        print(f"  截止日期文本: {txt}")

# Test English page
english_url = "https://admission.umontreal.ca/en/programs/doctorate-in-biomedical-sciences/"
print(f"\n测试英文页面: {english_url}")
resp_en = requests.get(english_url, verify=False, timeout=10)
soup_en = BeautifulSoup(resp_en.text, 'html.parser')
sit_en = soup_en.select('.situation-texte')
print(f"英文页面找到 {len(sit_en)} 个 .situation-texte 元素")
for elem in sit_en[:2]:
    txt = elem.get_text(separator=" ", strip=True)
    print(f"  内容: {txt}")

# Check for "Application deadlines" in English page
print("\n在英文页面搜索 'Application deadlines':")
import re
page_text = soup_en.get_text(separator="\n", strip=True)
match = re.search(r"Application deadlines.*?\n(.*?)(?:\n|$)", page_text, re.IGNORECASE)
if match:
    print(f"  找到: {match.group(1)}")
else:
    print("  未找到")
