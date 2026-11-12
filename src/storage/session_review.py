"""Durable generation drafts; only an explicit review may mutate campaign canon."""
import copy
import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.RLock()
COLLECTIONS = {'npcs':'updated_npcs', 'quests':'updated_quests', 'locations':'locations',
               'items':'items', 'pcs':'detected_pcs'}
TEXT_FIELDS = {'title','chronicle_text','recap_text','closing_expectations','next_session_script','user_coaching','episode_synopsis'}

class ReviewConflict(ValueError):
    pass

def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()

def directory(output_dir):
    return Path(output_dir) / 'session-reviews'

def review_path(output_dir, review_id):
    if not re.fullmatch(r'[a-f0-9]{32}', review_id):
        raise FileNotFoundError('Revisión no encontrada.')
    return directory(output_dir) / (review_id+'.json')

def _write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    temp.replace(path)

def load_review(output_dir, review_id):
    return json.loads(review_path(output_dir,review_id).read_text(encoding='utf8'))

def _citation_check(citations, transcript):
    # Exact quotations establish provenance, not correctness of interpretation.
    quotes=[q for q in citations if isinstance(q,str) and q.strip()] if isinstance(citations,list) else []
    normalized=' '.join(transcript.split())
    valid=bool(quotes) and all(' '.join(q.split()) in normalized for q in quotes)
    return {'quotes':quotes,'verified':valid,'notice':'Citas localizadas; interpretación pendiente de revisión.' if valid else 'Sin citas verificables en esta transcripción.'}

def campaign_state(manager, name):
    if not manager.get_campaign_path(name).exists() and not manager.get_campaign_dir(name).exists():
        return None
    return manager._load_for_manual_change(name)

def review_markdown(chapter):
    sections=["# Borrador pendiente de revisión", "## " + chapter.get("title", "")]
    for key,label in (("chronicle_text","Crónica"),("recap_text","Resumen factual"),("closing_expectations","Cierre"),("next_session_script","Guion"),("user_coaching","Reflexión")):
        if chapter.get(key):
            sections.append("## " + label + "\n\n" + chapter[key])
    return "\n\n".join(sections)

def stage_review(manager, output_dir, campaign_name, chapter, generated, arguments):
    state=campaign_state(manager,campaign_name)
    exists=state is not None
    state=state if exists else manager.load_campaign(campaign_name)
    rid=uuid.uuid4().hex
    transcript=arguments['raw_transcript']
    evidence=generated.get('evidence',[])
    if not isinstance(evidence,list): evidence=[]
    proposals=[]
    for collection, field in COLLECTIONS.items():
        records=generated.get(field) or []
        if collection=='pcs' and not records:
            records=generated.get('detected_party') or []
        for index, record in enumerate(records):
            key=str(record.get('name') or record.get('personaje') or record.get('character_name') or record.get('id') or '')
            prior=next((x for x in state.get('universal_pcs' if collection=='pcs' else collection,[]) if
                        str(x.get('name') or x.get('personaje') or x.get('character_name') or x.get('id') or '')==key),None)
            citation=next((e for e in evidence if isinstance(e,dict) and e.get('collection')==collection and e.get('key')==key),{})
            proposals.append({'id':f'{collection}:{index}', 'collection':collection,'key':key,
                              'before':copy.deepcopy(prior),'after':copy.deepcopy(record),
                              'evidence':_citation_check(citation.get('quotes'),transcript)})
    data={'version':1,'id':rid,'status':'pending','created_at':datetime.now(timezone.utc).isoformat(),
          'campaign_name':campaign_name,'session_number':arguments['session_number'],
          'replaces_session':any(s.get('session_number')==arguments['session_number'] for s in state.get('sessions',[])),
          'base_fingerprint':fingerprint(state) if exists else None,'chapter':copy.deepcopy(chapter),'arguments':copy.deepcopy(arguments),
          'proposals':proposals,'transcript':transcript,'transcript_sha256':hashlib.sha256(transcript.encode()).hexdigest()}
    data['revision']=fingerprint(data)
    with _LOCK:
        _write(review_path(output_dir,rid),data)
        review_path(output_dir,rid).with_suffix('.md').write_text(review_markdown(chapter),encoding='utf8')
    return data

def list_reviews(output_dir, campaign_name=None):
    folder=directory(output_dir)
    result=[]
    for path in folder.glob('*.json') if folder.exists() else []:
        d=json.loads(path.read_text(encoding='utf8'))
        if d.get('status')!='pending' or (campaign_name and d.get('campaign_name')!=campaign_name): continue
        result.append({k:d.get(k) for k in ('id','campaign_name','session_number','created_at','replaces_session')})
        result[-1]['title']=d.get('chapter',{}).get('title','')
    return sorted(result,key=lambda d:d['created_at'],reverse=True)

def apply_review(manager, output_dir, review_id, revision, selected, chapter):
    with _LOCK:
        d=load_review(output_dir,review_id)
        if d['status']=='superseded': raise ReviewConflict('Hay una revisión más reciente. Ábrela desde Revisiones pendientes.')
        if revision!=d['revision']: raise ReviewConflict('El borrador cambió. Vuelve a abrir su revisión.')
        allowed={p['id'] for p in d['proposals']}
        if len(set(selected))!=len(selected) or not set(selected)<=allowed:
            raise ValueError('La selección contiene propuestas desconocidas o repetidas.')
        if not set(chapter)<=TEXT_FIELDS or any(not isinstance(v,str) for v in chapter.values()):
            raise ValueError('La revisión solo permite editar los campos narrativos indicados.')
        decision=fingerprint({'selected':sorted(selected),'chapter':chapter})
        state=campaign_state(manager,d['campaign_name'])
        current_fingerprint=fingerprint(state) if state is not None else None
        state=state if state is not None else manager.load_campaign(d['campaign_name'])
        prior=next((s for s in state.get('sessions',[]) if s.get('review_id')==review_id),None)
        if d['status']=='applied' or prior:
            if (d.get('decision') or prior.get('review_decision'))!=decision:
                raise ReviewConflict('Esta revisión ya se aplicó con otra selección.')
            d.update(status='applied',decision=decision)
            _write(review_path(output_dir,review_id),d)
            return {'campaign_state':state,'campaign_name':d['campaign_name'],'session_number':d['session_number'],'status':'applied'}
        if current_fingerprint!=d['base_fingerprint']:
            raise ReviewConflict('La campaña cambió después de generar el borrador. Se conservan ambas versiones; revisa el conflicto antes de guardarlo.')
        ch=copy.deepcopy(d['chapter']);ch.update(chapter)
        ch['session_title']=ch.get('title','')
        ch['review_id']=review_id;ch['review_decision']=decision;ch['review_status']='approved'
        ch['canon_evidence']={'transcript_sha256':d['transcript_sha256'],'selected':[p for p in d['proposals'] if p['id'] in selected]}
        args=copy.deepcopy(d['arguments'])
        for collection, field in COLLECTIONS.items():
            args[field]=[p['after'] for p in d['proposals'] if p['collection']==collection and p['id'] in selected]
        args['detected_party']=[]
        args['strict_identity']=True
        args['detected_npc_names']=[n.get('name','') for n in args['updated_npcs']]
        # Rebuild the derivative from the user's revised fields, never stale LLM text.
        args['chronicle_markdown']='\n\n'.join(ch.get(k,'') for k in ('chronicle_text','closing_expectations','user_coaching','next_session_script') if ch.get(k))
        state=manager.record_session(name=d['campaign_name'],session_chapter=ch,**args)
        d.update(status='applied',decision=decision,applied_at=datetime.now(timezone.utc).isoformat())
        _write(review_path(output_dir,review_id),d)
        return {'campaign_state':state,'campaign_name':d['campaign_name'],'session_number':d['session_number'],'status':'applied'}


def artifact_path(output_dir, filename):
    if re.fullmatch(r'[a-f0-9]{32}(?:_transcripcion)?\.(?:md|txt)', filename):
        return directory(output_dir) / filename
    return Path(output_dir) / filename


def refresh_review(manager, output_dir, review_id, revision, chapter):
    with _LOCK:
        old=load_review(output_dir,review_id)
        if old['status']!='pending' or old['revision']!=revision:
            raise ReviewConflict('Esta revisión cambió o ya fue aplicada. Abre su versión actual.')
        if not set(chapter)<=TEXT_FIELDS or any(not isinstance(v,str) for v in chapter.values()):
            raise ValueError('Solo se pueden conservar los campos narrativos editables.')
        generated={field:[] for field in COLLECTIONS.values()}
        generated['evidence']=[]
        for p in old['proposals']:
            generated[COLLECTIONS[p['collection']]].append(p['after'])
            generated['evidence'].append({'collection':p['collection'],'key':p['key'],'quotes':p['evidence']['quotes']})
        ch=copy.deepcopy(old['chapter']);ch.update(chapter)
        args=copy.deepcopy(old['arguments'])
        state=campaign_state(manager,old['campaign_name'])
        if state is not None:
            args['roster']=state.get('roster',args.get('roster',[]))
        new=stage_review(manager,output_dir,old['campaign_name'],ch,generated,args)
        # Keep the original downloadable draft; approving still requires a new review.
        review_path(output_dir,new['id']).with_suffix('.md').write_text(review_markdown(ch),encoding='utf8')
        old.update(status='superseded',superseded_by=new['id'])
        _write(review_path(output_dir,review_id),old)
        return {'id':new['id']}
