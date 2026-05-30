"""Build frontmatter (title, authors, affiliations, abstract, keywords)."""
import json, re, pathlib, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fix, esc_plain, process_text
from config import DOCX_TMP as DOCX, PAPER_OUT as PAPER

data = json.loads((DOCX / 'body.json').read_text(encoding='utf-8'))

title = fix(next(p['text'] for p in data if p.get('style')=='Title2'))
authors_raw = fix(next(p['text'] for p in data if p.get('style')=='AuthorsFull'))
addresses = [fix(p['text']).strip() for p in data
             if p.get('style')=='Addresses' and p.get('text','').strip()]
abstract_raw = fix(next((p['text'] for p in data if p.get('style')=='Abstract'), ''))
abstract = re.sub(r'^Abstract\s*[:.]?\s*(text\.\s*)?', '', abstract_raw, flags=re.I)

mt = [fix(p['text']) for p in data if p.get('style')=='MainText']
funding = next((t for t in mt if t.lower().startswith('funding:')), '')
kwline = next((t for t in mt if t.lower().startswith('keywords:')), '')
keywords = []
if kwline:
    keywords = [k.strip() for k in kwline.split(':',1)[1].split(',') if k.strip()]

# parse author line
auths = authors_raw.rstrip(',').replace(' and ', ', ')
author_list = []
for a in [x.strip() for x in auths.split(',') if x.strip()]:
    is_corr = a.endswith('*')
    name = a.rstrip('*').strip()
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)  # "HuijunDun" -> "Huijun Dun"
    author_list.append((name, is_corr))

# group address blocks
def is_header(line):
    if not line or line.startswith('E-mail'): return False
    if re.search(r'University|Institute|Laboratory|School|Co\.|Ltd|Department|Engineering', line):
        return False
    if len(line) > 60: return False
    return bool(re.match(r'^[A-Z]\.\s', line))

aff_blocks = []
cur = None
for line in addresses:
    if is_header(line):
        if cur is not None: aff_blocks.append(cur)
        cur = {'persons':[p.strip() for p in line.split(',')], 'lines':[], 'email':''}
    elif line.startswith('E-mail'):
        if cur is not None:
            cur['email'] = line.split(':',1)[1].strip()
    else:
        if cur is None:
            cur = {'persons':[], 'lines':[], 'email':''}
        cur['lines'].append(line)
if cur is not None: aff_blocks.append(cur)

def person_key(person):
    m = re.match(r'^([A-Z])\.\s*(\S.*)$', person)
    return (m.group(1), m.group(2)) if m else (None, person)

# author -> [aff indices]
author_aff = {}
author_email = {}
for ai, blk in enumerate(aff_blocks):
    for person in blk['persons']:
        ki, kl = person_key(person)
        for full, _ in author_list:
            parts = full.split()
            if parts and parts[0][0]==ki and parts[-1]==kl:
                author_aff.setdefault(full, []).append(ai+1)
                if blk['email']:
                    author_email[full] = blk['email']

# Build frontmatter LaTeX
out = []
out.append(f'\\title[mode=title]{{{esc_plain(title)}}}\n')

corr_idx = 1
for full, is_corr in author_list:
    affs = author_aff.get(full, [])
    aff_str = ','.join(str(x) for x in affs) if affs else '1'
    out.append(f'\\author[{aff_str}]{{{esc_plain(full)}}}')
    if is_corr:
        out.append(f'\\cormark[{corr_idx}]')
        if full in author_email:
            out.append(f'\\ead{{{author_email[full]}}}')
        corr_idx += 1
    out.append('')

# Affiliations
for ai, blk in enumerate(aff_blocks, 1):
    org = blk['lines'][0] if blk['lines'] else ''
    # Try to extract city/postcode/country from org line
    m = re.search(r',\s*([A-Z][A-Za-z ]+?)\s*(\d{6})?\s*,\s*([A-Z][A-Za-z]+)\.?\s*$', org)
    city, postcode, country = ('', '', '')
    if m:
        city, postcode, country = m.group(1), m.group(2) or '', m.group(3)
        org = org[:m.start()].rstrip(',').rstrip()
    out.append(f'\\affiliation[{ai}]{{organization={{{esc_plain(org)}}},')
    if city: out.append(f'                city={{{esc_plain(city)}}},')
    if postcode: out.append(f'                postcode={{{postcode}}},')
    if country: out.append(f'                country={{{esc_plain(country)}}}}}')
    else: out.append(f'                country={{China}}}}')
    out.append('')

# Corresponding author marks
for i in range(1, corr_idx):
    out.append(f'\\cortext[{i}]{{Corresponding author}}')

out.append('')
out.append('\\begin{abstract}')
out.append(process_text(abstract))
out.append('\\end{abstract}')
out.append('')
out.append('\\begin{keywords}')
out.append(' \\sep '.join(esc_plain(k) for k in keywords))
out.append('\\end{keywords}')

if funding:
    out.append('')
    out.append('% Funding info preserved as a footnote')
    out.append(f'\\nonumnote{{{process_text(funding)}}}')

(DOCX / 'frontmatter.tex').write_text('\n'.join(out), encoding='utf-8')
(PAPER / 'frontmatter.tex').write_text('\n'.join(out), encoding='utf-8')
print('Wrote frontmatter.tex')
print('Authors:', [a for a,_ in author_list])
print('Affiliations:', len(aff_blocks))
print('Keywords:', keywords)
print('Abstract length:', len(abstract))
