"""Triagem de todo o catálogo: candidatos por texto nunca viram pareamento confirmado."""
import json,re,unicodedata,math
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STOP=set('de da do das dos e com para por em a o os as um uma sem kit pacote par mini produto novo nova cor cores sortido sortidas sortidos modelo original profissional portátil portatil elétrico elétrica eletrico eletrica automático automática automatico automatica universal peças pecas unidade unidades tamanho grande pequeno premium'.split())
def tokens(s):
    return [x for x in re.findall(r'[a-zA-ZÀ-ÿ0-9]+',s.lower()) if len(x)>2 and x not in STOP and not x.isdigit()]
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
def prepare():
    data=json.loads((ROOT/'docs/fornecedores.json').read_text('utf-8'));market=json.loads((ROOT/'docs/data.json').read_text('utf-8'))
    products=data['produtos']; freq=Counter(t for p in products for t in set(map(norm,tokens(p['nome']))))
    postings={};mt={}
    for a in market['products']:
        ts=set(map(norm,tokens(a['n'])));mt[a['i']]=ts
        for t in ts:postings.setdefault(t,[]).append(a)
    pairs=[];groups={}
    for p in products:
        ts=list(dict.fromkeys(tokens(p['nome'])));normalized=set(map(norm,ts))
        # Duas palavras iniciais descrevem a família; serve apenas para BUSCAR.
        terms=ts[:2] or [p['nome']]
        key='|'.join(terms);groups.setdefault(key,{'terms':terms,'urls':[]})['urls'].append(p['url'])
        candidates={a['i']:a for t in normalized for a in postings.get(t,[])}
        scored=[]
        for a in candidates.values():
            common=normalized&mt[a['i']]
            if len(common)<2:continue
            score=sum(math.log(771/(freq.get(t,0)+1)) for t in common)/max(sum(math.log(771/(freq.get(t,0)+1)) for t in normalized),1)
            if score>=.45:scored.append({'score':round(score,3),'anuncio':a})
        pairs.append({'url':p['url'],'nome':p['nome'],'pesquisado':p['pesquisado'],'custo':p.get('unit'),'terms':terms,'candidatos':sorted(scored,key=lambda x:(-x['score'],-(x['anuncio'].get('m') or 0)))[:8]})
    output=ROOT/'data/oportunidades/auditoria';output.mkdir(parents=True,exist_ok=True)
    (output/'catalogo-cruzado.json').write_text(json.dumps(pairs,ensure_ascii=False,indent=2),'utf-8')
    plan={'geradoEm':'2026-09-09','catalogo':len(products),'grupos':list(groups.values()),'nota':'Busca por família cobre todos os SKUs; resultados de texto exigem conferência visual antes de aprovação.'}
    (output/'plano.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'catalogo':len(products),'pesquisados_antes':sum(p['pesquisado'] for p in products),'familias':len(groups),'com_candidatos_locais':sum(bool(p['candidatos']) for p in pairs)}))
if __name__=='__main__':prepare()
