"""Context-first social editor. Prepare and review drafts; never publish them."""
import base64
import json
import os
import re
from urllib.request import Request, urlopen
from decimal import Decimal, InvalidOperation


def money(value):
    try:
        number=Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('Invalid numerical value') from exc
    if not number.is_finite(): raise ValueError('Non-finite numerical value')
    return number


class SocialTools:
    # Mixin: the host Tools class supplies self.ws.
    def inspect_clip(self, manifest):
        data = self._manifest(manifest)
        return {'source':self.ws.evidence(manifest),'duration_seconds':data['duration_seconds'],
                'rights':data.get('rights','unknown'),'transcript_status':data.get('transcript_status','missing'),
                'segments':data['segments'], 'frames':data.get('frames',[]),
                'notice':data.get('fixture_notice','Supplied transcript and context metadata; not independently verified.')}

    def _manifest(self, file):
        data=json.loads(self.ws.text(file))
        duration=money(data['duration_seconds'])
        if duration <= 0: raise ValueError('Clip duration must be positive')
        ids=[]
        for segment in data['segments']:
            ids.append(segment['id'])
            start,end=money(segment['start']),money(segment['end'])
            if start<0 or end<=start or end>duration: raise ValueError('Invalid transcript timing')
            if not isinstance(segment['text'],str): raise ValueError('Transcript text must be a string')
        if len(ids)!=len(set(ids)): raise ValueError('Segment IDs must be unique')
        return data

    def context_window(self, manifest, start_second, end_second, padding_seconds=10):
        data=self._manifest(manifest)
        if not 0<=start_second<end_second<=data['duration_seconds'] or not 0<=padding_seconds<=60:
            raise ValueError('Invalid clip window or padding')
        lo,hi=max(0,start_second-padding_seconds),min(data['duration_seconds'],end_second+padding_seconds)
        return {'source':self.ws.evidence(manifest),'window':[lo,hi],
                'segments':[s for s in data['segments'] if s['start']<hi and s['end']>lo],
                'frames':[f for f in data.get('frames',[]) if lo<=f['second']<=hi],
                'note':'Context from supplied transcript. Audio tone and unsampled visuals may still be missing.'}

    def inspect_image(self, file, question):
        model=os.environ.get('OLLAMA_VISION_MODEL')
        if not model: raise ValueError('Set OLLAMA_VISION_MODEL to an installed local vision model')
        path=self.ws.path(file)
        if path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'): raise ValueError('Use PNG, JPEG or WebP')
        body={'model':model,'stream':False,'options':{'temperature':0,'num_predict':700},
              'messages':[{'role':'user','content':'Describe only visible evidence. Quote legible text. Flag ambiguity; do not infer identity or audio context. '+question[:1200],
                           'images':[base64.b64encode(path.read_bytes()).decode()]}]}
        req=Request('http://127.0.0.1:11434/api/chat',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=180) as response: raw=response.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('Vision response too large')
        return {'source':self.ws.evidence(file),'observation':json.loads(raw)['message']['content'],
                'note':'Model observation of one image, not verification of the whole video.'}

    def review_social_draft(self, manifest, accounts, draft_json):
        data=self._manifest(manifest)
        policies=json.loads(self.ws.text(accounts))['accounts']
        draft=json.loads(draft_json)
        account=next((a for a in policies if a['id']==draft.get('account_id')),None)
        issues=[]
        if account is None: raise ValueError('Unknown account')
        start,end=money(draft.get('start_second',-1)),money(draft.get('end_second',-1))
        if not 0<=start<end<=money(data['duration_seconds']): issues.append('invalid_clip_window')
        if end-start>money(account['max_clip_seconds']): issues.append('clip_exceeds_account_limit')
        caption=draft.get('caption','')
        if not isinstance(caption,str) or not caption.strip(): issues.append('missing_caption'); caption=''
        if len(caption)>account['max_caption_chars']: issues.append('caption_exceeds_account_limit')
        citations=draft.get('evidence_ids',[])
        if not isinstance(citations,list) or not all(isinstance(x,str) for x in citations): raise ValueError('evidence_ids must be a list of strings')
        indexed={s['id']:s for s in data['segments']}
        if not citations: issues.append('missing_evidence')
        for evidence in citations:
            if evidence not in indexed: issues.append('unknown_evidence:'+evidence); continue
            segment=indexed[evidence]
            if money(segment['start'])<start or money(segment['end'])>end:
                issues.append('cited_evidence_outside_cut:'+evidence)
            for needed in segment.get('requires_context',[]):
                other=indexed.get(needed)
                if other is None or money(other['start'])<start or money(other['end'])>end:
                    issues.append('missing_required_context:'+needed)
        if data.get('rights')!='owned_or_licensed': issues.append('rights_need_confirmation')
        if data.get('transcript_status')!='reviewed': issues.append('transcript_needs_review')
        if draft.get('topic') not in account['allowed_topics']: issues.append('topic_not_allowed_for_account')
        for token in account.get('blocked_caption_phrases',[]):
            if token.casefold() in caption.casefold(): issues.append('account_blocked_phrase:'+token)
        if data.get('privacy_review')!='clear': issues.append('privacy_review_required')
        # All are workflow gates, never proof that the caption preserves the video's meaning.
        return {'account_id':account['id'],'platform':account['platform'],
                'status':'revise_or_ask' if issues else 'ready_for_human_review',
                'issues':sorted(set(issues)),'draft':draft,
                'semantic_review':'Model must separately check irony, quotation, context and account fit; human review remains required.',
                'publish_performed':False,
                'dedupe_key':__import__('hashlib').sha256((self.ws.evidence(manifest)['sha256']+json.dumps(draft,sort_keys=True)).encode()).hexdigest()}
