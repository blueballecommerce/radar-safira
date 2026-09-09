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
    context=browser.new_context(viewport={'width':1440,'height':950},timezone_id='America/Sao_Paulo')
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
    page.locator('#ot-all').click()
    page.locator('#ot-query').fill('Caneta Impressora 3D')
    page.wait_for_selector('.ot-card')
    card=page.locator('.ot-card').first
    assert card.locator('a').count()==1 and card.locator('a').inner_text()=='Mercado Livre ↗'
    page.screenshot(path=str(OUT/'oportunidades-desktop.png'),full_page=True)
    card.locator('[data-sheet]').click()
    assert page.locator('#tab-forn').is_visible()
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
    # Três classificações reais na tela, com um conjunto pequeno e determinístico.
    page.evaluate('''() => {
      const base=structuredClone(forn.data.produtos.find(p=>p.nome==='Caneta Impressora 3D'));
      const now=new Date(); const created=new Date(now.getTime()-20*864e5).toISOString().slice(0,10);
      base.nome='Caso promissor';base.url='fixture:promissor';base.unit=10;
      base.anuncios=[{id:'MLBTEST1',nome:'Teste',revisadoEm:now.toISOString(),veredito:'igual',qtd:1,preco:60,vendas_mes:20,vendas_sem:7,vendas_desde_criacao:20,criadoEm:created,lidoEm:now.toISOString(),catalogo:false,avaliacoes:2,frete_gratis:true,l1:'Brinquedos e Hobbies'}];
      const pending=structuredClone(base);pending.nome='Caso pendente';pending.url='fixture:pendente';pending.anuncios[0].criadoEm=null;
      const closed=structuredClone(base);closed.nome='Caso fechado';closed.url='fixture:fechado';closed.anuncios[0].catalogo=true;closed.anuncios[0].bb=6;closed.anuncios[0].preco_min=60;
      forn.data.produtos=[base,pending,closed];
    }''')
    page.evaluate('RadarOportunidades.load()');page.locator('#ot-query').fill('')
    for classification in ['Promissor','Precisa de mais análise','Não vale o teste']:
        assert page.locator('.ot-card[data-status="'+classification+'"]').count()==1,classification
    page.locator('#ot-all').click();assert page.locator('.ot-card[data-status="Não vale o teste"]').count()==0
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    assert not errors, errors
    print('Chromium limpo: aba, 3 classificações, Ver ficha, recálculo de frete, celular e console OK.')
    print('Resultado e capturas: '+str(OUT))
    context.close();browser.close()
finally:server.shutdown();server.server_close()
