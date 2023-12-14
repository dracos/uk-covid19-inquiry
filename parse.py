#from datetime import datetime
import glob
import json
import os
import re
import string

ACRONYMS = {
}

class Section(object):
    def __init__(self, heading, level=1):
        self.heading = heading
        self.level = level

class Speech(object):
    def __init__(self, speaker, text, speaker_display=None, typ=None):
        self.speaker = speaker
        self.speaker_display = speaker_display
        self.text = [[text]]
        self.type = typ

    def add_para(self, text):
        self.text.append([text])

    def add_text(self, text):
        self.text[-1].append(text)

def parse_speech(speech):
    text = '\n\n'.join([' '.join(s) for s in speech.text])
    text = text.strip()
    if not text:
        return ''

    # Deal with some acronyms
    for acronym, meaning in ACRONYMS.items():
        text = re.sub(fr'\b{acronym}\b', f':abbr:`{acronym} ({meaning})`', text, count=1)

    if speech.speaker:
        return f"**{speech.speaker}**: {text}\n\n"
    else:
        return f"*{text}*\n\n"

def parse_transcripts():
    for f in sorted(glob.glob('data/*.scraped.txt')):
        Speech.witness = None
        date, title = re.match('data/(\d\d\d\d-\d\d-\d\d)-(.*).scraped.txt$', f).groups()
        if m := re.search('Module (2[ABC])', title):
            sect = 'module-' + m.group(1)
            os.makedirs(sect, exist_ok=True)
            outfile = f'{sect}/{date}'
        elif m := re.search('Module (\d)', title):
            sect = 'module-' + m.group(1)
            os.makedirs(sect, exist_ok=True)
            outfile = f'{sect}/{date}'
        else:
            outfile = f'{date}'

        with open(f, 'r', encoding='utf-8') as fp:
            if os.path.exists(f'{outfile}.rst'):
                print(f"Reparsing {f}")
            else:
                print(f"\033[31mPARSING {f}\033[0m")
            with open(f'{outfile}.rst', 'w') as out:
                out.write(title + '\n' + '=' * len(title) + '\n\n')
                for speech in parse_transcript(f, fp):
                    if isinstance(speech, Speech):
                        out.write(parse_speech(speech))
                    elif isinstance(speech, Section):
                        if speech.level == 1:
                            out.write(speech.heading + '\n' + '-' * len(speech.heading) + '\n\n')
                        elif speech.level == 2:
                            out.write(speech.heading + '\n' + '^' * len(speech.heading) + '\n\n')

def strip_line_numbers(text):
    page, num = 1, 1
    state = 'text'
    data = {}
    for line in text:
        line = line.rstrip('\n')

        # Page break
        if '\014' in line:
            page += 1
            num = 1
            line = line.replace('\014', '')

        # Empty line
        if re.match('\s*$', line):
            continue

        # Start of index, ignore from then on
        if re.match(' *\d* +I ?N ?D ?E ?X$', line) or '...............' in line:
            state = 'index'
            continue
        if state == 'index':
            continue

        # Just after last line, there should be a page number
        if num == 26:
            m = re.match(' +(\d+)$', line)
            assert int(m.group(1)) == page
            continue

        # Let's check we haven't lost a line anywhere...
        assert re.match(' *%d( |$)' % num, line), '%s != %s' % (num, line)

        # Strip the line number
        line = re.sub('^ *%d' % num, '', line)

        # Okay, here we have a non-page number, non-index line of just text
        data.setdefault(page, []).append((num, line))
        num += 1

    return data

def remove_left_indent(data):
    # Work out how indented everything is
    for page in data.keys():
        min_indent = 999
        for num, line in data[page]:
            if re.match('\s*$', line):
                continue
            left_space = len(line) - len(line.lstrip())
            if left_space:
                min_indent = min(min_indent, left_space)
        # Strip that much from every line
        data[page] = [
            (num, re.sub('^' + (' ' * min_indent), '', line))
            for num, line in data[page]
        ]

    return data

def parse_transcript(url, text):
    data = strip_line_numbers(text)
    data = remove_left_indent(data)

    indent = None
    speech = None
    interviewer = None
    state = 'text'
    skip_lines = 0
    date = None
    for page in data.keys():
        new_para_indent = 4
        for num, line in data[page]:
            m1 = re.match(' *((?:[A-Z -]|Mc)+): (.*)', line)
            m2 = re.match('([QA])\. (.*)', line)
            if m1 or m2:
                new_para_indent = 7
        if '2023-10-16' in url and page in (94,96,108,178):
            new_para_indent = 8

        for num, line in data[page]:
            # Okay, here we have a non-empty, non-page number, non-index line of just text
            #print(f'{page},{num:02d} {line}')

            if skip_lines > 0:
                skip_lines -= 1
                continue

            # Empty line
            if re.match('\s*$', line):
                continue

            line = line.replace('MAPEC_', 'MAPEC)')
            line = line.replace('**', '\*\*')

            # Date at start
            m = re.match(' *(Mon|Tues|Wednes|Thurs|Fri)day,? \d+(nd)? (August|September|October|November|December|January|February|March|April|May|June|July) 202[123]$', line)
            if m:
                date = line.strip() # datetime.strptime(line.strip(), '%A, %d %B %Y')
                continue

            if state == 'adjournment':
                if re.match(' *(\(.*\))$', line):
                    # Meta message immediately after heading
                    spkr = getattr(speech, 'speaker', None)
                    yield speech
                    yield Speech(speaker=None, text=line)
                    speech = Speech( speaker=spkr, text='' )
                    continue
                if re.match(' *(.*)\)$', line):
                    # End of multi-line meta text
                    state = 'text'
                    speech.add_text(line.strip())
                    continue
                if re.match(' *(MODULE 2[ABC])$', line):
                    # End of multi-line heading
                    state = 'text'
                    speech.heading += ' ' + fix_heading(line)
                    continue
                if not re.match(' *[A-Zc -]*:', line):
                    # Continuation of heading
                    speech.heading += ' ' + fix_heading(line)
                    continue
                state = 'text'

            # Time/message about lunch/adjournments
            m = re.match(' *(\(.*\))$', line)
            if m:
                spkr = None
                if speech:
                    spkr = getattr(speech, 'speaker', None)
                    yield speech
                yield Speech(speaker=None, text=line)
                speech = Speech( speaker=spkr, text='' )
                continue

            # Multiline message about adjournment
            m = re.match('(?i) *\((The (hearing|Inquiry) adjourned|On behalf of)', line)
            if m:
                yield speech
                state = 'adjournment'
                speech = Speech( speaker=None, text=line.strip() )
                continue

            # Multiline heading
            m = re.match(' *(Response statement by LEAD COUNSEL TO THE INQUIRY FOR$|Submissions on behalf of)', line)
            if m:
                yield speech
                state = 'adjournment'
                speech = Section( heading=fix_heading(line) )
                continue

            # Questions
            m = re.match(' *(?:Further question|Question|Examin)(?:s|ed) (?:from|by) (.*?)(?: \(continued\))?$', line.strip())
            if m:
                yield speech
                speech = Section( heading=fix_heading(line), level=2)
                interviewer = fix_name(m.group(1))
                continue

            # Headings
            m = re.match(' *(((Opening|Closing|Reply|Response|Further) s|S)(ubmissions?|tatement)|(Closing|Concluding|Opening|Introductory) remarks) by ([A-Z0-9 ]*)(?:,? KC)?(?: \(continued\))?$|[A-Z ]*$', line.strip())
            if m:
                yield speech
                speech = Section( heading=fix_heading(line) )
                if m.group(6):
                    yield speech
                    speech = Speech( speaker=fix_name(m.group(6)), text='' )
                continue

            # Witness arriving
            m1 = re.match(" *((?:[A-Z]|Mr)(?:[A-Z0-9'’ ,-]|Mc|Mac|Mr|and)+?)(,?\s*\(.*\)|, (?:sworn|affirmed|statement summarised|summary read by ([A-Z ]*)))$", line)
            m2 = re.match(" *(Mr.*)(, statement summarised)$", line)
            m3 = re.match(" *(Summary of witness statement of )([A-Z ]*)(\s*\(read\))$", line)
            if m1 or m2 or m3:
                m = m1 or m2 or m3
                if m3:
                    heading = m.group(1) + fix_name(m.group(2).strip())
                    narrative = '%s%s%s.' % (m.group(1), m.group(2), m.group(3))
                else:
                    heading = fix_name(m.group(1).strip())
                    if 'statement' not in line:
                        Speech.witness = heading
                    narrative = '%s%s.' % (m.group(1), m.group(2))
                spkr = speech.speaker
                yield speech

                witness_heading = Section( heading=heading )
                if re.match(' *and$', data[page][num][1]):
                    witness_heading.heading += ' and '
                    if re.match(' *and$', data[page][num][1]):
                        next_witness = data[page][num+1][1]
                        m4 = re.match(" *((?:[A-Z0-9' ,-]|Mc|Mr)+?)(,?\s*\(.*\)|, (?:sworn|affirmed))$", next_witness)
                        if m4:
                            witness_heading.heading += fix_name(m4.group(1).strip())
                            narrative += '*\n\n*%s%s.' % (m4.group(1), m4.group(2))
                            skip_lines = 2
                yield witness_heading

                yield Speech( speaker=None, text=narrative )
                if m1 and m.group(3):
                    speaker = fix_name(m.group(3))
                    speech = Speech( speaker=speaker, text='')
                else:
                    speech = Speech( speaker=spkr, text='' )
                continue

            # Question/answer (speaker from previous lines)
            m = re.match(' *([QA])\. (.*)', line)
            if m and not re.match(' *A\. The list of issues\.$', line):
                yield speech
                if m.group(1) == 'A':
                    assert Speech.witness
                    speaker = Speech.witness
                else:
                    assert interviewer
                    speaker = interviewer
                speech = Speech( speaker=speaker, text=m.group(2) )
                continue

            # New speaker
            m = re.match(' *((?:[A-Z -]|Mc|O\')+): (.*)', line)
            if m:
                yield speech
                speaker = fix_name(m.group(1))
                if not interviewer:
                    interviewer = speaker
                speech = Speech( speaker=speaker, text=m.group(2) )
                continue

            # New paragraph if indent at least some spaces
            m = re.match(' ' * new_para_indent, line)
            if m:
                speech.add_para(line.strip())
                continue

            # If we've got this far, hopefully just a normal line of speech
            speech.add_text(line.strip())

    yield speech

#name_fixes = { }
def fix_name(name):
    name = name.title()
    name = name.replace('Kc', 'KC')
    #s = s.replace(' Of ', ' of ').replace(' And ', ' and ').replace('Dac ', 'DAC ') \
    #     .replace('Ds ', 'DS ')
    # Deal with the McNames
    name = re.sub('Ma?c[a-z]', lambda mo: mo.group(0)[:-1] + mo.group(0)[-1].upper(), name)
    #s = name_fixes.get(s, s)
    # More than one name given, or Lord name that doesn't include full name
    #if ' and ' in name or (' of ' in name and ',' not in name):
    #    return name
    # Remove middle names
    name = re.sub('^(DAC|DS|Dr|Miss|Mrs|Mr|Ms|Baroness|Lord|Professor|Sir) (\S+ )(?:\S+ )+?(\S+)((?: KC)?)$', r'\1 \2\3\4', name)
    name = re.sub('^(?!DAC|DS|Dr|Miss|Mrs|Mr|Ms|Baroness|Lord|Professor|Sir)(\S+) (?!Court)(?:\S+ )+(\S+)', r'\1 \2', name)
    return name

def fix_heading(s):
    s = string.capwords(s.strip())
    rep = [ '2a', '2b', '2c', 'Kc', 'Uk', 'Sos', 'Cv' ]
    s = re.sub('|'.join(rep), lambda m: m.group(0).upper(), s)
    rep = [ 'Of', 'By', 'The', 'To', 'On', 'For', 'And' ]
    s = re.sub('\\b' + '\\b|\\b'.join(rep) + '\\b', lambda m: m.group(0).lower(), s)
    return s

parse_transcripts()
