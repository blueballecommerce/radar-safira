/* Independent read-only module; does not mutate the existing Radar datasets. */
(() => {
  'use strict';
  const state = {data:null, request:null, seller:null, product:null, q:'', category:'', sort:'sales', shown:30};
  const root = () => document.getElementById('conc-root');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
  const number = value => value == null ? 'Não informado' : new Intl.NumberFormat('pt-BR',{maximumFractionDigits:0}).format(value);
  const money = value => value == null ? 'Não informado' : new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(value);
  const percent = value => value == null ? 'Não informado' : new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2}).format(value)+'%';
  const date = value => value ? new Intl.DateTimeFormat('pt-BR',{timeZone:'UTC'}).format(new Date(value)) : 'Não informado';
  const yes = value => value == null ? 'Não informado' : value ? 'Sim' : 'Não';
  const norm = value => String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const link = (url,label,accessibleLabel=label) => {
    try { const u=new URL(url); if(!['https:','http:'].includes(u.protocol)) return esc(label); }
    catch { return esc(label); }
    return '<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer" aria-label="'+esc(accessibleLabel)+' (abre em outra aba)">'+esc(label)+' ↗</a>';
  };
  const metric = (value,label) => '<div class="cx-metric"><strong>'+esc(value)+'</strong><span>'+esc(label)+'</span></div>';
  const badge = (label,kind='') => '<span class="cx-badge '+kind+'">'+esc(label)+'</span>';
  const calendarDay = value => {
    const parts = /^(\d{4})-(\d{2})-(\d{2})(?:T|$)/.exec(String(value||''));
    if(!parts) return null;
    const [year,month,day]=parts.slice(1).map(Number), stamp=Date.UTC(year,month-1,day), parsed=new Date(stamp);
    return parsed.getUTCFullYear()===year && parsed.getUTCMonth()===month-1 && parsed.getUTCDate()===day ? stamp : null;
  };
  const todayDay = () => {
    const parts=Object.fromEntries(new Intl.DateTimeFormat('en',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).map(p=>[p.type,p.value]));
    return calendarDay(parts.year+'-'+parts.month+'-'+parts.day);
  };
  function creationInfo(listing,identified=true) {
    const created=identified?calendarDay(listing.adPublishDate):null;
    if(created===null) return {date:'Não informada',age:identified?'Data de criação não disponível na fonte':'Anúncio desta opção não identificado'};
    const days=Math.round((todayDay()-created)/86400000);
    if(days<0) return {date:'A conferir',age:'Data futura informada pela fonte'};
    return {date:date(created),age:'há '+number(days)+(days===1?' dia':' dias')};
  }
  function creationBlock(listing,identified=true) {
    const info=creationInfo(listing,identified);
    return '<div class="cx-created"><strong>Criação: '+esc(info.date)+'</strong><span>'+esc(info.age)+'</span></div>';
  }
  const image = (url,name) => url && /^https:\/\/http2\.mlstatic\.com\//.test(url)
    ? '<img src="'+esc(url)+'" alt="'+esc(name)+'" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
    : '<span class="cx-image-empty">Sem foto</span>';
  const specs = object => '<dl class="cx-specs">'+Object.entries(object).map(([k,v])=>'<div><dt>'+esc(k)+'</dt><dd>'+esc(v ?? 'Não informado')+'</dd></div>').join('')+'</dl>';
  function route() {
    const parts=location.hash.slice(1).split('/');
    if(parts[0] !== 'concorrentes') return;
    const seller=parts[1] || null, product=parts[2] || null;
    if(seller!==state.seller) Object.assign(state,{q:'',category:'',sort:'sales',shown:30});
    state.seller=seller; state.product=product;
  }
  function navigate(seller,product) {
    const path='#concorrentes'+(seller?'/'+seller:'')+(product?'/'+product:'');
    if(location.hash===path){route();render();} else location.hash=path;
  }
  function heading(title,subtitle) {
    return '<div class="cx-summary"><div><h2 tabindex="-1" id="cx-title">'+esc(title)+'</h2><p class="lead">'+esc(subtitle)+'</p></div><div class="cx-meta">Fonte: JoomPulse + páginas do Mercado Livre<br>Dados de '+date(state.data.snapshot)+' · pesquisados em '+date(state.data.collectedAt)+'</div></div>';
  }
  function method() {
    return '<details><summary>Como ler os números e a cobertura</summary>'+Object.values(state.data.method).map(t=>'<p>'+esc(t)+'</p>').join('')+'</details>';
  }
  function renderHome() {
    let html=heading('Concorrentes','Conheça o catálogo e os números dos vendedores encontrados nos produtos do Radar.');
    html+='<div class="cx-note"><strong>2 concorrentes nesta primeira pesquisa</strong><p>Abra um vendedor para explorar os produtos. Cores, tamanhos e kits identificados aparecem separados; anúncios do mesmo produto ficam reunidos na ficha.</p></div><div class="cx-grid">';
    for(const s of state.data.sellers) {
      const p=s.profile,c=s.coverage;
      html+='<article class="cx-card"><div class="cx-card-top">'+badge('MercadoLíder '+(p.newSellerMedal||'').replace('platinum','Platinum'))+'<span class="cx-store-link">'+link(s.url,'Ver loja no Mercado Livre','Ver loja de '+s.name+' no Mercado Livre')+'</span></div><h3>'+esc(s.name)+'</h3><div class="cx-meta">'+esc(p.city)+' · '+esc(p.state?.replace('BR-',''))+' · no ML desde '+date(p.registrationDate)+'</div>';
      html+='<div class="cx-metrics">'+metric(number(p.monthlyAvgSales),'vendas/mês · média estimada')+metric(money(p.monthlyAvgRevenue),'faturamento/mês · média estimada')+metric(number(c.products),'produtos e variações identificados')+metric(number(c.collectedListings),'anúncios pesquisados na fonte')+'</div>';
      html+='<p class="cx-meta">'+number(c.pagesChecked)+' páginas conferidas para características e variações.</p><div class="cx-seed"><strong>Encontrado no Radar por:</strong><br>'+esc(s.seed.name)+'</div>';
      html+='<button class="btn" data-cx-seller="'+esc(s.id)+'">Ver produtos de '+esc(s.name)+'</button></article>';
    }
    html+='</div><div class="cx-note warn"><strong>Cobertura da loja: parcial</strong><p>Foram incluídos os '+number(state.data.sellers.reduce((n,s)=>n+s.coverage.collectedListings,0))+' anúncios ativos que a JoomPulse encontrou. A loja pode ter anúncios adicionais fora dessa base. A contagem de produtos considera as variações identificadas.</p></div>'+method();
    root().innerHTML=html;
  }
  function getSeller() { return state.data.sellers.find(s=>s.id===state.seller); }
  function renderSeller(s) {
    const p=s.profile,c=s.coverage;
    let html='<button class="btn cx-back" data-cx-home>← Todos os concorrentes</button>'+heading(s.name,'Produtos, variações e anúncios deste vendedor no Mercado Livre.');
    html+='<div class="cx-links">'+badge('Reputação '+(p.newSellerReputation==='5_green'?'verde':p.newSellerReputation))+' '+badge('MercadoLíder '+(p.newSellerMedal||''))+' '+link(s.url,'Abrir vendedor no Mercado Livre')+'</div>';
    html+='<div class="cx-metrics">'+metric(number(p.monthlyAvgSales),'vendas/mês · média estimada')+metric(money(p.monthlyAvgRevenue),'faturamento/mês · média estimada')+metric(number(p.sales365Days),'vendas concluídas em 365 dias · fonte ML')+metric(percent(p.monthlySalesGrowth),'variação mensal das vendas · estimada')+'</div>';
    html+='<details><summary>Mais informações do vendedor</summary>'+specs({'No Mercado Livre desde':date(p.registrationDate),'Localização':p.city+' / '+p.state,'Taxa de cancelamento':percent(p.cancelRate),'Anúncios na fonte':number(p.listingsCount),'Anúncios com vendas estimadas':number(p.listingsWithSalesCount),'Anúncios de catálogo':number(p.catalogListingsCount),'Anúncios com Full':number(p.fullShippingCount),'Anúncios com frete grátis':number(p.freeShippingCount)})+'<p>'+link(s.seed.url,'Produto que levou a este concorrente')+'</p></details>';
    html+='<div class="cx-note warn"><strong>'+number(c.collectedListings)+' de '+number(c.sourceListings)+' anúncios ativos da fonte pesquisados</strong><p>'+number(c.products)+' produtos e variações organizados · '+number(c.pagesChecked)+' páginas conferidas. A loja completa pode ter mais anúncios. Quando a variação não pôde ser confirmada, isso aparece na ficha.</p></div>';
    html+='<div class="cx-tools"><label>Buscar produto ou variação<input type="search" id="cx-search" placeholder="Nome, cor, tamanho, kit…" value="'+esc(state.q)+'"></label><label>Categoria<select id="cx-category"><option value="">Todas as categorias</option>'+[...new Set(s.products.map(x=>x.category).filter(Boolean))].sort().map(cat=>'<option '+(state.category===cat?'selected':'')+'>'+esc(cat)+'</option>').join('')+'</select></label><label>Ordenar<select id="cx-sort"><option value="sales">Mais vendas no anúncio principal</option><option value="revenue">Maior faturamento no anúncio</option><option value="price">Menor preço do anúncio</option><option value="name">Nome do produto</option></select></label></div><div id="cx-results"></div>'+method();
    root().innerHTML=html;
    root().querySelector('#cx-sort').value=state.sort;
    for(const [id,key] of [['cx-search','q'],['cx-category','category'],['cx-sort','sort']]) {
      root().querySelector('#'+id).addEventListener(id==='cx-search'?'input':'change',e=>{state[key]=e.target.value;state.shown=30;renderProducts(s);});
    }
    renderProducts(s);
  }
  function renderProducts(s) {
    const listings=new Map(s.listings.map(l=>[l.id,l]));
    const items=s.products.filter(p=>(!state.q||norm(p.name+' '+p.variant+' '+p.brand+' '+p.listings.map(l=>l.id).join(' ')).includes(norm(state.q)))&&(!state.category||p.category===state.category));
    const field=state.sort==='revenue'?'orderGmv1m':state.sort==='price'?'priceAmount':'orderCount1m';
    items.sort((a,b)=>state.sort==='name'?a.name.localeCompare(b.name,'pt-BR'):a.hasListingMetrics!==b.hasListingMetrics?Number(b.hasListingMetrics)-Number(a.hasListingMetrics):state.sort==='price'?
      (listings.get(a.mainListingId)[field]??Infinity)-(listings.get(b.mainListingId)[field]??Infinity):
      (listings.get(b.mainListingId)[field]??-1)-(listings.get(a.mainListingId)[field]??-1));
    let html='<p class="cx-result" role="status">'+number(items.length)+' produtos e variações encontrados · mostrando '+Math.min(state.shown,items.length)+'</p><p class="cx-meta">Criação informada pela JoomPulse · dias calculados até '+date(todayDay())+'. Quando há vários anúncios, mostramos o de maior estimativa mensal de vendas; os demais estão na ficha.</p><div class="cx-products">';
    if(!items.length) html+='<div class="cx-empty">Nenhum produto corresponde a essa busca. Tente outro nome ou categoria.</div>';
    for(const p of items.slice(0,state.shown)) {
      const l=listings.get(p.mainListingId);
      html+='<article class="cx-product">'+image(p.image,p.name)+'<div><h4>'+esc(p.name)+'</h4>'+(p.variant?badge(p.variant):badge('Variação não confirmada','neutral'))+'<small>'+esc(p.category||'Categoria não informada')+' · '+p.listings.length+' anúncio(s)'+(p.listings.length>1?' · data do anúncio principal':'')+'</small>'+creationBlock(l,p.hasListingMetrics)+'</div>';
      html+='<div class="cx-price"><span class="cx-value">'+money(p.hasListingMetrics?l.priceAmount:null)+'</span><small>preço do anúncio</small></div><div class="cx-sales"><span class="cx-value">'+number(p.hasListingMetrics?l.orderCount1m:null)+'</span><small>'+(p.hasListingMetrics?'vendas/mês estimadas<br>do anúncio principal':'opção sem anúncio correspondente na fonte')+'</small></div><button class="btn" data-cx-product="'+esc(p.id)+'">Ver ficha</button></article>';
    }
    html+='</div>';
    if(state.shown<items.length) html+='<button class="btn cx-more" data-cx-more>Mostrar mais 30 produtos</button>';
    root().querySelector('#cx-results').innerHTML=html;
  }
  function renderProduct(s,p) {
    const lookup=new Map(s.listings.map(l=>[l.id,l]));
    const main=lookup.get(p.mainListingId);
    let html='<button class="btn cx-back" data-cx-seller="'+esc(s.id)+'">← Produtos de '+esc(s.name)+'</button>';
    html+='<div class="cx-detail-head">'+image(p.image,p.name)+'<div><p class="cx-meta">'+esc(s.name)+' · '+esc(p.category||'')+'</p><h3 tabindex="-1" id="cx-title">'+esc(p.name)+'</h3>'+(p.variant?badge(p.variant):badge('Variação não confirmada','warn'))+'<p class="cx-meta">Pesquisa de '+date(state.data.collectedAt)+' · dados de '+date(state.data.snapshot)+'</p></div></div>';
    const mainCreation=creationInfo(main,p.hasListingMetrics);
    if(p.hasListingMetrics) html+='<h3>Números do anúncio principal</h3><div class="cx-metrics">'+metric(money(main.priceAmount),'preço do anúncio na fonte')+metric(number(main.orderCount1m),'vendas/mês estimadas · anúncio')+metric(money(main.orderGmv1m),'faturamento/mês estimado · anúncio')+metric(mainCreation.date,'criação do anúncio · '+mainCreation.age)+'</div>';
    html+='<div class="cx-note warn"><strong>Vendas por variação: não informadas pela fonte</strong><p>Os números abaixo pertencem aos anúncios. Um mesmo anúncio pode atender várias cores e tamanhos; não some esses valores entre variações.</p></div>';
    html+='<h3>Produto e características</h3>'+(Object.keys(p.attributes).length?specs(p.attributes):'<p class="cx-meta">A fonte identificou o produto, mas as características e variações desta página ainda não foram confirmadas.</p>');
    html+='<p class="cx-meta">'+esc(p.identity)+'. '+p.listings.length+' anúncio(s) vinculado(s) a esta ficha.</p><h3>'+(p.hasListingMetrics?'Anúncio principal':'Opções relacionadas')+'</h3><p class="cx-meta">Maior estimativa mensal de vendas entre os anúncios vinculados. Os números não foram somados. Criação informada pela JoomPulse; dias decorridos calculados até '+date(todayDay())+'.</p>';
    let otherHeading=false;
    for(const ref of p.listings) {
      const l=lookup.get(ref.id), primary=l.id===p.mainListingId;
      if(ref.referenceOnly) {
        html+='<article class="cx-listing">'+badge('Opção encontrada · números não disponíveis','warn')+'<p>Esta opção aparece no seletor do Mercado Livre, mas seu anúncio específico não foi identificado na base pesquisada. Preço, vendas e faturamento desta opção não estão confirmados.</p>'+link(ref.url,'Conferir esta opção no Mercado Livre')+'</article>';
        continue;
      }
      if(!primary&&!otherHeading) {
        html+='<h3>Demais anúncios vinculados ('+p.listings.filter(r=>!r.referenceOnly&&r.id!==p.mainListingId).length+')</h3>';
        otherHeading=true;
      }
      html+='<article class="cx-listing">'+badge(primary?'Principal · maior estimativa de vendas':'Outro anúncio deste produto',primary?'':'neutral')+'<h4>'+esc(l.productName)+'</h4><p class="cx-meta">'+esc(l.id)+' · '+(l.catalogProduct?'Anúncio de catálogo':'Anúncio próprio')+' · '+(l.listingType==='gold_pro'?'Premium':l.listingType==='gold_special'?'Clássico':esc(l.listingType))+'</p>';
      html+=creationBlock(l);
      if(l.pageStatus==='redirected') html+='<div class="cx-note warn"><strong>O anúncio não abriu na conferência.</strong><p>O Mercado Livre redirecionou para uma categoria. Os números preservam a leitura da fonte de '+date(state.data.snapshot)+', mas a disponibilidade atual não foi confirmada.</p></div>';
      if(ref.shared) html+='<p class="cx-meta"><strong>Este anúncio reúne variações; preço e vendas não são exclusivos desta opção.</strong></p>';
      if(!primary) html+='<div class="cx-metrics">'+metric(money(l.priceAmount),'preço do anúncio na fonte')+metric(number(l.orderCount1m),'vendas/mês estimadas · anúncio')+metric(money(l.orderGmv1m),'faturamento/mês estimado · anúncio')+metric(number(l.orderCount1w),'vendas/semana estimadas · anúncio')+'</div>';
      if(primary) html+='<p><strong>'+number(l.orderCount1w)+'</strong> vendas/semana estimadas neste anúncio.</p>';
      html+=specs({'Tempo ativo informado pela fonte':l.daysInAd==null?'Não informado':number(l.daysInAd)+' dias'+(l.catalogProduct?' · referência de catálogo':'')+' · pode diferir dos dias desde a criação','Primeira venda':'Não informada','Avaliação do produto':l.reviewsRating==null?'Não informada':String(l.reviewsRating).replace('.',',')+' / 5 · '+number(l.reviewsCount)+' avaliações'+(l.catalogProduct?' do catálogo':''),'Full':yes(l.isFull),'Frete grátis':yes(l.isFreeShipping),'Vendedores no catálogo':number(l.numBuyBoxSellers),'Página conferida':l.pageChecked?'Sim · características coletadas':'Características ainda não confirmadas'});
      html+='<div class="cx-links">'+link(ref.url,'Ver produto no Mercado Livre')+link(l.url,'Abrir anúncio '+l.id)+'</div></article>';
    }
    html+='<div class="cx-note"><strong>Custos e lucro deste concorrente</strong><p>O custo de compra, os impostos e a margem do vendedor não são públicos. Não foram estimados como se fossem dados confirmados.</p></div>'+method();
    root().innerHTML=html;
  }
  function render() {
    if(!root()||!state.data) return;
    if(!state.seller) renderHome();
    else {
      const s=getSeller();
      if(!s) {root().innerHTML='<div class="cx-empty">Concorrente não encontrado. <button class="btn" data-cx-home>Ver concorrentes</button></div>';return;}
      const p=state.product?s.products.find(p=>p.id===state.product):null;
      if(state.product&&!p) {root().innerHTML='<div class="cx-empty">Produto não encontrado. <button class="btn" data-cx-seller="'+esc(s.id)+'">Voltar ao catálogo</button></div>';return;}
      if(p) renderProduct(s,p); else renderSeller(s);
    }
  }
  async function load() {
    if(!root()) return;
    route();
    if(state.data) {render();return;}
    if(state.request) return state.request;
    root().innerHTML='<p role="status">Carregando pesquisa dos concorrentes…</p>';
    state.request=(async()=>{
      try {
        const response=await fetch('concorrentes.json?v=20260908',{cache:'no-cache',signal:AbortSignal.timeout(20000)});
        if(!response.ok) throw new Error('HTTP '+response.status);
        const data=await response.json();
        if(data.schemaVersion!==1||!Array.isArray(data.sellers)) throw new Error('Dados inválidos');
        state.data=data; route(); render();
      } catch(error) {
        root().innerHTML='<div class="cx-error" role="alert"><strong>Não foi possível carregar os concorrentes.</strong><p>Confira a conexão e tente novamente.</p><button class="btn" data-cx-retry>Tentar novamente</button></div>';
      } finally {state.request=null;}
    })();
    return state.request;
  }
  document.addEventListener('click',event=>{
    const el=event.target.closest('[data-cx-home],[data-cx-seller],[data-cx-product],[data-cx-more],[data-cx-retry]');
    if(!el||!root()?.contains(el)) return;
    if(el.hasAttribute('data-cx-home')) navigate();
    else if(el.hasAttribute('data-cx-seller')) navigate(el.dataset.cxSeller);
    else if(el.hasAttribute('data-cx-product')) navigate(state.seller,el.dataset.cxProduct);
    else if(el.hasAttribute('data-cx-more')) {state.shown+=30;renderProducts(getSeller());}
    else load();
  });
  function applyHash() {
    if(!location.hash.startsWith('#concorrentes')) return;
    route();
    document.querySelector('button[data-tab="conc"]')?.click();
    if(state.data) render();
    window.scrollTo({top:0});
    root()?.querySelector('#cx-title')?.focus({preventScroll:true});
  }
  window.addEventListener('hashchange',applyHash);
  window.addEventListener('load',applyHash);
  window.RadarConcorrentes={load};
})();
