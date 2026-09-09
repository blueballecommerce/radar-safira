"""Ordena candidatos para revisão humana/visual. Não aprova produtos."""
import json, math
from datetime import datetime
from collections import Counter
from auditar_oportunidades import tokens,norm,ROOT
from revisar_pares_oportunidades import pool

products,ads=pool()
freq=Counter(t for p in products for t in set(map(norm,tokens(p['nome']))))
result=[]
prepared=[]
for a in ads.values():
 try:days=(datetime(2026,9,9)-datetime.fromisoformat(a['criadoEm'][:10])).days
 except (ValueError,KeyError,TypeError):continue
 if not 1<=days<=40 or (a.get('vendas_mes') or 0)<days:continue
 if a.get('catalogo') and (a.get('bb') or 0)>=3:continue
 prepared.append((a,set(map(norm,tokens(a.get('nome','')))),days))
for ix,p in enumerate(products):
 ts=set(map(norm,tokens(p['nome'])));cost=p.get('unit')
 if not cost:continue
 for a,at,days in prepared:
  common=ts&at
  if len(common)<min(2,len(ts)):continue
  score=sum(math.log(771/(freq.get(t,0)+1)) for t in common)/max(sum(math.log(771/(freq.get(t,0)+1)) for t in ts),1)
  if score<.58:continue
  try:days=(datetime(2026,9,9)-datetime.fromisoformat(a['criadoEm'][:10])).days
  except (ValueError,KeyError,TypeError):continue
  if not 1<=days<=40 or (a.get('vendas_mes') or 0)<days:continue
  price=a.get('preco')
  if not price or not 1.6<=price/cost<=8:continue
  if a.get('catalogo') and (a.get('bb') or 0)>=3:continue
  result.append({'index':ix,'id':a['id'],'nome':p['nome'],'cost':cost,'qtd':None,'ad':a,'score':score,'age':days})
result.sort(key=lambda x:(-x['score'],-x['ad']['vendas_mes']))
(ROOT/'data/oportunidades/auditoria/prospectos.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
print(len(result),'candidatos: quantidade por kit ainda não verificada')
