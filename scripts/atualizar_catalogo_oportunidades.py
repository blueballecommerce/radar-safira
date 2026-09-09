"""Leitura pontual pública da Flexx; não altera o catálogo operacional."""
import sys,json,time
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radar.fornecedor import _cards,LISTA
import httpx
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'data/oportunidades/auditoria';out.mkdir(parents=True,exist_ok=True)
items={};pages=[]
checkpoint=out/'catalogo-site.json'
if checkpoint.exists():
 previous=json.loads(checkpoint.read_text('utf-8'))
 if previous.get('lidoEm','')[:10]==datetime.now(timezone.utc).date().isoformat():
  if previous.get('concluido'):print('Catálogo já lido por completo hoje.');sys.exit(0)
  items={p['url']:p for p in previous['produtos']};pages=previous['paginas']
def save(complete=False):
 snapshot={'lidoEm':datetime.now(timezone.utc).isoformat(),'fonte':'Site público Flexx Imports','paginas':pages,'produtos':list(items.values()),'concluido':complete,'nota':'Listagem pública não garante estoque nem prazo de reposição.'}
 (out/'catalogo-site.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),'utf-8')
with httpx.Client(timeout=30,follow_redirects=True,headers={'User-Agent':'Mozilla/5.0 (compatible; RadarSafira/1.0)'}) as client:
 for page in range(len(pages)+1,41):
  url=LISTA.format(n=page)
  try:response=client.get(url)
  except httpx.TransportError:
   time.sleep(2);response=client.get(url)
  if response.status_code==404 and items:save(True);break
  response.raise_for_status()
  cards=_cards(response.text)
  if not cards:save(True);break
  new=0
  for card in cards:
   if card.get('url') and card['url'] not in items:items[card['url']]=card;new+=1
  pages.append({'url':url,'itens':len(cards),'novos':new})
  save()
  print('Página',page,':',new,'novos;',len(items),'produtos',flush=True)
  if not new:save(True);break
  time.sleep(1.5)
print('Leitura salva, sem alterar fornecedores.json.')
