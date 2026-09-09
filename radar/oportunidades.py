"""Exporta consultas pontuais salvas; nunca consulta a JoomPulse nem roda às 5h."""
import json
from datetime import datetime, timezone
from pathlib import Path
from . import config


def exportar(root=None):
    root=Path(root or config.ROOT);items={};sources=[];missing=set()
    for path in sorted((root/'data/oportunidades').glob('*.json')):
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
                if ident not in items or str(entry['read'] or '')>=str(items[ident]['read'] or ''):items[ident]=entry
        missing.update(set(doc.get('requestedIds',[]))-found);sources.append(str(path.relative_to(root)).replace('\\','/'))
    data={'geradoEm':datetime.now(timezone.utc).isoformat(),'anuncios':items,'naoRetornados':sorted(missing-items.keys()),'fontes':sources,
          'nota':'Datas e demanda pontual. Preços e composição continuam os de fornecedores.json. Nenhuma leitura na rotina diária.'}
    destination=root/'docs/oportunidades.json';destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    return data


if __name__=='__main__':
    d=exportar();print(json.dumps({'anuncios':len(d['anuncios']),'naoRetornados':d['naoRetornados']},ensure_ascii=False))
