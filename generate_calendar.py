#!/usr/bin/env python3
"""
Generate an ICS calendar from a CSV of meetings.
Place your CSV at `data/meetings.csv` or pass --input.
"""
import argparse
import csv
import re
from datetime import datetime, date, time, timedelta
import pytz
from dateutil import parser as dtparser
from dateutil.relativedelta import relativedelta
from icalendar import Calendar, Event

WEEKDAY_MAP = {
    'monday': 'MO', 'mon': 'MO',
    'tuesday': 'TU', 'tue': 'TU', 'tues': 'TU',
    'wednesday': 'WE', 'wed': 'WE',
    'thursday': 'TH', 'thu': 'TH', 'thurs': 'TH',
    'friday': 'FR', 'fri': 'FR',
    'saturday': 'SA', 'sat': 'SA',
    'sunday': 'SU', 'sun': 'SU'
}

ORDINAL_MAP = {'1st': 1, 'first': 1, '2nd': 2, 'second': 2, '3rd': 3, 'third': 3, '4th': 4, 'fourth': 4, 'last': -1}

DEFAULT_TZ = 'America/Chicago'


def extract_time(text):
    if not text:
        return None
    m = re.search(r'(?P<h>\d{1,2})(?::(?P<M>\d{2}))?\s*(?P<ampm>am|pm)', text, flags=re.I)
    if m:
        h = int(m.group('h'))
        M = int(m.group('M') or 0)
        ampm = m.group('ampm').lower()
        if ampm == 'pm' and h != 12:
            h += 12
        if ampm == 'am' and h == 12:
            h = 0
        return time(hour=h, minute=M)
    return None


def find_weekdays(text):
    found = []
    text_l = (text or '').lower()
    for k in WEEKDAY_MAP:
        if re.search(r'\b' + re.escape(k) + r'\b', text_l):
            found.append(WEEKDAY_MAP[k])
    return list(dict.fromkeys(found))


def find_ordinal(text):
    text_l = (text or '').lower()
    for k, v in ORDINAL_MAP.items():
        if k in text_l:
            return v
    m = re.search(r"\b([1-5])(st|nd|rd|th)\b", text_l)
    if m:
        return int(m.group(1))
    return None


def detect_cycle_week(text):
    """Detect phrases like '1st week of cycle' or '2nd week of cycle'."""
    if not text:
        return None
    m = re.search(r"\b([12])(st|nd|rd|th)?\s+week of cycle\b", text.lower())
    if m:
        return int(m.group(1))
    return None


def infer_rrule(cadence_text):
    if not cadence_text or not cadence_text.strip():
        return None
    text = cadence_text.lower()
    weekdays = find_weekdays(text)
    cycle_week = detect_cycle_week(text)
    # If cadence mentions a cycle week (1st/2nd week) treat as biweekly on that weekday
    if cycle_week is not None:
        if weekdays:
            return {'FREQ': 'WEEKLY', 'INTERVAL': 2, 'BYDAY': ','.join(weekdays)}
        return {'FREQ': 'WEEKLY', 'INTERVAL': 2}
    if 'every other' in text or 'every 2' in text or 'biweekly' in text:
        if weekdays:
            return {'FREQ': 'WEEKLY', 'INTERVAL': 2, 'BYDAY': ','.join(weekdays)}
        return {'FREQ': 'WEEKLY', 'INTERVAL': 2}
    # phrases like 'odd'/'even' often mean alternating weeks
    if 'odd' in text or 'even' in text or re.search(r'alternate|alternating', text):
        if weekdays:
            return {'FREQ': 'WEEKLY', 'INTERVAL': 2, 'BYDAY': ','.join(weekdays)}
        return {'FREQ': 'WEEKLY', 'INTERVAL': 2}
    if 'weekly' in text or any(w in text for w in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']) and 'monthly' not in text:
        if weekdays:
            return {'FREQ': 'WEEKLY', 'BYDAY': ','.join(weekdays)}
        return {'FREQ': 'WEEKLY'}
    if 'monthly' in text or 'every month' in text or find_ordinal(text):
        ordv = find_ordinal(text)
        if weekdays:
            rule = {'FREQ': 'MONTHLY', 'BYDAY': ','.join(weekdays)}
            if ordv is not None:
                rule['BYSETPOS'] = ordv
            return rule
        return {'FREQ': 'MONTHLY'}
    if 'quarter' in text or 'quarterly' in text:
        return {'FREQ': 'MONTHLY', 'INTERVAL': 3}
    return None


def nth_weekday_of_month(year, month, weekday_index, n):
    d = date(year, month, 1)
    first_wd = d.weekday()
    delta_days = (weekday_index - first_wd) % 7
    first_occ = d + timedelta(days=delta_days)
    if n > 0:
        result = first_occ + timedelta(weeks=n-1)
        return result
    else:
        next_month = d + relativedelta(months=1)
        next_first_wd = (weekday_index - next_month.weekday()) % 7
        next_first = next_month + timedelta(days=next_first_wd)
        last = next_first - timedelta(weeks=1)
        return last


def next_occurrence_for_rule(rrule, default_time, tz):
    today = datetime.now(pytz.timezone(tz)).date()
    if rrule['FREQ'] == 'WEEKLY':
        days = []
        if 'BYDAY' in rrule:
            for d in rrule['BYDAY'].split(','):
                idx = ['MO','TU','WE','TH','FR','SA','SU'].index(d)
                days.append(idx)
        else:
            days = [today.weekday()]
        for i in range(0, 14):
            cand = today + timedelta(days=i)
            if cand.weekday() in days:
                dt = datetime.combine(cand, default_time)
                return pytz.timezone(tz).localize(dt)
    if rrule['FREQ'] == 'MONTHLY':
        if 'BYDAY' in rrule and 'BYSETPOS' in rrule:
            byday = rrule['BYDAY'].split(',')[0]
            weekday_index = ['MO','TU','WE','TH','FR','SA','SU'].index(byday)
            n = int(rrule['BYSETPOS'])
            for k in range(0,3):
                m = (today.month - 1 + k) % 12 + 1
                y = today.year + ((today.month - 1 + k) // 12)
                cand_date = nth_weekday_of_month(y, m, weekday_index, n)
                if cand_date >= today:
                    dt = datetime.combine(cand_date, default_time)
                    return pytz.timezone(tz).localize(dt)
        cand = date(today.year, today.month, 1) + relativedelta(months=1)
        dt = datetime.combine(cand, default_time)
        return pytz.timezone(tz).localize(dt)
    dt = datetime.combine(today, default_time)
    return pytz.timezone(tz).localize(dt)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='data/meetings.csv')
    p.add_argument('--output', default='public/minneapolis_stpaul_meetings.ics')
    p.add_argument('--tz', default=DEFAULT_TZ)
    args = p.parse_args()

    cal = Calendar()
    cal.add('prodid', '-//Minneapolis & St Paul Meetings//mxm 1.0//')
    cal.add('version', '2.0')

    with open(args.input, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row.get('Agency') or row.get('meeting_name') or row.get('Description')
            cadence = row.get('Cadence') or row.get('Est. annual meetings') or ''
            info_link = row.get('Info link') or row.get('Info') or row.get('InfoLink')
            cal_link = row.get('Calendar link') or row.get('Calendar link')
            agenda_link = row.get('Agenda link')
            notes = row.get('Notes') or ''

            t = extract_time(cadence)
            if t is None:
                t = time(hour=12, minute=0)
            rrule = infer_rrule(cadence)
            dtstart = next_occurrence_for_rule(rrule, t, args.tz) if rrule else pytz.timezone(args.tz).localize(datetime.combine(datetime.now().date(), t))

            e = Event()
            e.add('summary', name or 'Meeting')
            e.add('dtstart', dtstart)
            e.add('dtend', dtstart + timedelta(hours=1))
            descr = ''
            if info_link:
                descr += f'Info: {info_link}\n'
            if cal_link:
                descr += f'Calendar: {cal_link}\n'
            if agenda_link:
                descr += f'Agenda: {agenda_link}\n'
            if notes:
                descr += f'Notes: {notes}\n'
            if descr:
                e.add('description', descr)
            if rrule:
                e.add('rrule', rrule)
            cal.add_component(e)

    try:
        from pathlib import Path
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    with open(args.output, 'wb') as fh:
        fh.write(cal.to_ical())
    print('Wrote', args.output)

if __name__ == '__main__':
    main()
