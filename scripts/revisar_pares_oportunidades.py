"""Pranchas locais de evidências; não altera nem aprova pareamentos."""
import json,html,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/oportunidades/auditoria'
def pool():
 f=json.loads((ROOT/'docs/fornecedores.json').read_text('utf-8'));m=json.loads((ROOT/'docs/data.json').read_text('utf-8'));ads={}
 for p in f['produtos']:
  for a in p.get('anuncios',[]):ads[a['id']]=a
 for a in m['products']:
  ads[a['i']]={'id':a['i'],'nome':a['n'],'img':a['img'],'preco':a['pr'],'vendas_mes':a['m'],'criadoEm':a.get('pub'),'catalogo':a['c'],'bb':a.get('bb'),'l1':a['l1'],'avaliacoes':a.get('rc'),'frete_gratis':a.get('fs')}
 names={'productName':'nome','productImage':'img','priceAmount':'preco','orderCount1m':'vendas_mes','adPublishDate':'criadoEm','catalogProduct':'catalogo','numBuyBoxSellers':'bb','merchantCategoryL1':'l1','reviewsCount':'avaliacoes','isFreeShipping':'frete_gratis'}
 for path in list(OUT.glob('busca-*.json'))+list(OUT.glob('detalhes-*.json')):
  for page in json.loads(path.read_text('utf-8')).get('pages',[]):
   for values in page.get('data',[]):
    r=dict(zip(page['columns'],values));i=r['id'];ads[i]={**ads.get(i,{}),'id':i,**{v:r[k] for k,v in names.items() if k in r}}
 return f['produtos'],ads
def make(spec):
 products,ads=pool();pairs=json.loads(Path(spec).read_text('utf-8'));cards=[]
 for idx,pair in enumerate(pairs):
  p=products[pair['index']];a=ads[pair['id']];esc=html.escape
  def picture(src):
   if src and not src.startswith('http'):src=(ROOT/'docs'/src).as_uri()
   return '<img src="'+esc(src or '')+'">'
  cards.append('<article><h3>'+str(idx)+' · '+esc(p['nome'])+'</h3><p>Fornecedor R$ '+str(p.get('unit'))+' · anúncio R$ '+str(a.get('preco'))+' · mês '+str(a.get('vendas_mes'))+'</p><div>'+picture(p.get('img'))+picture(a.get('img'))+'</div><p>'+esc(a['id']+' · '+a.get('nome',''))+'</p></article>')
 for start in range(0,len(cards),6):
  text='<!doctype html><meta charset="utf-8"><style>body{font:14px Arial;background:#eee;margin:12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}article{background:white;padding:12px;height:400px}h3{font-size:16px;margin:0}p{margin:6px 0}article div{display:flex;height:285px}img{width:50%;height:100%;object-fit:contain}</style><div class="grid">'+''.join(cards[start:start+6])+'</div>'
  (OUT/('prancha-'+str(start//6)+'.html')).write_text(text,'utf-8')
 print(len(cards),'pares preparados')
if __name__=='__main__':make(sys.argv[1])
