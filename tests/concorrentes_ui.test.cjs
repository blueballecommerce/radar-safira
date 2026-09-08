const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

const base = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(base, 'docs/concorrentes.js'), 'utf8');
const data = JSON.parse(fs.readFileSync(path.join(base, 'docs/concorrentes.json'), 'utf8'));
// UTC is already September 9; the user's Sao Paulo calendar is still September 8.
class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : ['2026-09-09T01:00:00Z'])); }
}

async function screen(fixture, hash) {
  const controls = new Map();
  const root = {innerHTML:'', querySelector(selector) {
    if(!controls.has(selector)) controls.set(selector, {innerHTML:'', value:'', addEventListener(){}});
    return controls.get(selector);
  }};
  const context = vm.createContext({Date:FixedDate, Intl, URL, AbortSignal,
    location:{hash}, window:{addEventListener(){}},
    document:{getElementById:()=>root, addEventListener(){}},
    fetch:async()=>({ok:true, json:async()=>fixture})});
  vm.runInContext(source, context);
  await context.window.RadarConcorrentes.load();
  return {html:root.innerHTML, rows:controls.get('#cx-results')?.innerHTML || ''};
}

function single(date, identified=true) {
  const fixture=structuredClone(data), seller=fixture.sellers[0], product=seller.products[0];
  seller.products=[product];
  product.hasListingMetrics=identified;
  seller.listings.find(l=>l.id===product.mainListingId).adPublishDate=date;
  return fixture;
}

test('creation age uses the Sao Paulo calendar, not activity days or UTC today', async()=>{
  const result=await screen(single('2026-09-07T23:59:00.000'), '#concorrentes/1806697386');
  assert.match(result.rows, /Criação: 07\/09\/2026/);
  assert.match(result.rows, /há 1 dia</);
  assert.match(result.rows, /calculados até 08\/09\/2026/);
});

test('same-day and leap-year creation dates calculate correctly', async()=>{
  let result=await screen(single('2026-09-08T00:00:00.000'), '#concorrentes/1806697386');
  assert.match(result.rows, /há 0 dias/);
  result=await screen(single('2024-02-29T00:00:00.000'), '#concorrentes/1806697386');
  assert.match(result.rows, /há 922 dias/);
});

test('missing, invalid, future and unrelated variant dates are not invented', async()=>{
  for(const date of [null, '', 'invalid', '2026-02-30T00:00:00.000']) {
    const result=await screen(single(date), '#concorrentes/1806697386');
    assert.match(result.rows, /Criação: Não informada/);
    assert.doesNotMatch(result.rows, /há \d+ dias?/);
  }
  const future=await screen(single('2026-09-09T00:00:00.000'), '#concorrentes/1806697386');
  assert.match(future.rows, /Data futura informada pela fonte/);
  const variant=await screen(single('2025-04-22T14:40:45.000',false), '#concorrentes/1806697386');
  assert.match(variant.rows, /Anúncio desta opção não identificado/);
  assert.doesNotMatch(variant.rows, /Criação: 22\/04\/2025/);
});

test('the row uses its main listing date and the sheet shows every linked listing date', async()=>{
  const fixture=structuredClone(data), seller=fixture.sellers[0];
  const product=seller.products.find(p=>p.hasListingMetrics && p.listings.length>1);
  seller.products=[product];
  product.listings.forEach((ref,i)=>{
    seller.listings.find(l=>l.id===ref.id).adPublishDate=`2026-09-0${i+1}T12:00:00.000`;
  });
  const row=await screen(fixture, '#concorrentes/'+seller.id);
  const first=product.listings.findIndex(ref=>ref.id===product.mainListingId)+1;
  assert.match(row.rows,new RegExp('Criação: 0'+first+'/09/2026'));
  assert.equal((row.rows.match(/class="cx-created"/g)||[]).length,1);
  const detail=await screen(fixture, '#concorrentes/'+seller.id+'/'+product.id);
  assert.match(detail.html,/Demais anúncios vinculados/);
  assert.equal((detail.html.match(/class="cx-created"/g)||[]).length,product.listings.length);
  product.listings.forEach((ref,i)=>assert.ok(detail.html.includes('Criação: 0'+(i+1)+'/09/2026')));
});
