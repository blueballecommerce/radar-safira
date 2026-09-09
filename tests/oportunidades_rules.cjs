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
assert.equal(api.analyze(product({criadoEm:'2026-07-30'}),supplier,env).status,'Não vale o teste');
assert.equal(api.analyze(product({criadoEm:null,dias:7}),supplier,env).status,'Precisa de mais análise');
assert.equal(api.analyze(product({vendas_desde_criacao:0}),supplier,env).status,'Não vale o teste');
assert.equal(api.analyze(product({vendas_desde_criacao:null,vendas_mes:20,vendas_sem:5}),supplier,env).status,'Precisa de mais análise'); // janela parcial não comprova fracasso
let opener=product({catalogo:true,bb:11,preco:30.5,preco_min:23});opener.unit=9;
r=api.analyze(opener,supplier,env);assert.equal(r.status,'Não vale o teste');assert.match(r.reason,/fechado/);
let doll=product({veredito:'parecido',preco:42.41});doll.unit=9.98;doll.fornecedor='logospan';
r=api.analyze(doll,{regra:'Loja física, aceita quantidade menor que a caixa fechada'},env);assert.equal(r.status,'Promissor');assert.equal(r.approximate,true);assert.equal(api.analyze(doll,supplier,env),null);
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
console.log('Regras, janelas, kits, campos ausentes e fronteiras de frete: OK');
