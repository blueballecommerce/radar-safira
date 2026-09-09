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
    const all=[...(p.anuncios||[]),...(p.mesma_categoria||[])];
    root.querySelectorAll('.an[data-id]').forEach(el=>{const a=all.find(x=>x.id===el.dataset.id);if(a)el.outerHTML=competitor(a,p,env);});
    root.querySelectorAll('[data-compare]').forEach(b=>b.onclick=()=>compare(p,all.find(a=>a.id===b.dataset.compare)));
    if(number(p.unit)==null){for(const id of ['f-alvos','f-calc']){const el=root.querySelector('#'+id);if(el)el.textContent='Custo do fornecedor não coletado. A conta fica pendente.';}}
  }
  window.RadarFichaOportunidades={decorate};
})();
