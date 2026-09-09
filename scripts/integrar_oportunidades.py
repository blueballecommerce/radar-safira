"""Integra a aba e a correção de frete na página atual, sem substituir outras abas."""
import argparse
import re
from pathlib import Path


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Ponto de integração ausente ou ambíguo: ' + before[:100])
    return text.replace(before, after, 1)


def readings_hook(source):
    if 'window.RadarOportunidades?.leave(t)' not in source:
        source=replace_once(source,'function showTab(t){','function showTab(t){\n  window.RadarOportunidades?.leave(t);')
        source=replace_once(source,"history.replaceState(null,'','#oportunidades'); setTimeout", "if(!location.hash.startsWith('#oportunidades')) history.replaceState(null,'','#oportunidades'); setTimeout")
    if 'function fornProduto(root, F, productOverride=null)' not in source:
        source=replace_once(source,'function fornProduto(root, F){','function fornProduto(root, F, productOverride=null){')
        source=replace_once(source,"  const p = D.produtos.find(x=>x.url===forn.prod); if(!p)","  const p = productOverride || D.produtos.find(x=>x.url===forn.prod); if(!p)")
    source=re.sub(r'oportunidades\.(js|css)\?v=[^"\s]+',r'oportunidades.\1?v=20260909r5',source)
    source=re.sub(r'oportunidades-ficha.js\?v=[^"\s]+','oportunidades-ficha.js?v=20260909r5',source)
    if 'await window.RadarOportunidades.withReadings(forn.data)' not in source:
        source=replace_once(source,'    forn.data = await r.json();','    forn.data = await r.json();\n    try { forn.data = await window.RadarOportunidades.withReadings(forn.data); } catch(e) { /* Base original disponível; a aba exibe a falha da leitura. */ }')
    if 'src="oportunidades-ficha.js?' not in source:
        source=replace_once(source,'<script src="oportunidades.js?', '<script src="oportunidades-ficha.js?v=20260909r5"></script>\n<script src="oportunidades.js?')
    if 'window.RadarFichaOportunidades?.decorate(root,p)' not in source:
        source=replace_once(source,'  renderAlvos(p); renderCalc(p);', '  renderAlvos(p); renderCalc(p);\n  window.RadarFichaOportunidades?.decorate(root,p);')
    return source

def integrate(source):
    if 'src="oportunidades.js?' in source:
        return readings_hook(source)
    edits = [
        ('<meta name="color-scheme" content="light dark">', '<meta name="color-scheme" content="light dark">\n<link rel="stylesheet" href="oportunidades.css?v=20260909">'),
        ('    <button role="tab" data-tab="forn" aria-selected="false">Fornecedores</button>', '    <button role="tab" data-tab="forn" aria-selected="false">Fornecedores</button>\n    <button role="tab" data-tab="oport" aria-selected="false" aria-controls="tab-oport">Oportunidade de fornecedores</button>'),
        ('<!-- ================= SHOPEE ================= -->', '<section id="tab-oport" hidden aria-label="Oportunidade de fornecedores"><div id="oport-root"><p role="status">Carregando oportunidades…</p></div></section>\n<!-- ================= SHOPEE ================= -->'),
        ('<script src="concorrentes.js?', '<script src="oportunidades.js?v=20260909"></script>\n<script src="concorrentes.js?'),
        ("  if (t==='forn') setTimeout(fornLoad, 0);", "  if (t==='forn') setTimeout(fornLoad, 0);\n  if (t==='oport') { history.replaceState(null,'','#oportunidades'); setTimeout(()=>window.RadarOportunidades.load(), 0); }\n  else if(location.hash.startsWith('#oportunidades')) history.replaceState(null,'',location.pathname+location.search);"),
        ("const t=location.hash.startsWith('#concorrentes') ? 'conc' : localStorage.getItem('radar.tab');", "const t=location.hash.startsWith('#oportunidades') ? 'oport' : location.hash.startsWith('#concorrentes') ? 'conc' : localStorage.getItem('radar.tab');"),
        ('const FEES = {', 'const FEES = {\n  standardFree: true, // João confirmou entrega padrão em 09/09/2026.\n  offerFree: true, // Oferta de frete desta simulação; os anúncios usam seu próprio dado.'),
        ('<option value="0">0% (vendedor novo)</option>', '<option value="0" selected>0% (QuickBuy amarela; desconto não confirmado)</option>'),
        ('<option value="0.5" selected>50% (reputação verde)</option>', '<option value="0.5">50% (reputação verde)</option>'),
        ("  g.innerHTML=h;", '''  h+=`<label for="f-standard-free">Frete grátis de R$ 19 a R$ 78,99 pago pelo Mercado Livre (entrega padrão)</label><div><input id="f-standard-free" type="checkbox" ${FEES.standardFree?'checked':''}></div>`;
  h+=`<label for="f-offer-free">Oferecer frete grátis abaixo de R$ 79 nesta simulação</label><div><input id="f-offer-free" type="checkbox" ${FEES.offerFree?'checked':''}></div>`;
  g.innerHTML=h;'''),
        ("    if (t.id==='f-free') FEES.freeFrom=+t.value;", "    if (t.id==='f-free') FEES.freeFrom=+t.value;\n    if (t.id==='f-standard-free') FEES.standardFree=t.checked;\n    if (t.id==='f-offer-free') FEES.offerFree=t.checked;"),
        ('function calc(price, cost, cat, type, wi, rep, tax, other, ads){', 'function calc(price, cost, cat, type, wi, rep, tax, other, ads, freeShipping=false){'),
        ('  const taxV = price*tax/100, adsV = price*ads/100;', '''  if (price < FEES.freeFrom && freeShipping && !(FEES.standardFree && price>=19 && price<79)) {
    ship = (FEES.ship[wi]?.val||0)*(1-rep);
  }
  const taxV = price*tax/100, adsV = price*ads/100;'''),
        ('function priceForMargin(target, cost, cat, type, wi, rep, tax, other, ads){', 'function priceForMargin(target, cost, cat, type, wi, rep, tax, other, ads, freeShipping=false){'),
        ('calc(mid,cost,cat,type,wi,rep,tax,other,ads);', 'calc(mid,cost,cat,type,wi,rep,tax,other,ads,freeShipping);'),
        ('const r = calc(price,cost,cat,type,wi,rep,tax,other,ads);', 'const r = calc(price,cost,cat,type,wi,rep,tax,other,ads,FEES.offerFree);'),
        ('const need = priceForMargin(target,cost,cat,type,wi,rep,tax,other,ads);', 'const need = priceForMargin(target,cost,cat,type,wi,rep,tax,other,ads,FEES.offerFree);'),
        ("  const alt = price<FEES.freeFrom ?", "  if(price<FEES.freeFrom && r.ship) $('#s-led').insertAdjacentHTML('beforeend', `<tr><td>Frete grátis oferecido por você</td><td class=\"n\">− ${fmtBRL(r.ship)}</td></tr>`);\n  const alt = price<FEES.freeFrom ?"),
        ("  $('#s-note').textContent = alt +", "  $('#s-note').textContent = (FEES.standardFree ? 'Entrega padrão: de R$ 19 a R$ 78,99, envio pago pelo Mercado Livre, quando elegível. Abaixo de R$ 19 o frete grátis oferecido sai do vendedor. ' : 'Subsídio da entrega padrão desligado. Frete grátis oferecido sai do vendedor. ') + alt +"),
        ("function initSim(){", "function initSim(){"),
        ("  simulate();\n}\n\n/* ===================== toast", "  simulate();\n}\n\n/* ===================== toast"),
        ('function custoMaximo(m, preco, tipo, cat){', 'function custoMaximo(m, preco, tipo, cat, freteGratis=false){'),
        ('const r = calc(preco||0, 0, cat, tipo, o.wi, o.rep, o.tax, o.other, o.ads);', 'const r = calc(preco||0, 0, cat, tipo, o.wi, o.rep, o.tax, o.other, o.ads, freteGratis);'),
        ("rep:+($('#s-rep')?.value||0.5)", "rep:+($('#s-rep')?.value??0)"),
        ("tax:+($('#s-tax')?.value||6)", "tax:+($('#s-tax')?.value??6)"),
        ("other:+($('#s-other')?.value||1.5)", "other:+($('#s-other')?.value??1.5)"),
        ('''  const r = calc(preco, custo, cat, tipo, o.wi, o.rep, o.tax, o.other, o.ads);
  // frete grátis oferecido abaixo da linha dos R$ 79 é opcional — e sai do bolso de quem oferece
  const extra = (preco < FEES.freeFrom && freteGratis) ? (FEES.ship[o.wi]?.val||0)*(1-o.rep) : 0;
  const profit = r.profit - extra;
  return {...r, ship: r.ship + extra, profit, margin: preco ? profit/preco : 0,''', '''  const r = calc(preco, custo, cat, tipo, o.wi, o.rep, o.tax, o.other, o.ads, freteGratis);
  const profit = r.profit;
  return {...r, profit, margin: preco ? profit/preco : 0,'''),
        ('<b>pago pelo comprador</b>', '<b>${FEES.standardFree && preco>=19 && preco<79 ? "coberto pelo ML na entrega padrão elegível" : "sem custo de envio nesta conta"}</b>'),
    ]
    out=source
    for before, after in edits:
        out=replace_once(out,before,after)
    # Todas as contas dependentes acompanham qualquer mudança do Simulador.
    anchor="  $('#s-note').textContent = "
    start=out.index(anchor); end=out.index('\n}', start)
    out=out[:end]+"\n  setTimeout(()=>{ if(forn.data){ fornParaRadar(); renderML(true); if(!$('#tab-forn').hidden) fornRender(); window.RadarOportunidades?.refresh(); } },0);"+out[end:]
    return readings_hook(out)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();args.output.write_text(integrate(args.source.read_text('utf-8-sig')),encoding='utf-8')
