# -*- coding: utf-8 -*-
"""Minimal OMML (Office Math) -> LaTeX converter, good enough for inline symbols."""
import json, re, sys
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8')

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def m(t): return f'{{{M}}}{t}'
def w(t): return f'{{{W}}}{t}'

GREEK = {
    'α':r'\alpha','β':r'\beta','γ':r'\gamma','δ':r'\delta','ε':r'\varepsilon',
    'ζ':r'\zeta','η':r'\eta','θ':r'\theta','ι':r'\iota','κ':r'\kappa',
    'λ':r'\lambda','μ':r'\mu','ν':r'\nu','ξ':r'\xi','π':r'\pi','ρ':r'\rho',
    'σ':r'\sigma','τ':r'\tau','φ':r'\varphi','χ':r'\chi','ψ':r'\psi','ω':r'\omega',
    'Δ':r'\Delta','Φ':r'\Phi','Ω':r'\Omega','Σ':r'\sum','Π':r'\prod',
    '∈':r'\in','×':r'\times','⋅':r'\cdot','·':r'\cdot','−':'-','⊙':r'\odot',
    '∑':r'\sum','≈':r'\approx','≤':r'\leq','≥':r'\geq','→':r'\to','∞':r'\infty',
    '∂':r'\partial','√':r'\sqrt','≠':r'\neq','±':r'\pm','∼':r'\sim',
}

FUNCS = {'sin','cos','tan','tanh','sinh','cosh','exp','log','ln','max','min',
         'softmax','sigmoid','score','Softmax'}

def conv_text(s):
    if not s: return ''
    out=[]
    for ch in s:
        if ch in GREEK: out.append(GREEK[ch]+' ')
        else: out.append(ch)
    return ''.join(out)

def is_func(s):
    return s.strip() in FUNCS

def conv(node):
    tag = node.tag
    if tag == m('oMath') or tag == m('oMathPara'):
        return ''.join(conv(c) for c in node)
    if tag == m('r'):  # run
        txt=''.join((t.text or '') for t in node.iter(m('t')))
        return conv_text(txt)
    if tag == m('t'):
        return conv_text(node.text or '')
    if tag == m('sSub'):
        e=node.find(m('e')); sub=node.find(m('sub'))
        return f'{wrap(conv_seq(e))}_{{{conv_seq(sub)}}}'
    if tag == m('sSup'):
        e=node.find(m('e')); sup=node.find(m('sup'))
        return f'{wrap(conv_seq(e))}^{{{conv_seq(sup)}}}'
    if tag == m('sSubSup'):
        e=node.find(m('e')); sub=node.find(m('sub')); sup=node.find(m('sup'))
        return f'{wrap(conv_seq(e))}_{{{conv_seq(sub)}}}^{{{conv_seq(sup)}}}'
    if tag == m('f'):  # fraction
        num=node.find(m('num')); den=node.find(m('den'))
        return f'\\frac{{{conv_seq(num)}}}{{{conv_seq(den)}}}'
    if tag == m('rad'):  # radical
        deg=node.find(m('deg')); e=node.find(m('e'))
        degtxt=conv_seq(deg) if deg is not None and list(deg) else ''
        if degtxt:
            return f'\\sqrt[{degtxt}]{{{conv_seq(e)}}}'
        return f'\\sqrt{{{conv_seq(e)}}}'
    if tag == m('d'):  # delimiter (parentheses)
        beg='(' ; end=')'
        dPr=node.find(m('dPr'))
        if dPr is not None:
            b=dPr.find(m('begChr')); en=dPr.find(m('endChr'))
            if b is not None: beg=b.get(w('val'),'(')
            if en is not None: end=en.get(w('val'),')')
        inner=''.join(conv_seq(e) for e in node.findall(m('e')))
        L={'(':'(','[':'[','{':r'\{','|':'|','':'.'}.get(beg,beg)
        R={')':')',']':']','}':r'\}','|':'|','':'.'}.get(end,end)
        return f'\\left{L}{inner}\\right{R}'
    if tag == m('nary'):  # sum/integral
        chr_='∑'
        naryPr=node.find(m('naryPr'))
        if naryPr is not None:
            c=naryPr.find(m('chr'))
            if c is not None: chr_=c.get(w('val'),'∑')
        op=GREEK.get(chr_, r'\sum' if chr_=='∑' else conv_text(chr_))
        sub=node.find(m('sub')); sup=node.find(m('sup')); e=node.find(m('e'))
        s=f'{op}'
        if sub is not None and list(sub): s+=f'_{{{conv_seq(sub)}}}'
        if sup is not None and list(sup): s+=f'^{{{conv_seq(sup)}}}'
        s+=f' {conv_seq(e)}'
        return s
    if tag == m('func'):
        fName=node.find(m('fName')); e=node.find(m('e'))
        fn=conv_seq(fName).strip()
        return f'\\{fn if fn in FUNCS else fn}{{{conv_seq(e)}}}' if False else f'{fn}({conv_seq(e)})'
    if tag == m('acc'):  # accent
        e=node.find(m('e'))
        accPr=node.find(m('accPr')); chrv='^'
        if accPr is not None:
            c=accPr.find(m('chr'))
            if c is not None: chrv=c.get(w('val'),'^')
        body=conv_seq(e)
        if chrv in ('~','˜','∼'): return f'\\tilde{{{body}}}'
        if chrv in ('^',): return f'\\hat{{{body}}}'
        if chrv in ('→','⃗'): return f'\\vec{{{body}}}'
        if chrv in ('‾','¯'): return f'\\bar{{{body}}}'
        return f'\\hat{{{body}}}'
    if tag == m('bar'):
        e=node.find(m('e'))
        return f'\\overline{{{conv_seq(e)}}}'
    if tag == m('groupChr'):
        e=node.find(m('e'))
        gPr=node.find(m('groupChrPr')); chrv=''
        if gPr is not None:
            c=gPr.find(m('chr'))
            if c is not None: chrv=c.get(w('val'),'')
        body=conv_seq(e)
        if chrv=='←': return f'\\overleftarrow{{{body}}}'
        if chrv=='→': return f'\\overrightarrow{{{body}}}'
        return body
    if tag == m('e') or tag==m('num') or tag==m('den') or tag==m('sub') or tag==m('sup') or tag==m('deg') or tag==m('fName'):
        return conv_seq(node)
    # default: descend
    return ''.join(conv(c) for c in node)

def conv_seq(node):
    if node is None: return ''
    return ''.join(conv(c) for c in node)

def wrap(s):
    # wrap base in braces if more than one token
    if len(s)<=1 or (s.startswith('\\') and ' ' not in s):
        return s
    if re.fullmatch(r'[A-Za-z0-9]', s): return s
    return s

def main():
    omml=json.load(open('_tmp_docx/omml.json',encoding='utf-8'))
    res={}
    for k in sorted(omml, key=int):
        root=ET.fromstring(omml[k])
        latex=conv(root)
        latex=re.sub(r'\s+',' ',latex).strip()
        res[k]=latex
        print(f'EQ#{k}: {latex}')
    json.dump(res,open('_tmp_docx/eqtex.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

if __name__=='__main__':
    main()
