const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..'),api=require(path.join(root,'docs/oportunidades.js'));
const html=fs.readFileSync(path.join(root,'docs/index.html'),'utf8');
function fn(name){const start=html.indexOf('function '+name+'(');assert.ok(start>=0,name);const end=html.indexOf('\n}',start);return html.slice(start,end+2);}
const values={'#s-weight':'0','#s-rep':'0','#s-tax':'6','#s-other':'1.5','#s-ads':'0'};
const ctx=vm.createContext({$:id=>({value:values[id]})});
vm.runInContext(html.slice(html.indexOf('const FEES = {'),html.indexOf('function feeGrid()'))+['calc','simOpts','extrato','custoMaximo'].map(fn).join('\n')+'\nglobalThis.shared={FEES,calc,extrato,custoMaximo,simOpts};',ctx);
const shared=ctx.shared;
const supplier={id:'flexx',nome:'Flexx',regra:'Vende apenas caixa fechada'};
const env={extrato:shared.extrato,max:shared.custoMaximo,cat:()=> 'Brinquedos e Hobbies',score:(m,v)=>({pontos:(m||0)*60+Math.log1p(v||0)*40}),rows:[],dates:{},exported:'2026-09-09',now:'2026-09-09',catalogLimits:[3,6],ownLimits:[1000,10000]};
function product(changes={}){return {url:'test:item',nome:'Produto',fornecedor:'flexx',pesquisado:true,unit:23.5,caixa:120,tags:[],anuncios:[{id:'MLB1',preco:61.49,qtd:1,veredito:'igual',catalogo:false,avaliacoes:3314,vendas_mes:40,vendas_sem:10,vendas_desde_criacao:40,criadoEm:'2026-07-31',lidoEm:'2026-09-09',frete_gratis:true,...changes}]};}
let r=api.analyze(product(),supplier,env);assert.equal(r.status,'Promissor');assert.ok(Math.abs(r.classic.profit-18.97925)<1e-6);assert.equal(r.capital,2820);assert.equal(r.demand.daily,1);assert.equal(r.entrance,'disputada');
assert.equal(api.analyze(product({criadoEm:'2026-07-26'}),supplier,env).status,'Precisa de mais análise'); // anúncio antigo sozinho não reprova a família
assert.equal(api.analyze(product({criadoEm:null,dias:7}),supplier,env).status,'Precisa de mais análise');
assert.equal(api.analyze(product({vendas_desde_criacao:0}),supplier,env).status,'Não vale o teste');
assert.equal(api.analyze(product({vendas_desde_criacao:null,vendas_mes:20,vendas_sem:5}),supplier,env).status,'Precisa de mais análise'); // janela parcial não comprova fracasso
let opener=product({catalogo:true,bb:11,preco:30.5,preco_min:23});opener.unit=9;
r=api.analyze(opener,supplier,env);assert.equal(r.status,'Não vale o teste');assert.match(r.reason,/fechado/);
let doll=product({veredito:'parecido',preco:42.41});doll.unit=9.98;doll.fornecedor='logospan';
r=api.analyze(doll,{regra:'Loja física, aceita quantidade menor que a caixa fechada'},env);assert.equal(r.status,'Promissor');assert.equal(r.approximate,true);assert.equal(api.analyze(doll,supplier,env).status,'Promissor'); // João autorizou similares também em caixa, com condição.
assert.equal(api.analyze(product({catalogo:true,bb:6,preco_min:61.49}),supplier,env).status,'Não vale o teste');
assert.equal(api.analyze(product({catalogo:true,bb:2,preco_min:61.49}),supplier,env).status,'Promissor');
assert.equal(api.analyze(product({qtd:null}),supplier,env).classic,null);
let p=product();p.anuncios.push({...p.anuncios[0],id:'MLB2',vendas_mes:30,preco:59});r=api.analyze(p,supplier,env);assert.equal(r.monthly,40);assert.equal(r.ads.length,2);
assert.equal(api.age('2026-02-30','2026-09-09'),null);assert.equal(api.age('2026-09-10','2026-09-09'),null);
assert.equal(shared.simOpts().rep,0);values['#s-tax']='0';values['#s-other']='0';assert.equal(shared.simOpts().tax,0);assert.equal(shared.simOpts().other,0);values['#s-tax']='6';values['#s-other']='1.5';
for(const enabled of [true,false])for(const price of [18.99,19,78.99,79])for(const free of [true,false]){
 shared.FEES.standardFree=enabled;
 const e=shared.extrato(price,'c','Brinquedos e Hobbies',5,free),c=shared.calc(price,5,'Brinquedos e Hobbies','c',0,0,6,1.5,0,free);
 assert.equal(e.profit,c.profit);assert.equal(e.ship,price>=79||(free&&!(enabled&&price>=19))?20.9:0);
 const max=shared.custoMaximo(.2,price,'c','Brinquedos e Hobbies',free);assert.ok(Math.abs(shared.extrato(price,'c','Brinquedos e Hobbies',max,free).margin-.2)<1e-10);
}
assert.ok(api.csv([]).includes('produto'));assert.ok(api.csv([r]).includes('referencia_aproximada'));
shared.FEES.standardFree=true;
// A idade e a margem do líder NÃO contaminam a oportunidade de outro anúncio.
let mixed=product({id:'OLD',criadoEm:'2025-01-01',vendas_mes:3000});
mixed.anuncios.push({...product().anuncios[0],id:'NEW',vendas_mes:40});
let chosen=api.analyze(mixed,supplier,env);
assert.equal(chosen.status,'Promissor');assert.equal(chosen.ref.id,'NEW');assert.equal(chosen.leader.id,'OLD');assert.equal(chosen.monthly,40);assert.equal(chosen.evaluated.length,2);
mixed=product({id:'CAT',catalogo:true,bb:20,preco_min:20,vendas_mes:3000});
mixed.anuncios.push({...product().anuncios[0],id:'OWN'});
chosen=api.analyze(mixed,supplier,env);assert.equal(chosen.ref.id,'OWN');assert.equal(chosen.status,'Promissor');
// O pareamento contestado nunca aprova, mesmo com margem e demanda suficientes.
assert.equal(api.analyze(product({id:'MLB7314817188'}),supplier,env).status,'Precisa de mais análise');
const fresh={anuncios:{MLB1:{ad:{id:'MLB1',preco:42,vendas_mes:50,lidoEm:'2026-09-08'}}},pareamentos:[]};
const enriched=api.enrich({produtos:[product()]},fresh).produtos[0];
assert.equal(enriched.anuncios[0].preco,42);assert.equal(enriched.anuncios[0].qtd,1);assert.equal(enriched.anuncios[0].veredito,'igual');
assert.equal(product().anuncios[0].preco,61.49); // sem mutar a fonte
const dated={anuncios:{MLB1:{lidoEm:'2026-09-09T18:00:00Z',created:'2026-08-20',monthly:40,ad:{preco:60}}}};
const radar={meta:{generatedAt:'2026-09-10T08:00:00Z'},products:[{i:'MLB1',pr:50,m:80,c:false}]};
const live=api.latestReadings(dated,radar).anuncios.MLB1;
assert.equal(live.ad.preco,50);assert.equal(live.monthly,80);assert.equal(live.created,'2026-08-20');assert.equal(live.read,null);assert.equal(dated.anuncios.MLB1.ad.preco,60);
radar.meta.generatedAt='2026-09-09T10:00:00Z';assert.equal(api.latestReadings(dated,radar).anuncios.MLB1.ad.preco,60);
const catalog={produtos:[{url:'supplier:1',nome:'Caneta impressora',anuncios:[]}]};
const market={products:[{i:'NEW',n:'Caneta impressora 3D',pub:'2026-08-20',m:30,pr:50},{i:'OLD',n:'Caneta impressora 3D',pub:'2025-01-01',m:5000,pr:50},{i:'WEAK',n:'Caneta impressora 3D',pub:'2026-08-20',m:1,pr:50}]};
const suggestions=api.discover(catalog,market,s=>new Set(s.toLowerCase().split(' ')),()=>false,'2026-09-09');
assert.deepEqual(suggestions['supplier:1'].map(x=>x.id),['NEW']);assert.equal(catalog.produtos[0].anuncios.length,0);
console.log('Regras, janelas, kits, campos ausentes e fronteiras de frete: OK');

// 45 dias já é antigo. Dias de atividade não substituem data de criação.
assert.equal(api.CONFIG.idade,45);
assert.equal(api.isRecent({criadoEm:'2026-07-27'},env),true);
assert.equal(api.isRecent({criadoEm:'2026-07-26'},env),false);
assert.equal(api.isRecent({criadoEm:null,dias:2},env),false);
assert.equal(api.analyze(product({criadoEm:'2026-07-27',vendas_desde_criacao:44}),supplier,env).status,'Promissor');
// Uma referência antiga pendente não ocupa o lugar da referência recente, mesmo reprovada.
const wrongChoice=product({id:'OLD',criadoEm:'2025-01-01',vendas_mes:5000});
wrongChoice.anuncios.push({...product().anuncios[0],id:'RECENT',preco:5});
assert.equal(api.analyze(wrongChoice,supplier,env).ref.id,'RECENT');
