import bs4
import datetime
import os
import re
import requests
import requests_cache
import subprocess
import urllib.parse

session = requests_cache.CachedSession(expire_after=86400*7)

BASE = 'https://www.covid19.public-inquiry.uk/wp-json/c19inquiry/v1/feed/'

def fetch_hearings():
    i = 1
    while True:
        r = requests.post(BASE, json={
            "data": {
                "taxonomies": {
                    "document_type": { "parent":0,"terms":[[51,"Publication"]] },
                    "pub_type": { "parent":"publication","terms":[["20","Transcript"]]} },
                "date_range": {"from":"","to":""},
                "post_types": ["document"],
                "search": "",
                "order": "Date",
                "page": i
            }
        })
        j = r.json()
        for t in j['posts']:
            fetch_hearing_page(t)
        if j['current_page'] == j['total_pages']:
            break
        i += 1

def fetch_hearing_page(item):
    link = item['guid']
    title = item['post_title']
    date = datetime.datetime.strptime(item['post_date'], '%Y-%m-%d %H:%M:%S').date().isoformat()
    #filename = item['post_name']

    # Not right format
    if date == '2023-05-12' or date == '2023-05-05' or date == '2023-04-13':
        return

    # Been put in wrong type
    if title == 'INQ000320588 - Witness statement of Lesley Fraser, Director General Corporate, dated 23/10/2023.':
        return

    filename_pdf = f'data/{date}-{title}.pdf'
    filename_txt = filename_pdf.replace('.pdf', '.txt')
    filename_out = filename_pdf.replace('.pdf', '.scraped.txt')
    if os.path.exists(filename_out):
        return

    url = urllib.parse.urljoin(BASE, link)
    r = session.get(url)
    soup = bs4.BeautifulSoup(r.content, "html.parser")
    href = soup.find('a', class_=re.compile('btn-download'))['href']
    print(date, href)

    with open(filename_pdf, 'wb') as fp:
        content = session.get(href).content
        fp.write(content)

    subprocess.run(['pdftotext', '-layout', filename_pdf])

    # Not 4-up
    if date == '2023-03-21':
        with open(filename_txt, 'r') as fpI, open(filename_out, 'w') as fpO:
            fpO.write(fpI.read())
        return

    with open(filename_txt, 'r') as fp:
        text = convert_four_up_pdf(fp.read())

    with open(filename_out, 'w') as fp:
        fp.write(text)

def convert_four_up_pdf(text):
    # Remove header/footer from all pages
    text = re.sub('\014? *(The )?UK Covid-19 Inquiry  *\d+ .*? 202\d', '', text)
    text = re.sub(' *\(\d+\) Pages \d+ - \d+', '', text)
    #text = re.sub('\xef\xbf\xbd', '', text)

    # Loop through, slurping up the pages by page number
    text_l, text_r = [], []
    pages = {}
    text = re.split('\r?\n', text)
    state = 'okay'

    for line in text:
        #print('*', line)
        if re.match('\s*$', line): continue
        if re.match(r' ?1 +INDEX', line): break
        elif 'INDEX' in line: state = 'index'
        elif re.match(' *Statement by LEAD COUNSEL TO THE INQUIRY \. 2$', line): break

        m = re.match(r' +(\d+)(?: +(\d+))? *$', line)
        if m:
            page_l = int(m.group(1))
            pages[page_l] = text_l
            if m.group(2) and len(text_r):
                page_r = int(m.group(2))
                pages[page_r] = text_r
            text_l, text_r = [], []
            if state == 'index':
                break
            continue

        # Left and right pages
        m = re.match(r' *(\d+)( .*?) + \1( .*)?$', line)
        if m:
            line_n = int(m.group(1))
            line_l = '       %s' % m.group(2).rstrip()
            line_r = '       %s' % m.group(3) if m.group(3) else ''
            text_l.append('%2d%s' % (line_n, line_l))
            text_r.append('%2d%s' % (line_n, line_r))
            continue

        # Offset index lines (2023-11-28)
        if m := re.match(r' +Questions from .*?\.\.\.', line):
            continue

        # Just left page at the end
        m = re.match(r' ?(\d+)( .*)?$', line)
        line_n = int(m.group(1))
        line_l = '       %s' % m.group(2) if m.group(2) else ''
        text_l.append('%2d%s' % (line_n, line_l))

    # Reconstruct in page order for normal processing
    text = ''
    for num, page in sorted(pages.items()):
        for line in page:
            text += line + '\n'
        text += '    %d\n\014\n' % num
    return text


fetch_hearings()
