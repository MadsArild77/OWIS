"""Cached public-article enrichment after relevance screening. No paywall bypass."""
import ipaddress
import json
import os
import re
import socket
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup
from owis.core.storage.db import get_conn
from owis.core.llm.client import AIClient
from owis.modules.news.processing.editorial import prefilter, topics_for
from owis.modules.news.collectors.scrape_fetcher import _extract_article_text

def public_url(url):
    p=urlparse(url)
    if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or p.port not in {None,80,443}:
        raise ValueError('Only public HTTP(S) article URLs are supported')
    addresses=socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Private network address rejected')

def fetch_public(url):
    with httpx.Client(timeout=12,follow_redirects=False,headers={'User-Agent':'OWIS/1.0 ArticleReader'}) as client:
        for _ in range(4):
            public_url(url)
            with client.stream('GET',url) as r:
                if r.is_redirect:
                    url=urljoin(url,r.headers['location']);continue
                if r.status_code in {401,402}:return 'restricted','',url
                if r.status_code in {403,429}:return 'blocked','',url
                r.raise_for_status()
                if 'html' not in r.headers.get('content-type',''):return 'unknown','',url
                chunks=[];size=0
                for chunk in r.iter_bytes():
                    size+=len(chunk)
                    if size>2_000_000:raise ValueError('Article response too large')
                    chunks.append(chunk)
                html=b''.join(chunks).decode(r.encoding or 'utf-8',errors='replace')
                soup=BeautifulSoup(html,'html.parser')
                page_text=soup.get_text(' ',strip=True).lower()
                if any(marker in page_text for marker in ('verify you are human','checking your browser','enable javascript and cookies')):
                    return 'blocked','',url
                restricted=False
                for script in soup.select('script[type="application/ld+json"]'):
                    if '"isAccessibleForFree"' in script.text and re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")',script.text,re.I):restricted=True
                text=_extract_article_text(html)
                if restricted:return 'restricted','',url
                if len(text)<800 or not (soup.find('article') or soup.find('main')):
                    if any(t in soup.get_text(' ',strip=True).lower() for t in ('subscribe to read','log in to read','kun for abonnenter','abonner for å lese')):
                        return 'restricted','',url
                    return 'unknown','',url
                return 'open',text,url
    return 'unknown','',url

def alternative_sources(raw, ai):
    """Search collected sources first. Only verified open same-event coverage is offered."""
    from owis.modules.news.matching.service import build_candidate_pairs,judge_pair
    with get_conn() as c:
        rows=[dict(r) for r in c.execute('''SELECT p.*,r.article_url,r.published_at FROM news_processed_items p
            JOIN news_raw_items r ON r.id=p.raw_item_id WHERE r.article_url!=? ORDER BY r.fetched_at DESC LIMIT 350''',(raw['article_url'],))]
    target={'id':2147483647,'title':raw['title_raw'],'summary':raw.get('summary_raw',''),'published_at':raw.get('published_at'),'domain_bucket':'offshore_wind'}
    for row in rows:row['domain_bucket']='offshore_wind'
    pairs=build_candidate_pairs(rows+[target],days_window=30)
    candidates=[a if b['id']==target['id'] else b for a,b,_ in pairs if target['id'] in (a['id'],b['id'])][:3]
    # Optional broader search; one request, no more than three external candidates.
    key=os.getenv('BRAVE_SEARCH_API_KEY','')
    if key and len(candidates)<3:
        try:
            response=httpx.get('https://api.search.brave.com/res/v1/web/search',
                params={'q':raw['title_raw'][:300], 'count':3},
                headers={'X-Subscription-Token':key},timeout=12)
            response.raise_for_status()
            for i,row in enumerate(response.json().get('web',{}).get('results',[])[:3]):
                if row.get('url')==raw['article_url']:continue
                candidates.append({'id':2147483600+i,'title':row.get('title',''),'summary':row.get('description',''),
                    'article_url':row['url'],'published_at':None})
        except Exception:pass
    results=[]
    unique={item['article_url']:item for item in candidates if item['article_url'] != raw['article_url']}
    for item in list(unique.values())[:3]:
        try:access,text,url=fetch_public(item['article_url'])
        except Exception:continue
        if access!='open':continue
        item['cleaned_text']=text
        judgement=judge_pair(ai,target,item,0)
        if judgement['fallback'] or judgement['relationship']!='same_event' or judgement['confidence']<0.8:continue
        results.append({'url':url,'title':item['title'],'access':'open','text':text})
        if len(results)>=2:break
    return results

def enrichment_eligible(raw):
    from owis.modules.news.processing.pipeline import _score, _classify_theme, _classify_geo, _extract_actors, _clean_text
    with get_conn() as c:
        positive=c.execute("""SELECT 1 FROM news_editorial_state s JOIN news_editorial_events e ON e.id=s.event_id
            JOIN news_processed_items p ON p.id=s.processed_id WHERE p.raw_item_id=? AND e.value='relevant' LIMIT 1""",(raw['id'],)).fetchone()
        stored=c.execute('SELECT signal_score FROM news_processed_items WHERE raw_item_id=?',(raw['id'],)).fetchone()
    text=_clean_text(f"{raw.get('title_raw','')} {raw.get('content_raw') or raw.get('summary_raw','')}")
    score=stored['signal_score'] if stored else _score(_classify_theme(text),_classify_geo(text),_extract_actors(text),text)
    try:threshold=max(0,min(100,int(os.getenv('OWI_OPEN_SOURCE_MIN_SCORE','70'))))
    except ValueError:threshold=70
    return bool(positive) or (score>=threshold and bool(topics_for(text))), bool(positive)


def prepare(raw, refresh=False):
    from owis.modules.news.storage.evidence import save
    eligible,positive=enrichment_eligible(raw)
    with get_conn() as c:
        saved=c.execute('SELECT * FROM news_content_basis WHERE raw_id=?',(raw['id'],)).fetchone()
    ai=AIClient()
    if saved and not refresh:
        meta=dict(saved)
    else:
        decision,reason,_=prefilter(raw,ai)
        if positive:decision,reason='relevant','Manuelt vurdert som interessant'
        feed=raw.get('content_raw') or raw.get('summary_raw') or ''
        save(raw['id'],raw['article_url'],raw['title_raw'],raw.get('source_name',''),
             'unknown','feed_text' if len(feed)>=800 else 'feed_excerpt',feed)
        meta=dict(raw_id=raw['id'],relevance=decision,reason=reason,access='unknown',basis='feed_text' if len(feed)>=800 else 'feed_excerpt',text=feed,source_url=raw['article_url'],alternatives='[]',checked_at=datetime.now(timezone.utc).isoformat())
        if decision!='excluded' and (len(feed)<800 or refresh) and os.getenv('OWI_FULLTEXT_ENABLED','true').lower()=='true':
            try:
                access,text,url=fetch_public(raw['article_url'])
                meta['access']=access
                if access=='open':meta.update(text=text,source_url=url,basis='fulltext')
            except Exception as exc:meta['reason']+=f'; Fulltekst ikke tilgjengelig ({type(exc).__name__})'
        save(raw['id'],raw['article_url'],raw['title_raw'],raw.get('source_name',''),meta['access'],meta['basis'],meta['text'])
    if saved and saved['basis']=='alternative_fulltext' and meta['basis']!='fulltext':
        meta=dict(saved)  # Preserve verified evidence during cached rechecks.
    if positive:meta.update(relevance='relevant',reason='Manuelt vurdert som interessant')
    thin=len(BeautifulSoup(meta['text'],'html.parser').get_text(' ',strip=True))<800
    needs_more=meta['basis']!='alternative_fulltext' and (thin or meta['access'] in {'restricted','blocked'})
    if eligible and meta['relevance']!='excluded' and needs_more and os.getenv('OWI_FULLTEXT_ENABLED','true').lower()=='true':
        # Atomically reserve one search per story per week, including failed/no-result searches.
        now=datetime.now(timezone.utc)
        with get_conn() as c:
            cursor=c.execute("""INSERT INTO news_open_search_attempts(raw_id,checked_at) VALUES(?,?)
                ON CONFLICT(raw_id) DO UPDATE SET checked_at=excluded.checked_at,result_count=0
                WHERE news_open_search_attempts.checked_at < ?""",(raw['id'],now.isoformat(),(now-timedelta(days=7)).isoformat()))
            search=cursor.rowcount>0
        if search:
            try:alternatives=alternative_sources(raw,ai)
            except Exception:alternatives=[]
            for alternative in alternatives:
                save(raw['id'],alternative['url'],alternative['title'],urlparse(alternative['url']).hostname or '',
                     'open','alternative_fulltext',alternative['text'],suggest=True)
            meta['alternatives']=json.dumps([{k:v for k,v in x.items() if k!='text'} for x in alternatives],ensure_ascii=False)
            if alternatives:meta.update(text=alternatives[0]['text'],source_url=alternatives[0]['url'],basis='alternative_fulltext')
            else:meta['reason']+='; Begrenset kildegrunnlag: ingen verifisert åpen alternativkilde funnet'
            with get_conn() as c:c.execute('UPDATE news_open_search_attempts SET result_count=? WHERE raw_id=?',(len(alternatives),raw['id']))
    with get_conn() as c:
        c.execute("""INSERT OR REPLACE INTO news_content_basis(raw_id,relevance,reason,access,basis,text,source_url,alternatives,checked_at)
            VALUES(:raw_id,:relevance,:reason,:access,:basis,:text,:source_url,:alternatives,:checked_at)""",meta)
    result=dict(raw);result['content_raw']=meta['text'];result['_content_basis']=meta
    return result
