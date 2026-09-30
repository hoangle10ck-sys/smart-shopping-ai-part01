"""Small source-observed model phrases for lookup, never offer creation."""
import re
from app.services.extraction.product_extraction_service import KNOWN_BRANDS, KNOWN_PRODUCT_FAMILIES
from app.services.normalization.text_normalizer import normalize_product_text

BRANDS = (*KNOWN_BRANDS, 'LG', 'TCL', 'Hisense', 'Panasonic', 'Philips', 'Poco')
BRAND_PATTERN = re.compile(r'(?<!\w)('+'|'.join(map(re.escape,sorted(BRANDS,key=len,reverse=True)))+r')(?!\w)',re.I)
STOP = {'gia','price','buy','mua','chinh','hang','giam','tra','gop','la','chiec','voi','cho','tai','tot',
        'moi','nhat','tu','den','only','sale','best','is','the','for','or','and','va','hay','hang','thi',
        'smart','tivi','tv','television','duoi','trieu','vnd','dong','inch','google','android',
        'review','camera','factory','unlocked','dual','crystal','uhd','business','ram','mobile',
        'specs','specifications','features','overview','support','catalog','collection','series',
        'global','rom','fullbox','cell','lte','snap'}
ACCESSORY = re.compile(r'\b(op lung|bao da|mieng dan|gia treo|remote|ke (?:tv|tivi)|chan de|phu kien|case for|mount for)\b')


def observed_models(text, extra_brands=()):
    """Bounded, contiguous brand + model tokens; reject prose and mixed brands."""
    result=[]
    pattern = BRAND_PATTERN if not extra_brands else re.compile(
        r'(?<!\w)('+'|'.join(map(re.escape,sorted(set((*BRANDS,*extra_brands)),key=len,reverse=True)))+r')(?!\w)',re.I)
    for match in pattern.finditer(text[:12000]):
        # Accessory mentions do not seed main-product lookups.
        preceding=re.split(r'[.!?;\n]',text[max(0,match.start()-100):match.start()])[-1]
        if ACCESSORY.search(normalize_product_text(preceding) or ''): continue
        suffix=text[match.end():].split('\n',1)[0]
        tokens=[]
        end=match.end()
        for token in re.finditer(r'\S+',suffix):
            if token.group().startswith('('): break
            raw=token.group().strip('(),:;.')
            # Navigation text can concatenate a variant suffix with the next
            # label ("Note 20 UltraThay camera"). Retain only the observed
            # suffix after an already numbered model, never fabricate a code.
            glued = re.match(r'^(Ultra|Pro|Plus|Max|Mini|Lite)(?=[A-Z][a-z])', raw)
            if glued and any(any(c.isdigit() for c in part) for part in tokens):
                end = match.end() + token.start() + len(glued.group())
                tokens.append(glued.group())
                break
            key=normalize_product_text(raw) or ''
            if re.fullmatch(r'[45]G\+[45]G', raw, re.I): break
            if not key or key in STOP or raw[0] in '|–—': break
            if re.fullmatch(r'\d{5,}|\d{1,3}(?:[.,]\d{3})+',raw): break
            if tokens and re.fullmatch(r'(?:19|20)\d{2}',raw): break
            if re.match(r'\d+(?:[.,]\d+)?\s*(?:inch|cm|mm)\b',suffix[token.start():],re.I): break
            if pattern.fullmatch(raw):
                tokens=[]; break
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+./-]*',raw): break
            if '/' in raw and not re.fullmatch(r'\d+(?:GB|TB)?/\d+(?:GB|TB)',raw,re.I):
                tokens=[]; break
            if not tokens and raw[0].isdigit() and not re.fullmatch(r'\d{1,2}[A-Za-z][A-Za-z0-9]*',raw): break
            if raw.isalpha() and not (raw[0].isupper() or raw.isupper()): break
            if len(raw)>22 or (len(tokens)>=5 and not re.fullmatch(r'\d+(?:GB|TB)',raw,re.I)): break
            if len(tokens)>=7: break
            tokens.append(raw);end=match.end()+token.end()
            if token.group().endswith((',',':',';','.')): break
        if not tokens: continue
        # Resolution/connectivity alone does not identify an electronics model.
        codes=[t for t in tokens if any(c.isalpha() for c in t) and any(c.isdigit() for c in t)
               and t.upper() not in {'4K','8K','4G','5G','1080P'} and not re.fullmatch(r'\d+(GB|TB)',t,re.I)]
        family=normalize_product_text(' '.join(tokens)) or ''
        named=any(family==normalize_product_text(f) or family.startswith((normalize_product_text(f) or '')+' ')
                  for f in KNOWN_PRODUCT_FAMILIES)
        numbered_family = any(t.isdigit() for t in tokens[1:]) and tokens[0].isalpha()
        if not codes and not named and not numbered_family: continue
        name=text[match.start():end].strip(' ,;:.()')
        if name and name not in result: result.append(name)
    return result[:12]


def lookup_key(name):
    """Group capacity/connectivity spellings for lookup allocation, not offers."""
    name=re.sub(r'\b\d+(?:\s*/\s*\d+)?\s*(?:GB|TB)\b|\b[45]G\b','',name,flags=re.I)
    key = ' '.join((normalize_product_text(name.replace('(',' ').replace(')',' ')) or '').split())
    # Family spelling varies (Reno 10/Reno10, Note 14/Note14). This key only
    # allocates lookup attempts; it never deduplicates offers or storage SKUs.
    key = re.sub(r'(?<=[a-z])\s+(?=\d)', '', key)
    # Lookup aliases only, never used for catalog identity or offer deduplication.
    return re.sub(r'^samsung galaxy (?=[asmzf]\d)', 'samsung ', key)
