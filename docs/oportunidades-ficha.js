/* Ficha compartilhada: apresentação dos dados existentes, sem novas consultas. */
(function(){
  'use strict';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number=v=>typeof v==='number'&&Number.isFinite(v)?v:null;
  const num=v=>number(v)==null?'não coletado':v.toLocaleString('pt-BR',{maximumFractionDigits:2});
  const money=v=>number(v)==null?'não coletado':v.toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
  const percent=v=>number(v)==null?'não coletada':num(v*100)+'%';
  const date=v=>v&&/^\d{4}-\d{2}-\d{2}/.test(v)?v.slice(0,10).split('-').reverse().join('/'):'não coletada';
  const verdict={igual:'Mesmo produto',parecido:'Referência aproximada',diferente:'Produto diferente'};
  const metric=(label,value)=>`<div><span>${label}</span><b>${value}</b></div>`;

  function categoryChoices(p){
    const choices=new Map();
    const add=(path,source)=>{
      const clean=(path||[]).filter(Boolean),l1=clean[0];
      if(!l1||!FEES.comm[l1])return;
      const current=choices.get(l1)||{l1,path:[l1],sources:new Set(),evidence:0};
      if(clean.length>current.path.length)current.path=clean;
      current.sources.add(source);current.evidence+=1;choices.set(l1,current);
    };
    const stored=p.categoria?.caminho?.length?p.categoria.caminho:[p.categoria?.l1,p.categoria?.l2,p.categoria?.l3];
    add(stored,'categoria associada pelo Radar');
    for(const a of p.anuncios||[]){
      if(!['igual','parecido'].includes(a.veredito))continue;
      add([a.l1,a.l2,a.l3],a.veredito==='igual'?'anúncio conferido do mesmo produto':'referência aproximada conferida');
    }
    return [...choices.values()].sort((a,b)=>b.evidence-a.evidence||a.l1.localeCompare(b.l1,'pt-BR')).map(c=>({...c,sources:[...c.sources],fees:FEES.comm[c.l1]}));
  }

  function marketTools(p){
    const categories=categoryChoices(p),query=String(p.nome||'').trim().replace(/\s+/g,'-');
    const search='https://lista.mercadolivre.com.br/'+encodeURIComponent(query);
    const cards=categories.map((c,i)=>`<article class="ot-category-card"><div class="ot-category-index">${i+1}</div><div class="ot-category-copy"><h4>${esc(c.path.join(' › '))}</h4><p>${esc(c.sources.join(' · '))} · ${num(c.evidence)} evidência(s)</p></div><div class="ot-category-fee"><span>Clássico</span><b>${num(c.fees[0])}%</b><small>do preço da venda</small></div><div class="ot-category-fee premium"><span>Premium</span><b>${num(c.fees[1])}%</b><small>do preço da venda</small></div></article>`).join('');
    return `<section class="ot-market-search"><div><span class="ot-kicker">PESQUISA DIRETA</span><h3>Veja todo o mercado deste produto</h3><p>A busca abrirá com “${esc(p.nome)}”. Use os resultados para encontrar outros vendedores, preços e formas de apresentar o produto.</p></div><a class="btn primary" href="${esc(search)}" target="_blank" rel="noopener">Pesquisar no Mercado Livre ↗</a></section>
      <details class="ot-category-panel"><summary><div><span class="ot-kicker">CATEGORIAS POSSÍVEIS</span><b>${categories.length?num(categories.length)+' opção'+(categories.length>1?'ões':'')+' encontrada'+(categories.length>1?'s':''):'Categoria não coletada'}</b><small>${categories.length?'Clique para ver caminhos e comissões':'Falta categoria nos dados do Radar e dos anúncios recentes'}</small></div><span class="ot-category-open">Ver taxas</span></summary>${categories.length?`<div class="ot-category-list">${cards}</div><p class="ot-category-note">Estas são categorias observadas nos dados, não uma autorização automática para anunciar. A comissão muda por categoria; custo fixo, imposto, frete e embalagem continuam na conta do Simulador.</p>`:''}</details>`;
  }

  function competitor(a,p,env){
    const extra=env.dates[a.id],created=a.criadoEm||extra?.created;
    const days=RadarOportunidades.age(created,env.now),q=number(a.qtd),cost=number(p.unit),price=number(a.preco),cat=env.cat(a,p);
    const comparable=['igual','parecido'].includes(a.veredito);
    const canCalc=comparable&&q!=null&&q>0&&cost!=null&&price!=null&&cat&&typeof a.frete_gratis==='boolean';
    const classic=canCalc?extrato(price,'c',cat,cost*q,a.frete_gratis):null;
    const premium=canCalc?extrato(price,'p',cat,cost*q,a.frete_gratis):null;
    return `<article class="ot-rival ${esc(a.veredito||'pendente')}" data-rival="${esc(a.id)}">
      <div class="ot-rival-main"><button class="ot-photo" data-compare="${esc(a.id)}" aria-label="Comparar fotos: ${esc(a.nome)}"><img src="${esc(a.img||'')}" alt="Foto do concorrente" loading="lazy"></button>
        <div><h4>${esc(a.nome)}</h4><p>${esc(a.vendedor||'Vendedor não coletado')} · ${a.catalogo===true?'Catálogo · '+num(a.bb)+' vendedores':a.catalogo===false?'Anúncio próprio':'Tipo não coletado'} · ${esc(verdict[a.veredito]||'Sem conferência')}</p>
        <div class="tags"><span class="tag">Criado em ${date(created)} · ${num(days)} dias</span><span class="tag">Atividade: ${num(a.dias)} dias</span><span class="tag">Nota ${num(a.nota)}/5 · ${num(a.avaliacoes)} avaliações</span></div>
        <p class="ot-rival-observation">${esc(a.pendencia||a.obs||'Compare as fotos para conferir modelo, tamanho e conteúdo do kit.')}</p></div></div>
      <div class="ot-rival-values">${metric('Preço do anúncio',money(price))}${metric('Vendas estimadas/mês',num(a.vendas_mes))}${metric('Vendas estimadas/semana',num(a.vendas_sem))}${metric('Sobra Clássico',money(classic?.profit)+' · '+percent(classic?.margin))}${metric('Sobra Premium',money(premium?.profit)+' · '+percent(premium?.margin))}</div>
      <div class="ot-rival-bottom"><small>Vendas desde: ${date(a.primeiraVendaEm)} · ${num(q)} unidade(s) por anúncio. Fonte: JoomPulse · leitura ${date(a.lidoEm||extra?.read)}${!comparable?' · sem margem comparável para outro produto':''}.<br>Atividade não comprova dias com vendas. Início das vendas só aparece quando coletado.</small><div><button class="btn" data-compare="${esc(a.id)}">Comparar fotos</button><a class="btn ghost" href="https://produto.mercadolivre.com.br/${esc(String(a.id).replace('MLB','MLB-'))}" target="_blank" rel="noopener">Mercado Livre ↗</a></div></div>
      ${(a.outros||[]).length?`<details><summary>Outros vendedores registrados neste catálogo (${a.outros.length})</summary><ul>${a.outros.map(o=>`<li>${esc(o.vendedor||'não coletado')} · ${money(o.preco)} · vendas/mês: ${num(o.vendas_mes)}</li>`).join('')}</ul></details>`:''}
    </article>`;
  }

  function compare(p,a){
    document.getElementById('ot-compare')?.remove();
    const dialog=document.createElement('dialog');dialog.id='ot-compare';dialog.className='ot-comparison';
    dialog.innerHTML=`<header><h3>Conferir produto e concorrente</h3><button class="btn" data-close>Fechar</button></header><p>${esc(verdict[a.veredito]||'Sem conferência')} · ${esc(a.obs||'Confira modelo, material, tamanho e quantidade.')}</p><div class="ot-evidence"><figure><img src="${esc(p.img||'')}" alt="Produto do fornecedor"><figcaption>${esc(p.nome)} · ${money(p.unit)}</figcaption><button class="btn" data-photo="supplier">Ampliar fornecedor</button></figure><figure><img src="${esc(a.img||'')}" alt="Produto do concorrente"><figcaption>${esc(a.nome)} · ${money(a.preco)}</figcaption><button class="btn" data-photo="competitor">Ampliar concorrente</button></figure></div><p class="small muted">Verifique também conteúdo da embalagem e medidas. Semelhança visual não confirma especificações que não foram coletadas.</p>`;
    document.body.append(dialog);dialog.querySelector('[data-close]').onclick=()=>dialog.close();
    dialog.querySelectorAll('[data-photo]').forEach(b=>b.onclick=()=>{dialog.close();abrirLupa(b.dataset.photo==='supplier'?p:{nome:a.nome,img:a.img,fotos:[a.img]},0);});
    dialog.showModal();
  }

  function decorate(root,p){
    root.classList.add('ot-product-sheet');
    const env=RadarOportunidades.context(),f=forn.data.fornecedores.find(x=>x.id===p.fornecedor);
    const r=RadarOportunidades.analyze(p,f,env);
    const back=document.createElement('button');back.className='btn ghost ot-back';back.textContent='← Oportunidade de fornecedores';back.onclick=()=>root.closest('#tab-oport')?RadarOportunidades.closeSheet():showTab('oport');root.prepend(back);
    const summary=root.querySelector(':scope > .veredito');
    if(summary)summary.outerHTML=`<section class="ot-sheet-summary"><h3>${esc(r?.status||'Precisa de mais análise')}</h3><p>${esc(r?.reading||'Sem referência elegível para a Etapa 1. Confira os anúncios abaixo.')}</p>${r?`<div class="ot-rival-values">${metric('Referência usada',money(r.price))}${metric('Custo do produto no anúncio',money(r.cost))}${metric('Sobra Clássico',money(r.classic?.profit)+' · '+percent(r.classic?.margin))}${metric('Sobra Premium',money(r.premium?.profit)+' · '+percent(r.premium?.margin))}${metric('Pode pagar até para 20%',money(r.maxCost))}</div><p>${esc(r.stock)} · ${r.unit?'Compra após a venda':num(r.box)+' unidades por caixa = '+money(r.capital)}.</p><details><summary>Por que testar, conta e pendências</summary><p>${esc(r.reason)}</p><p>${esc(r.math)}</p><ul>${r.pending.map(t=>'<li>'+esc(t)+'</li>').join('')}</ul><small>Fornecedor: ${date(r.supplierDate)} · Mercado: ${date(r.exported)}. As margens usam as premissas atuais do Simulador.</small></details>`:''}</section>`;
    // Mantém a ficha existente e sua calculadora. O fornecedor não abre site externo.
    const supplierLink=root.querySelector('.fhead a[target="_blank"]');
    if(supplierLink)supplierLink.replaceWith(document.createTextNode(r?.stock||'Catálogo do fornecedor'));
    const calculator=root.querySelector('#f-calc');
    if(calculator)calculator.insertAdjacentHTML('afterend',marketTools(p));
    const all=[...(p.anuncios||[]),...(p.mesma_categoria||[])];
    root.querySelectorAll('.an[data-id]').forEach(el=>{const a=all.find(x=>x.id===el.dataset.id);if(a)el.outerHTML=competitor(a,p,env);});
    root.querySelectorAll('[data-compare]').forEach(b=>b.onclick=()=>compare(p,all.find(a=>a.id===b.dataset.compare)));
    if(number(p.unit)==null){for(const id of ['f-alvos','f-calc']){const el=root.querySelector('#'+id);if(el)el.textContent='Custo do fornecedor não coletado. A conta fica pendente.';}}
  }
  window.RadarFichaOportunidades={decorate,categoryChoices};
})();
