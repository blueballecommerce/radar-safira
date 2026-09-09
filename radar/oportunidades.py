"""Exporta consultas pontuais salvas; nunca consulta a JoomPulse nem roda às 5h."""
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from . import config


def exportar(root=None):
    root=Path(root or config.ROOT);items={};sources=[];missing=set()
    audit=root/'data/oportunidades/auditoria';searches=[]
    paths=list((root/'data/oportunidades').glob('*.json'))+list(audit.glob('busca-*.json'))+list(audit.glob('detalhes-*.json'))
    fields={'productName':'nome','productImage':'img','merchantCategoryL1':'l1','priceAmount':'preco','orderCount1m':'vendas_mes','orderCount1w':'vendas_sem','catalogProduct':'catalogo','numBuyBoxSellers':'bb','reviewsCount':'avaliacoes','reviewsRating':'nota','isFull':'full','isFreeShipping':'frete_gratis','listingType':'tipo','merchantName':'vendedor','adPublishDate':'criadoEm','daysInAd':'dias','brand':'marca','productId':'productId'}
    for path in sorted(paths):
        doc=json.loads(path.read_text('utf-8-sig'))
        if not isinstance(doc,dict) or 'pages' not in doc:continue
        found=set()
        for page in doc['pages']:
            for values in page.get('data',[]):
                row=dict(zip(page['columns'],values));ident=row.get('id')
                if not ident:continue
                found.add(ident)
                entry={'created':row.get('adPublishDate'),'read':row.get('date'),'monthly':row.get('orderCount1m'),
                       'listingStatus':row.get('listingStatus'),'lidoEm':doc.get('lidoEm'),
                       'source':doc.get('fonte'),'sourceFile':str(path.relative_to(root)).replace('\\','/')}
                ad={dest:row[src] for src,dest in fields.items() if src in row}
                ad.update(id=ident,lidoEm=row.get('date'))
                # Preço de uma oferta NÃO é o piso do catálogo inteiro.
                if 'catalogProduct' in row:ad['preco_min']=row.get('priceAmount') if row['catalogProduct'] is False else row.get('catalogPriceMin')
                entry['ad']=ad
                old=items.get(ident)
                if old and entry['read'] and old['read']:
                    newer=(entry['read'],entry['lidoEm'] or '')>=(old['read'],old['lidoEm'] or '')
                else:
                    newer=not old or str(entry['lidoEm'] or '')>=str(old['lidoEm'] or '')
                if newer:
                    if old:
                        entry['ad']={**old.get('ad',{}),**ad}
                        if entry['created'] is None:entry['created']=old.get('created')
                    items[ident]=entry
            if doc.get('groups') is not None:searches.append({'groups':doc['groups'],'query':page.get('query',{}),'rows':len(page.get('data',[])),'lidoEm':doc.get('lidoEm')})
        missing.update(set(doc.get('requestedIds',[]))-found);sources.append(str(path.relative_to(root)).replace('\\','/'))
    pairfile=root/'data/oportunidades/pareamentos-revisados.json'
    pairs=json.loads(pairfile.read_text('utf-8')) if pairfile.exists() else []
    data={'geradoEm':datetime.now(timezone.utc).isoformat(),'anuncios':items,'naoRetornados':sorted(missing-items.keys()),'fontes':sources,'pareamentos':pairs,
          'nota':'Leituras pontuais por anúncio; preço e demanda têm a mesma data. Pareamentos novos exigem revisão explícita. Nenhuma leitura na rotina diária.'}
    data['auditoria']={'revisaoObrigatoria':pairfile.exists(),'nota':'Após os falsos pareamentos encontrados, só referências reconferidas podem ser Promissor.'}
    statusfile=audit/'status.json'
    if statusfile.exists():data['auditoria']['coleta']=json.loads(statusfile.read_text('utf-8'))
    sitefile=audit/'catalogo-site.json'
    if sitefile.exists():
        site=json.loads(sitefile.read_text('utf-8'))
        data['catalogoAtual']={'lidoEm':site['lidoEm'],'total':len(site['produtos']),'concluido':site.get('concluido',False),'produtos':{p['url']:{'unit':p.get('unit'),'caixa':p.get('caixa')} for p in site['produtos']}}
    planfile=audit/'plano.json'
    if planfile.exists():
        plan=json.loads(planfile.read_text('utf-8'));coverage={}
        normalize=lambda s:''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn')
        for group in plan['grupos']:
            pages=[s for s in searches if group['terms'] in s['groups']]
            complete=bool(pages) and any(s['rows']<s['query'].get('limit',100) for s in pages)
            candidates=[i for i,e in items.items() if all(normalize(t) in normalize(e.get('ad',{}).get('nome','')) for t in group['terms'])]
            for url in group['urls']:
                coverage[url]={'termos':group['terms'],'buscado':bool(pages),'paginacaoCompleta':complete,'candidatos':len(candidates),'revisados':sum(p['url']==url for p in pairs),'lidoEm':max((s['lidoEm'] or '' for s in pages),default=None)}
        data['cobertura']={'total':plan['catalogo'],'pesquisadosAntes':219,'buscados':sum(c['buscado'] for c in coverage.values()),'comPareamentoRevisado':len({p['url'] for p in pairs}),'produtos':coverage}
    destination=root/'docs/oportunidades.json';destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    return data


if __name__=='__main__':
    d=exportar();print(json.dumps({'anuncios':len(d['anuncios']),'naoRetornados':d['naoRetornados']},ensure_ascii=False))
