"""Read-only tools. Financial amounts use Decimal, never binary floats."""
import csv
import difflib
import hashlib
import io
import json
import os
import re
import statistics
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .social import SocialTools

MAX_BYTES = 2_000_000
MAX_ROWS = 20_000


def money(value):
    try:
        result = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError('Amount must be a decimal number') from exc
    if not result.is_finite():
        raise ValueError('Amount must be finite')
    return result


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError('Workspace must be a directory')

    def path(self, name):
        p = (self.root / name).resolve()
        if self.root not in p.parents or not p.is_file():
            raise ValueError('File must be inside the selected workspace')
        if p.stat().st_size > MAX_BYTES:
            raise ValueError('File exceeds the 2 MB input limit')
        return p

    def text(self, name):
        return self.path(name).read_text(encoding='utf-8-sig')

    def files(self):
        return {'files': sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*')
                                if p.is_file() and not p.is_symlink())[:200]}

    def csv(self, name, required=()):
        reader = csv.DictReader(io.StringIO(self.text(name)))
        fields = reader.fieldnames or []
        if not fields or len(fields) != len(set(fields)):
            raise ValueError('CSV needs unique column names')
        if any(f not in fields for f in required):
            raise ValueError('Required columns: ' + ', '.join(required))
        rows = []
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError('Ragged CSV row')
            rows.append(row)
            if len(rows) > MAX_ROWS:
                raise ValueError('CSV exceeds the 20,000-row limit')
        return fields, rows

    def evidence(self, name):
        p = self.path(name)
        return {'file': str(p.relative_to(self.root)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}


class Tools(SocialTools):
    def __init__(self, root, network=False):
        self.ws = Workspace(root)
        self.network = network

    def list_files(self):
        return self.ws.files()

    def read_excerpt(self, file, start_line=1, lines=40):
        if not isinstance(start_line, int) or not isinstance(lines, int) or start_line < 1 or not 1 <= lines <= 100:
            raise ValueError('Use a positive start_line and 1–100 lines')
        text = self.ws.text(file).splitlines()
        return {'source': self.ws.evidence(file), 'total_lines': len(text),
                'excerpt': [{'line': i + 1, 'text': text[i][:1000]} for i in range(start_line-1, min(len(text), start_line-1+lines))]}

    def audit_csv(self, file, key='', numeric_column='', date_column='', as_of='', max_age_days=7):
        fields, rows = self.ws.csv(file)
        for col in (key, numeric_column, date_column):
            if col and col not in fields:
                raise ValueError('Unknown column: ' + col)
        missing = {f: sum(not r[f].strip() for r in rows) for f in fields}
        duplicates = []
        if key:
            counts = Counter(r[key] for r in rows if r[key].strip())
            duplicates = [{'value': k, 'count': n} for k, n in counts.items() if n > 1]
        numeric = {'column': numeric_column, 'valid': 0, 'invalid_rows': [], 'outlier_rows': []}
        values = []
        if numeric_column:
            for line, row in enumerate(rows, 2):
                if not row[numeric_column].strip():
                    continue
                try:
                    values.append((line, money(row[numeric_column])))
                except ValueError:
                    numeric['invalid_rows'].append(line)
            numeric['valid'] = len(values)
            if values:
                v = [x[1] for x in values]
                median = statistics.median(v)
                mad = statistics.median(abs(x-median) for x in v)
                numeric.update(min=str(min(v)), max=str(max(v)), median=str(median), sum=str(sum(v)), mad=str(mad))
                if mad:
                    numeric['outlier_rows'] = [line for line, val in values if abs(val-median)/mad > 6]
                else:
                    numeric['note'] = 'MAD is zero; no outlier classification made.'
        dates = {'column': date_column, 'invalid_rows': [], 'stale_rows': [], 'future_rows': []}
        if date_column:
            if not isinstance(max_age_days, int) or max_age_days < 0:
                raise ValueError('max_age_days must be a non-negative integer')
            cutoff = date.fromisoformat(as_of)
            for line, row in enumerate(rows, 2):
                if not row[date_column].strip():
                    continue
                try:
                    delta = (cutoff-date.fromisoformat(row[date_column])).days
                    if delta < 0: dates['future_rows'].append(line)
                    elif delta > max_age_days: dates['stale_rows'].append(line)
                except ValueError:
                    dates['invalid_rows'].append(line)
            dates['as_of'] = as_of
        return {'source': self.ws.evidence(file), 'rows': len(rows), 'columns': fields,
                'missing': missing, 'duplicate_keys': duplicates, 'numeric': numeric, 'dates': dates,
                'note': 'Checks describe data quality, not the truth of the underlying observations.'}

    def compare_documents(self, before, after):
        old, new = self.ws.text(before).splitlines(), self.ws.text(after).splitlines()
        if max(len(old),len(new)) > 5000:
            raise ValueError('Compare at most 5,000 lines per document; split large filings into sections')
        changes = []
        for tag, i, j, k, l in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
            if tag == 'equal': continue
            changes.append({'type': tag, 'before_lines': [i+1, j] if j>i else [],
                            'after_lines': [k+1, l] if l>k else [], 'before': old[i:j], 'after': new[k:l]})
        return {'before_source': self.ws.evidence(before), 'after_source': self.ws.evidence(after),
                'changed_blocks': len(changes), 'changes': changes[:100], 'truncated': len(changes)>100,
                'note': 'Text changes only; document claims and legal significance are not verified.'}

    def reconcile_payments(self, invoices, payments, as_of):
        _, inv = self.ws.csv(invoices, ('invoice_id','currency','amount','due_date'))
        _, pay = self.ws.csv(payments, ('payment_id','invoice_id','currency','amount','status'))
        cutoff = date.fromisoformat(as_of)
        ids = [r['invoice_id'] for r in inv]
        if any(x != x.strip() for x in ids): raise ValueError('Trim whitespace from invoice IDs')
        if any(not x for x in ids) or len(set(ids)) != len(ids):
            raise ValueError('Invoice IDs must be non-empty and unique')
        pid = [r['payment_id'] for r in pay]
        if any(x != x.strip() for x in pid): raise ValueError('Trim whitespace from payment IDs')
        if any(not x for x in pid): raise ValueError('Payment IDs must be non-empty')
        duplicates = {k for k,n in Counter(pid).items() if n>1}
        indexed = {r['invoice_id']: r for r in inv}
        totals = defaultdict(Decimal)
        exceptions = []
        for line, row in enumerate(pay,2):
            issue = None
            if row['payment_id'] in duplicates: issue = 'duplicate_payment_id'
            elif row['invoice_id'] not in indexed: issue = 'unknown_invoice'
            elif row['currency'] != indexed[row['invoice_id']]['currency']: issue = 'currency_mismatch'
            elif row['status'] != 'settled': issue = 'not_settled'
            try:
                value = money(row['amount'])
                if value <= 0: issue = issue or 'non_positive_payment'
            except ValueError:
                issue = issue or 'invalid_amount'
            if issue:
                exceptions.append({'row': line, 'payment_id': row['payment_id'], 'reason': issue})
            else:
                totals[row['invoice_id']] += value
        result, balances = [], defaultdict(Decimal)
        for row in inv:
            amount = money(row['amount'])
            if amount <= 0: raise ValueError('Invoice amount must be positive')
            if not re.fullmatch('[A-Z]{3}', row['currency']): raise ValueError('Currency needs a three-letter uppercase code')
            due = date.fromisoformat(row['due_date'])
            paid = totals[row['invoice_id']]
            balance = amount-paid
            state = 'paid' if balance==0 else ('overpaid' if balance<0 else ('overdue' if due<cutoff else 'open'))
            result.append({'invoice_id': row['invoice_id'], 'currency': row['currency'], 'amount': str(amount),
                           'settled': str(paid), 'balance': str(balance), 'state': state})
            balances[row['currency']] += max(balance, Decimal(0))
        return {'sources': [self.ws.evidence(invoices), self.ws.evidence(payments)], 'as_of': as_of,
                'invoices': result, 'exceptions': exceptions, 'outstanding_by_currency': {k: str(v) for k,v in balances.items()},
                'note': 'Reconciles supplied records only. Does not verify bank or blockchain settlement. Duplicate IDs excluded entirely; no FX conversion.'}

    def search_open_papers(self, query, limit=5):
        if not self.network: raise ValueError('Network disabled; enable --network for OpenAlex searches')
        if not isinstance(limit, int) or not 1 <= limit <= 10: raise ValueError('limit must be 1–10')
        if not isinstance(query,str) or not 2 <= len(query) <= 300: raise ValueError('query must be 2–300 characters')
        params = urlencode({'search':query,'filter':'open_access.is_oa:true','per-page':limit})
        headers = {'User-Agent':'PracticalAgents/0.1','Accept':'application/json'}
        key = os.environ.get('OPENALEX_API_KEY')
        if key: headers['Authorization'] = 'Bearer ' + key
        req = Request('https://api.openalex.org/works?' + params, headers=headers)
        with urlopen(req, timeout=25) as response:
            raw = response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise ValueError('API response too large')
        data = json.loads(raw)
        return self.paper_records(data, query)

    @staticmethod
    def paper_records(data, query):
        papers = []
        for r in data.get('results',[])[:10]:
            oa = r.get('open_access') or {}
            location = r.get('best_oa_location') or {}
            if not oa.get('is_oa'): continue
            papers.append({'title':r.get('display_name'), 'year':r.get('publication_year'),
                           'doi':r.get('doi'), 'source_record':r.get('id'),
                           'open_url':oa.get('oa_url') or location.get('landing_page_url'),
                           'license':location.get('license'), 'version':location.get('version'),
                           'retracted':r.get('is_retracted',False)})
        return {'query':query,'papers':papers,'source':'OpenAlex metadata',
                'note':'OpenAlex reports open availability. Links and licensing may change; metadata does not establish paper quality. Full text is not fetched.'}

    def inspect_paper_snapshot(self, file, query='fixture'):
        data = json.loads(self.ws.text(file))
        result = self.paper_records(data, query)
        result['snapshot_source'] = self.ws.evidence(file)
        result['mode'] = 'supplied metadata snapshot, not live search'
        return result
