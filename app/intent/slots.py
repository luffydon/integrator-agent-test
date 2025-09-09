from __future__ import annotations
import re
from typing import Dict
TIME_PAT=re.compile(r'(?ix)(today|tomorrow|tonight|now|сегодня|завтра|сейчас|heute|morgen|hôm\s*nay|ngày\s*mai|오늘|내일|지금|\b\d{1,2}:\d{2}\b)')
PEOPLE_PAT=re.compile(r'(?ix)(?:for|на|cho|für|dla)?\s*(\d{1,2})\s*(?:people|persons|чел|люд|người|personen|명)')
LOCATION_PAT=re.compile(r'(?i)\b(in|at|ở|в|bei|nach)\s+([\w\-\sÀ-žĐđ]+)')
TERM_PAT=re.compile(r'(?i)(short\s*-?term|long\s*-?term|на\s*короткий\s*срок|долгосрочно|ngắn\s*hạn|dài\s*hạn)')
def extract_slots(text:str, lang:str, base:Dict=None)->Dict:
    slots=dict(base or {})
    m=TIME_PAT.search(text or '');  slots['time']=m.group(0) if m else slots.get('time')
    m=PEOPLE_PAT.search(text or ''); 
    if m:
        try: slots['people']=int(m.group(1))
        except: pass
    m=LOCATION_PAT.search(text or ''); slots['location']=m.group(2).strip() if m else slots.get('location')
    m=TERM_PAT.search(text or '')
    if m:
        term=m.group(1).lower(); slots['term']='short-term' if ('short' in term or 'корот' in term or 'ngắn' in term) else 'long-term'
    return slots
