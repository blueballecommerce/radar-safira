"""Teste real de navegador com dados em rotas isoladas, sem editar os JSONs."""
import functools
import http.server
import json
import os
from pathlib import Path
import threading
import subprocess
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('RADAR_TEST_OUTPUT',str(ROOT/'data/oportunidades/testes')))
OUT.mkdir(parents=True,exist_ok=True)

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

server=http.server.ThreadingHTTPServer(('127.0.0.1',8090),functools.partial(Quiet,directory=str(ROOT/'docs')))
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1440,'height':950},timezone_id='America/Sao_Paulo',color_scheme='dark')
    page=context.new_page();errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    # Terceiros não fazem parte do teste funcional e não consomem rede/token.
    def external(route):
        if route.request.url.startswith('http://127.0.0.1:8090/'):
            if route.request.url.endswith('/favicon.ico'):route.fulfill(status=204)
            else:route.continue_()
        elif route.request.resource_type=='image':route.fulfill(status=200,content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60"><rect width="60" height="60" fill="#eee"/></svg>')
        else:route.fulfill(status=200,body='')
    page.route('**/*',external)
    page.goto('http://127.0.0.1:8090/#oportunidades')
    page.wait_for_selector('.ot-card')
    page.wait_for_function('typeof S!=="undefined" && S.products.length>0')
    page.evaluate('window.RadarOportunidades.load()')
    historic=json.loads(subprocess.check_output(['git','show','0c9b76c:docs/data.json'],cwd=ROOT))
    baseline=page.evaluate('''old => {const saved=S;const rep=$('#s-rep').value;const free=FEES.standardFree;
      S=old;$('#s-rep').value='0.5';FEES.standardFree=false;fornParaRadar();
      const rows=FORN_ROWS.filter(r=>r.opp.cor!=='vermelho').map(r=>({nome:r.n,url:r._forn.url,opp:r.opp}));
      S=saved;$('#s-rep').value=rep;FEES.standardFree=free;fornParaRadar();return rows;}''',historic)
    assert page.locator('[data-tab=oport]').get_attribute('aria-selected')=='true'
    assert page.locator('.ot-card[data-status="Não vale o teste"]').count()==0
    page.locator('#ot-own').focus();page.keyboard.press('Space')
    assert page.locator('#ot-own').is_checked()
    page.keyboard.press('Space')
    page.locator('#ot-all').click()
    page.locator('#ot-query').fill('Caneta Impressora 3D')
    page.wait_for_selector('.ot-card')
    card=page.locator('.ot-card').first
    assert card.locator('a').count()==1 and card.locator('a').inner_text()=='Mercado Livre ↗'
    page.screenshot(path=str(OUT/'oportunidades-desktop.png'),full_page=True)
    assert card.locator('.ot-metrics').count()==0
    assert card.bounding_box()['height']<240
    card.focus();page.keyboard.press('Enter')
    assert page.locator('#tab-oport').is_visible()
    assert page.locator('[data-tab=oport]').get_attribute('aria-selected')=='true'
    assert '#oportunidades/produto/' in page.url
    page.wait_for_selector('.ot-sheet-summary')
    expected=page.evaluate('forn.data.produtos.find(p=>p.url===forn.prod).anuncios.filter(a=>RadarOportunidades.isRecent(a,RadarOportunidades.context())).length')
    assert page.locator('#ot-sheet .ot-rival').count()>=expected
    assert page.evaluate("[...document.querySelectorAll('#ot-sheet .ot-rival')].every(e=>{const a=forn.data.produtos.find(p=>p.url===forn.prod).anuncios.find(a=>a.id===e.dataset.rival);return !a||RadarOportunidades.isRecent(a,RadarOportunidades.context())})")
    assert 'somando' not in page.locator('.ot-sheet-summary').inner_text()
    market_search=page.locator('.ot-market-search a')
    assert market_search.inner_text()=='Pesquisar no Mercado Livre ↗'
    assert market_search.get_attribute('href').startswith('https://lista.mercadolivre.com.br/Caneta-Impressora-3D')
    assert market_search.get_attribute('target')=='_blank'
    categories=page.locator('.ot-category-panel')
    assert categories.count()==1 and not categories.get_attribute('open')
    categories.locator('summary').click()
    assert categories.locator('.ot-category-card').count()>=1
    assert all('Clássico' in categories.locator('.ot-category-card').nth(i).inner_text() and 'Premium' in categories.locator('.ot-category-card').nth(i).inner_text() for i in range(categories.locator('.ot-category-card').count()))
    assert page.evaluate("[...document.querySelectorAll('.ot-category-card')].every(e=>{const l1=e.querySelector('h4').textContent.split(' › ')[0];const values=[...e.querySelectorAll('.ot-category-fee b')].map(x=>Number(x.textContent.replace('%','').replace(',','.')));return FEES.comm[l1]&&values[0]===FEES.comm[l1][0]&&values[1]===FEES.comm[l1][1]})")
    assert page.locator('.ot-market-proof').count()==1
    assert '35' in page.locator('.ot-market-proof').inner_text()
    assert page.locator('.ot-unreviewed .ot-rival').count()>=1
    page.screenshot(path=str(OUT/'ficha-pesquisa-categorias.png'),full_page=True)
    original_url=page.url
    page.locator('[data-tab=sim]').click()
    page.locator('[data-tab=oport]').click();page.wait_for_selector('#ot-sheet .ot-rival')
    assert page.url==original_url
    rival=page.locator('#ot-sheet .ot-rival').first
    assert 'Vendas desde: não coletada' in rival.inner_text()
    assert 'Nota ' in rival.inner_text() and 'Criado em ' in rival.inner_text()
    rival.locator('button[data-compare]').last.click()
    assert page.locator('#ot-compare').is_visible()
    assert page.locator('#ot-compare img').count()==2
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), page.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,10).map(e=>[e.tagName,e.id,e.className,e.getBoundingClientRect().width])")
    page.keyboard.press('Escape')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), page.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,10).map(e=>[e.tagName,e.id,e.className,e.getBoundingClientRect().width])")
    page.locator('.ot-category-panel summary').click()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Categorias excedem a largura no celular'
    page.screenshot(path=str(OUT/'ficha-mobile.png'))
    page.locator('.ot-back').click();page.wait_for_selector('.ot-card')
    assert page.locator('#ot-query').input_value()=='Caneta Impressora 3D'
    page.set_viewport_size({'width':1440,'height':950})
    page.locator('[data-tab=oport]').click();page.wait_for_selector('.ot-card')
    before=page.evaluate('RadarOportunidades.rows().find(r=>r.name==="Caneta Impressora 3D").classic?.profit')
    page.locator('[data-tab=sim]').click()
    page.locator('details:has(#fee-grid) summary').click()
    page.locator('#f-standard-free').uncheck()
    page.wait_for_timeout(100)
    page.locator('[data-tab=oport]').click();page.wait_for_selector('.ot-card')
    after=page.evaluate('RadarOportunidades.rows().find(r=>r.name==="Caneta Impressora 3D").classic?.profit')
    if before is not None:assert after<before
    page.locator('[data-tab=sim]').click();page.locator('#f-standard-free').check();page.wait_for_timeout(100)
    page.locator('[data-tab=oport]').click();page.wait_for_selector('.ot-card')
    rows=page.evaluate('RadarOportunidades.rows()')
    (OUT/'resultado-real.json').write_text(json.dumps({'rows':rows,'baseline':baseline,'radar':page.evaluate('FORN_ROWS.map(r=>({nome:r.n,url:r._forn.url,opp:r.opp}))')},ensure_ascii=False,indent=2),'utf-8')
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/'oportunidades-mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'), 'Rolagem horizontal'
    page.locator('#ot-query').fill('Repetidor de Wifi')
    page.locator('.ot-card').first.click();page.wait_for_selector('.ot-sheet-summary')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Calculadora da bolsa excede a largura'
    page.locator('.ot-back').click();page.wait_for_selector('.ot-card')
    # Três classificações reais na tela, com um conjunto pequeno e determinístico.
    page.evaluate('''() => {
      const base=structuredClone(forn.data.produtos.find(p=>p.nome==='Caneta Impressora 3D'));
      const now=new Date(); const created=new Date(now.getTime()-20*864e5).toISOString().slice(0,10);
      base.nome='Caso promissor';base.url='fixture:promissor';base.unit=10;
      base.anuncios=[{id:'MLBTEST1',nome:'Teste A',vendedor:'LOJA A',revisadoEm:now.toISOString(),veredito:'igual',qtd:1,preco:60,vendas_mes:20,vendas_sem:7,vendas_desde_criacao:20,criadoEm:created,lidoEm:now.toISOString(),catalogo:false,avaliacoes:2,frete_gratis:true,l1:'Brinquedos e Hobbies'}];
      base.anuncios.push({...base.anuncios[0],id:'MLBTEST2',nome:'Teste B',vendedor:'LOJA B'});base._coverage={buscado:true,paginacaoCompleta:true,candidatos:2,revisados:2,lidoEm:now.toISOString()};
      const pending=structuredClone(base);pending.nome='Caso pendente';pending.url='fixture:pendente';pending.anuncios.forEach(a=>a.qtd=null);
      const closed=structuredClone(base);closed.nome='Caso fechado';closed.url='fixture:fechado';closed.anuncios.forEach(a=>{a.catalogo=true;a.bb=6;a.preco_min=60});
      forn.data.produtos=[base,pending,closed];
    }''')
    page.evaluate('RadarOportunidades.load()');page.locator('#ot-query').fill('')
    for classification in ['Promissor','Precisa de mais análise','Não vale o teste']:
        assert page.locator('.ot-card[data-status="'+classification+'"]').count()==1,classification
    page.locator('#ot-all').click();assert page.locator('.ot-card[data-status="Não vale o teste"]').count()==0
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    # Links da ficha reabrem no mesmo produto e na mesma aba, inclusive após recarregar.
    restored=context.new_page();restored.route('**/*',external)
    restored.on('pageerror',lambda e:errors.append(str(e)))
    restored.goto(original_url);restored.wait_for_selector('#ot-sheet .ot-rival')
    restored.reload();restored.wait_for_selector('#ot-sheet .ot-rival')
    assert restored.locator('[data-tab=oport]').get_attribute('aria-selected')=='true'
    assert restored.locator('#tab-forn').is_hidden()
    assert restored.url==original_url
    restored.locator('[data-tab=forn]').click();restored.wait_for_selector('#forn-root .ot-rival')
    assert restored.locator('#ot-sheet').count()==0
    restored.close()
    assert not errors, errors
    print('Chromium limpo: aba, 3 classificações, Ver ficha, recálculo de frete, celular e console OK.')
    print('Resultado e capturas: '+str(OUT))
    context.close();browser.close()
finally:server.shutdown();server.server_close()
