/* Etapa 1: somente JSONs e as contas compartilhadas do Radar. Sem IA ou coleta. */
(function(global){
  'use strict';
  const OPT_MARGEM_MIN = .20;
  const OPT_DEMANDA_DIA_MIN = 1;
  const OPT_IDADE_MAX = 45;
  const OPT_REPETICAO_MIN = 2;
  const OPT_CRESCIMENTO_MIN = .20;
  const OPT_CAPITAL_ALERTA = null; // João: avaliar caso a caso, sem teto fixo.
  const OPT_APROXIMADOS = true;
  const OPT_PLANO = 'Após a primeira venda, observar se surgem outras; avaliar a compra pelo investimento e pelo prazo dos pedidos. Mais vendas reforçam o sinal, mas não autorizam automaticamente comprar a caixa.';
  const CONFIG = {margem:OPT_MARGEM_MIN, diaria:OPT_DEMANDA_DIA_MIN, idade:OPT_IDADE_MAX, repeticao:OPT_REPETICAO_MIN, crescimento:OPT_CRESCIMENTO_MIN, capital:OPT_CAPITAL_ALERTA, aproximados:OPT_APROXIMADOS};
  const PENDENTES = {
    'MLB5179068847':'Abridor KGQ03: cabeça e cabos diferentes; conferir na lupa.',
    'MLB4812803339':'Bomba: painel e corpo diferentes; conferir na lupa.',
    'MLB6625098390':'Modelador: comandos e base diferentes; conferir na lupa.',
    'MLB7481296738':'Squishy: marca e apresentação diferentes; conferir na lupa.',
    'MLB7314817188':'Revisão de 09/09: suporte UV com corpo, comandos e encaixes diferentes do fornecedor. Esta referência não valida o mesmo modelo.',
    'MLB4993558973':'Revisão de 09/09: power bank com corpo e disposição dos conectores diferentes. Capacidade e equivalência não comprovadas.',
    'MLB7418334426':'Revisão de 09/09: referência vende taça personalizada. Serviço de gravação e seu custo não estão no produto do fornecedor.',
  };
  const n = x => typeof x==='number' && Number.isFinite(x) ? x : null;
  const money=x=>n(x)==null?'não coletado':x.toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
  const num=x=>n(x)==null?'não coletado':x.toLocaleString('pt-BR',{maximumFractionDigits:2});
  const pct=x=>n(x)==null?'não coletado':num(x*100)+'%';
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function day(s){
    const v=String(s||'').slice(0,10);
    if(!/^\d{4}-\d{2}-\d{2}$/.test(v)) return null;
    const t=Date.parse(v+'T00:00:00Z');
    return Number.isFinite(t)&&new Date(t).toISOString().slice(0,10)===v?t:null;
  }
  const dateText=s=>day(s)==null?'não coletada':String(s).slice(0,10).split('-').reverse().join('/');
  const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const age=(created,at)=>day(created)==null||day(at)==null||day(at)<day(created)?null:Math.floor((day(at)-day(created))/864e5);
  function unitAllowed(f){return !!f && typeof f.regra==='string' && /unidade|quantidade menor/i.test(f.regra) && !/apenas caixa fechada/i.test(f.regra);}

  // As janelas não são somadas. Uma janela parcial só prova um LIMITE INFERIOR
  // da média desde a criação; se não atingir a meta, faltam dados para rejeitar.
  function demand(a, supplement, exported, now){
    const created=a.criadoEm||a.adPublishDate||supplement?.created;
    const currentAge=age(created,now);
    const read=a.lidoEm||supplement?.read||null;
    const sinceAge=age(created,read||exported);
    let sales=n(a.vendas_desde_criacao), windowDays=null, source='JoomPulse · vendas desde a criação';
    let bound=false;
    if(sales==null){
      if(n(supplement?.monthly)!=null){sales=supplement.monthly;windowDays=30;source=supplement.source+' · estimativa de 30 dias';}
      else if(n(a.vendas_mes)!=null){sales=a.vendas_mes;windowDays=30;source='JoomPulse / fornecedores.json · estimativa de 30 dias';}
      else if(n(a.vendas_sem)!=null){sales=a.vendas_sem;windowDays=7;source='JoomPulse / fornecedores.json · estimativa de 7 dias';}
      // Exportador normaliza o período: vendas_mes é mensal, não soma de anúncios.
      bound=sinceAge!=null && windowDays!=null && sinceAge>windowDays;
    }
    const daily=sales!=null && sinceAge!=null && sinceAge>0 ? sales/sinceAge : null;
    return {created, age:currentAge, ageAtReading:sinceAge, daily, lowerBound:bound, sales, windowDays, source, read,
      passes:daily!=null&&daily>=CONFIG.diaria,
      fails:daily!=null&&!bound&&daily<CONFIG.diaria};
  }

  // Compara o ritmo semanal com a média mensal do MESMO anúncio. Não soma
  // vendas de anúncios diferentes e não chama aceleração de histórico.
  function growth(a){
    const week=n(a.vendas_sem),month=n(a.vendas_mes);
    return week==null||month==null||month<=0?null:(week*4.33/month)-1;
  }

  function marketEvidence(p,candidates){
    const coverage=p._coverage||null;
    const recentReviewed=candidates.filter(r=>r.demand.age!=null&&r.demand.age<CONFIG.idade&&r.ref.revisadoEm&&!r.reviewPending&&!r.reviewRequired&&(!r.listingStatus||r.listingStatus==='active'));
    const key=r=>'vendedor:'+(r.ref.vendedor||r.ref.merchantName||r.ref.id).toLocaleLowerCase('pt-BR');
    const unique=list=>[...new Map(list.map(r=>[key(r),r])).values()];
    const strong=unique(recentReviewed.filter(r=>r.demand.passes));
    const growing=unique(strong.filter(r=>n(r.growth)!=null&&r.growth>=CONFIG.crescimento));
    const weak=unique(recentReviewed.filter(r=>r.demand.fails));
    const leader=[...recentReviewed].sort((a,b)=>(b.monthly??-1)-(a.monthly??-1))[0]||candidates[0]||null;
    const advantages=[];
    if(leader?.catalog)advantages.push('catálogo/Compra Ganha');
    if(leader?.ref.full===true&&recentReviewed.some(r=>r.ref.full===false))advantages.push('Full');
    const peerPrices=recentReviewed.map(r=>r.price).filter(v=>n(v)!=null);
    if(leader&&peerPrices.length>1&&leader.price<=Math.min(...peerPrices)*1.02)advantages.push('menor preço entre os comparáveis revisados');
    const peerReviews=recentReviewed.map(r=>r.rc).filter(v=>n(v)!=null&&v>0).sort((a,b)=>a-b);
    const median=peerReviews.length?peerReviews[Math.floor(peerReviews.length/2)]:null;
    if(leader&&median!=null&&leader.rc>=Math.max(100,median*3))advantages.push('muito mais avaliações');
    const repeatable=strong.length>=CONFIG.repeticao;
    const growthConfirmed=growing.length>=CONFIG.repeticao;
    const complete=coverage?.paginacaoCompleta===true;
    let diagnosis;
    if(!strong.length)diagnosis='Nenhum anúncio recente revisado sustenta uma venda por dia.';
    else if(!repeatable)diagnosis='Só '+strong.length+' vendedor recente revisado sustenta uma venda por dia'+(weak.length?' enquanto '+weak.length+' comparável revisado fica abaixo disso':'')+'. Resultado isolado não valida o mercado.';
    else diagnosis=strong.length+' vendedores recentes revisados sustentam uma venda por dia.';
    if(advantages.length)diagnosis+=' O líder tem vantagem observável de '+advantages.join(', ')+'.';
    else if(leader)diagnosis+=' Não foi encontrada uma vantagem objetiva que explique sozinho o líder.';
    return {coverage,complete,reviewed:recentReviewed.length,strong:strong.length,growing:growing.length,weak:weak.length,repeatable,growthConfirmed,
      growthThreshold:CONFIG.crescimento,diagnosis,advantages,leader:leader?.ref.id||null,
      coverageText:coverage?(complete?'Busca concluída para os termos.':'Busca parcial: '+num(coverage.revisados)+' de '+num(coverage.candidatos)+' candidatos foram comparados visualmente.'):'Cobertura da busca não coletada.'};
  }

  function classify(r){
    const why=[];
    if(r.listingStatus && r.listingStatus!=='active') why.push('Anúncio de referência não está ativo na leitura pontual.');
    if(r.catalog && r.entrance==='fechada') why.push('Catálogo fechado: '+num(r.bb)+' vendedores disputam a Compra Ganha.');
    if(n(r.maxFloor)!=null&&r.catalog&&n(r.cost)!=null&&r.maxFloor<r.cost) why.push('No piso do catálogo, o custo supera o máximo para margem de 20%.');
    if(n(r.classic?.profit)!=null&&r.classic.profit<=0) why.push('A sobra no preço de referência é zero ou negativa.');
    if(r.demand.age!=null&&r.demand.age>=CONFIG.idade) why.push('Criado há '+num(r.demand.age)+' dias: excede o limite de '+CONFIG.idade+' dias.');
    if(r.demand.fails) why.push('A média desde a criação é menor que uma venda por dia.');
    if(why.length) return {status:'Não vale o teste',reason:why.join(' ')};
    const missing=[];
    if(r.demand.age==null) missing.push('Data de criação não coletada; dias no ar não substituem criação.');
    if(!r.demand.passes) missing.push('Ainda falta comprovar média de uma venda por dia desde a criação.');
    if(!r.classic) missing.push('Falta preço, custo, quantidade do kit, categoria ou frete do anúncio.');
    else if(r.classic.margin<CONFIG.margem) missing.push('Margem no Clássico abaixo de 20%.');
    if(r.catalog && (r.entrance!=='aberta'||r.maxFloor==null||r.maxFloor<=r.cost)) missing.push('Falta margem para ficar abaixo do piso em catálogo aberto.');
    if(r.entrance==='não coletada') missing.push('Concorrência não coletada.');
    if(r.entrance==='fechada') missing.push('Anúncio próprio com líder de entrada fechada.');
    if(r.reviewPending) missing.push(r.reviewPending);
    if(r.reviewRequired) missing.push('Falta reconferir visualmente modelo e kit antes de aprovar esta referência.');
    if(r.quantityPending) missing.push('Quantidade do kit de munição ainda precisa de confirmação.');
    if(r.missingReading) missing.push('O anúncio não retornou na consulta pontual; revalidar disponibilidade.');
    if(r.market){
      if(!r.market.complete) missing.push(r.market.coverageText+' A pesquisa precisa ser concluída antes da aprovação.');
      if(!r.market.repeatable) missing.push('Demanda ainda não repetida: são necessários pelo menos '+CONFIG.repeticao+' vendedores recentes e revisados com uma venda por dia.');
      if(!r.market.growthConfirmed) missing.push('Crescimento forte ainda não confirmado em '+CONFIG.repeticao+' anúncios: o ritmo semanal precisa superar a média mensal em pelo menos '+pct(CONFIG.crescimento)+'.');
    }
    if(missing.length) return {status:'Precisa de mais análise',reason:missing.join(' ')};
    return {status:'Promissor',reason:'Mercado repetido em pelo menos '+CONFIG.repeticao+' vendedores comparáveis, crescimento semanal forte, pesquisa concluída, menos de 45 dias desde a criação, uma venda por dia e margem de pelo menos 20% no Clássico.'+(r.approximate?' Referência aproximada.':'')+(!r.unit?' Condição: definir como atender a primeira venda sem comprar a caixa antecipadamente.':'')};
  }

  function analyze(p,f,env,referenceId){
    if(!p.pesquisado)return null;
    let ads=(p.anuncios||[]).filter(a=>a.veredito==='igual'||(CONFIG.aproximados&&a.veredito==='parecido'));
    if(!ads.length)return null;
    const monthly=a=>n(a.vendas_mes)??(n(a.vendas_sem)==null?null:Math.round(a.vendas_sem*4.33));
    ads=[...ads].sort((a,b)=>(monthly(b)??-1)-(monthly(a)??-1)||String(a.id).localeCompare(String(b.id)));
    // O líder mede o mercado. A entrada é avaliada em CADA anúncio, com sua
    // própria idade, demanda, preço e conta; um líder antigo não elimina os novos.
    if(!referenceId){
      const candidates=ads.map(a=>analyze(p,f,env,a.id));
      const order={'Promissor':0,'Precisa de mais análise':1,'Não vale o teste':2};
      const evidence=r=>(r.ref.revisadoEm?4:0)+(r.demand.age!=null&&r.demand.age<CONFIG.idade?2:0)+(r.demand.passes?1:0);
      candidates.sort((a,b)=>Number(isRecent(b.ref,env))-Number(isRecent(a.ref,env))||order[a.status]-order[b.status]||(a.status==='Promissor'?0:evidence(b)-evidence(a))||(b.monthly??-1)-(a.monthly??-1)||a.ref.id.localeCompare(b.ref.id));
      const chosen=candidates[0];
      chosen.evaluated=candidates.map(r=>({id:r.ref.id,status:r.status,reason:r.reason,age:r.demand.age,monthly:r.monthly,price:r.price,margin:r.classic?.margin}));
      chosen.leader=ads[0];
      chosen.coverage=p._coverage||null;
      chosen.market=marketEvidence(p,candidates);
      chosen.stability=chosen.market.repeatable?'Demanda repetida em '+num(chosen.market.strong)+' vendedores recentes revisados.':'Não demonstrada: '+chosen.market.diagnosis;
      Object.assign(chosen,classify(chosen));
      chosen.reading=(chosen.catalog?'Catálogo':'Anúncio próprio')+' com entrada '+chosen.entrance+'. Referência a '+money(chosen.price)+', '+num(chosen.monthly)+' vendas mensais estimadas; sobra '+money(chosen.classic?.profit)+' ('+pct(chosen.classic?.margin)+') no Clássico. '+chosen.market.diagnosis+' '+chosen.reason;
      chosen.researchOnly=candidates.every(r=>r.demand.age==null||r.demand.age>=CONFIG.idade);
      if(chosen.status==='Não vale o teste' && candidates.every(r=>r.demand.age==null||r.demand.age>=CONFIG.idade)){
        chosen.status='Precisa de mais análise';
        chosen.reason='As referências conferidas são antigas ou não têm criação coletada. Falta confirmar um anúncio recente; isso não reprova o produto inteiro.';
        chosen.reading='Mercado com referência de '+num(monthly(ads[0]))+' vendas/mês a '+money(ads[0].preco)+'. '+chosen.reason;
        chosen.researchOnly=true;
      }
      return chosen;
    }
    const a=ads.find(x=>x.id===referenceId),approximate=a.veredito==='parecido',q=n(a.qtd),cost=n(p.unit),cat=env.cat(a,p);
    const quantity=q!=null&&Number.isInteger(q)&&q>=1?q:null;
    const totalCost=quantity!=null&&cost!=null?cost*quantity:null;
    const price=n(a.preco);
    const fs=typeof a.frete_gratis==='boolean'?a.frete_gratis:null;
    const comparable=ads.filter(x=>n(x.qtd)===quantity&&x.veredito===a.veredito&&(!isRecent(a,env)||isRecent(x,env)));
    const prices=comparable.map(x=>n(x.preco)).filter(x=>x!=null);
    const low=prices.length?Math.min(...prices):null, high=prices.length?Math.max(...prices):null;
    const floor=a.catalogo?n(a.preco_min):low;
    const canCalc=price!=null&&totalCost!=null&&cat!=null&&fs!=null;
    const classic=canCalc?env.extrato(price,'c',cat,totalCost,fs):null;
    const premium=canCalc?env.extrato(price,'p',cat,totalCost,fs):null;
    const floorResult=canCalc&&floor!=null?env.extrato(floor,'c',cat,totalCost,fs):null;
    const maxCost=canCalc?env.max(.20,price,'c',cat,fs):null;
    const maxFloor=canCalc&&floor!=null?env.max(.20,floor,'c',cat,fs):null;
    const bb=n(a.bb),rc=n(a.avaliacoes),catalog=typeof a.catalogo==='boolean'?a.catalogo:null;
    const entrance=catalog===true?(bb==null?'não coletada':bb>=env.catalogLimits[1]?'fechada':bb>=env.catalogLimits[0]?'disputada':'aberta'):
      catalog===false?(rc==null?'não coletada':rc>=env.ownLimits[1]?'fechada':rc>=env.ownLimits[0]?'disputada':'aberta'):'não coletada';
    const r={url:p.url,name:p.nome,img:p.img,supplier:f?.nome||p.fornecedor,supplierId:p.fornecedor,unit:unitAllowed(f),approximate,ref:a,ads,
      cost:totalCost,unitCost:cost,quantity,price,low,high,floor,classic,premium,floorResult,maxCost,maxFloor,catalog,bb,rc,entrance,
      monthly:monthly(a),weekly:n(a.vendas_sem),activityDays:n(a.dias),exported:a.lidoEm||a.exportadoEm||env.exported,
      supplierDate:p._siteLidoEm||env.exported,
      demand:demand(a,env.dates?.[a.id],a.exportadoEm||env.exported,env.now),
      growth:growth(a),
      listingStatus:env.dates?.[a.id]?.listingStatus,missingReading:env.missing?.includes(a.id)||false,
      radar:env.rows.find(x=>x._forn?.url===p.url)?.opp||null,
      box:n(p.caixa),siteBox:n(p.caixa_site),capital:n(p.caixa)!=null&&cost!=null?p.caixa*cost:null,
      quantityPending:/munição.*bolinhas.*gel/i.test(p.nome),
      september:(p.tags||[]).includes('catalogo_set26'),reviewPending:PENDENTES[a.id]||a.pendencia||null,
      reviewRequired:!!env.extra?.auditoria?.revisaoObrigatoria&&!a.revisadoEm,
      stock:p.fornecedor==='flexx'?((p.tags||[]).includes('catalogo_set26')?'No catálogo de setembro':'Só no site, estoque não confirmado'):'Prateleira · data da foto '+dateText(p.fotoEm||p.etiquetaEm),
      pending:['Peso e medidas embaladas.','Conteúdo da embalagem e quantidade do kit.','Estoque, prazo de reposição e prazo para atender o pedido.',p.fornecedor==='flexx'?'Qualidade do fornecedor: Flexx ainda não comprada.':'Qualidade e disponibilidade do lote: Logospan já utilizada.'],
    };
    if(/brinquedo|bebê/i.test(cat||'')||/elétric|eletric|usb|led|bateria|caneta.*3d/i.test(p.nome)) r.pending.push('Conferir certificação INMETRO aplicável, alimentação e voltagem.');
    if(!r.unit)r.pending.push('Decidir antes de publicar como atender a primeira venda sem comprar a caixa.');
    if(r.approximate)r.pending.push('Validar a procura pelo modelo do fornecedor: a demanda observada pertence a um produto similar, não idêntico.');
    if(n(a.nota)!=null&&a.nota<3.5)r.pending.push('Avaliação baixa da referência ('+num(a.nota)+'/5): investigar reclamações e qualidade antes de publicar.');
    if(r.siteBox!=null&&r.siteBox!==r.box)r.pending.push('Caixa diverge: catálogo '+num(r.box)+'; site '+num(r.siteBox)+'. Confirmar condição vigente.');
    if(r.reviewPending)r.pending.push(r.reviewPending);
    if(quantity==null)r.pending.push('Quantidade por anúncio não coletada: não assumir uma unidade.');
    if(r.quantityPending)r.pending.push('Munição: confirmar quantas unidades do fornecedor compõem o kit; a conta cadastrada é provisória.');
    if(r.demand.age==null)r.pending.push('Data de criação não coletada.');
    r.stability='não demonstrada';
    Object.assign(r,classify(r));
    r.score=env.score(classic?.margin,r.monthly).pontos;
    r.math=classic?'Venda '+money(price)+' − produto '+money(totalCost)+' − comissão '+money(classic.comm)+' − tarifa '+money(classic.fixed)+' − frete '+money(classic.ship)+' − imposto '+money(classic.taxV)+' − embalagem '+money(classic.o?.other)+' − ads '+money(classic.adsV)+' = '+money(classic.profit)+' ('+pct(classic.margin)+').':'Conta pendente: não substituir campos ausentes por zero.';
    r.reading=(catalog?'Catálogo':'Anúncio próprio')+' com entrada '+entrance+'. Referência a '+money(price)+', '+num(r.monthly)+' vendas mensais estimadas; sobra '+money(classic?.profit)+' ('+pct(classic?.margin)+') no Clássico. '+r.reason;
    return r;
  }

  function enrich(data,extra){
    if(!extra)return data;
    const pairs=extra.pareamentos||[];
    const products=data.produtos.map(p=>{
      const original=new Map((p.anuncios||[]).map(a=>[a.id,{...a,...(extra.anuncios?.[a.id]?.ad||{})}]));
      for(const pair of pairs.filter(x=>x.url===p.url)){
        const ad=extra.anuncios?.[pair.id]?.ad||original.get(pair.id);
        if(!ad)continue;
        original.set(pair.id,{...original.get(pair.id),...ad,veredito:pair.veredito,qtd:pair.qtd,obs:pair.obs,revisadoEm:pair.revisadoEm,pendencia:pair.pendencia||null});
      }
      const ads=[...original.values()];
      const rawCoverage=extra.cobertura?.produtos?.[p.url],coverage=rawCoverage?{...rawCoverage,candidatosDetalhes:(rawCoverage.candidatosIds||[]).map(id=>{
        const entry=extra.anuncios?.[id];return entry?{...entry.ad,id,criadoEm:entry.created,lidoEm:entry.read,listingStatus:entry.listingStatus,fontePesquisa:entry.source}:null;
      }).filter(Boolean)}:p._coverage||null;
      return {...p,pesquisado:p.pesquisado||pairs.some(x=>x.url===p.url),anuncios:ads,iguais:ads.filter(a=>a.veredito==='igual').length,parecidos:ads.filter(a=>a.veredito==='parecido').length,_coverage:coverage,_siteLidoEm:extra.catalogoAtual?.produtos?.[p.url]?extra.catalogoAtual.lidoEm:null};
    });
    return {...data,produtos:products,fornecedores:(data.fornecedores||[]).map(f=>({...f,pesquisados:products.filter(p=>p.fornecedor===f.id&&p.pesquisado).length}))};
  }
  function build(data,env){
    data=enrich(data,env.extra);
    const suppliers=Object.fromEntries((data.fornecedores||[]).map(f=>[f.id,f]));
    const order={'Promissor':0,'Precisa de mais análise':1,'Não vale o teste':2};
    const marketRank=r=>(n(r.market?.strong)||0)*100+(n(r.market?.growing)||0)*20+(r.market?.complete?10:0)+(r.approximate?0:5)+(r.market?.coverage?.candidatos?Math.min(1,(n(r.market.coverage.revisados)||0)/r.market.coverage.candidatos):0);
    return (data.produtos||[]).map(p=>analyze(p,suppliers[p.fornecedor],env)).filter(Boolean).sort((a,b)=>order[a.status]-order[b.status]||marketRank(b)-marketRank(a)||b.score-a.score||a.name.localeCompare(b.name));
  }
  const state={sheet:null,rows:[],data:null,extra:null,discovery:{},all:false,q:'',supplier:'',unit:false,own:false,color:'',september:false,limit:20};
  let extraPromise=null;
  function discover(data,radar,tokenize,match,now=today()){
    const index=new Map(),results={};
    for(const p of radar?.products||[]){
      const days=age(p.pub,now);
      if(days==null||days<1||days>=CONFIG.idade||n(p.m)==null||p.m/days<CONFIG.diaria)continue;
      const candidate={...p,_tk:tokenize(p.n)};
      for(const token of candidate._tk){if(!index.has(token))index.set(token,[]);index.get(token).push(candidate);}
    }
    for(const p of data.produtos){
      const ref={n:p.nome,_tk:tokenize(p.nome)},seen=new Map(),known=new Set((p.anuncios||[]).map(a=>a.id));
      for(const token of ref._tk)for(const a of index.get(token)||[]){
        if(known.has(a.i))continue;
        const short=ref._tk.size>=2&&ref._tk.size<=3&&[...ref._tk].every(t=>a._tk.has(t));
        if(match(ref,a)||short)seen.set(a.i,a);
      }
      if(seen.size)results[p.url]=[...seen.values()].sort((a,b)=>b.m-a.m).slice(0,5).map(a=>({id:a.i,nome:a.n,preco:a.pr,vendas:a.m,criadoEm:a.pub}));
    }
    return results; // sugestões por texto; nunca inseridas em anuncios/veredito
  }
  function latestReadings(extra,radar){
    const generated=radar?.meta?.generatedAt;
    if(!generated)return extra;
    const entries={...extra.anuncios};
    for(const p of radar.products||[]){
      const old=entries[p.i];
      if(!old || !Number.isFinite(Date.parse(generated)) || Date.parse(generated)<=Date.parse(old.lidoEm||old.read||0))continue;
      entries[p.i]={...old,created:p.pub||old.created,read:null,monthly:n(p.m),lidoEm:generated,source:'Radar / rodada exportada; data efetiva da JoomPulse não coletada neste JSON',
        ad:{...old.ad,id:p.i,nome:p.n,img:p.img,preco:n(p.pr),vendas_mes:n(p.m),vendas_sem:n(p.w),criadoEm:p.pub||old.created,lidoEm:null,exportadoEm:generated,avaliacoes:n(p.rc),bb:n(p.bb),catalogo:p.c,full:p.full,frete_gratis:p.fs,l1:p.l1,tipo:p.lt,vendedor:p.s}};
      // O piso de catálogo precisa vir de todas as ofertas daquele catálogo.
      if(p.c===true)entries[p.i].ad.preco_min=null;
    }
    return {...extra,anuncios:entries};
  }
  async function withReadings(data){
    if(!extraPromise)extraPromise=fetch('oportunidades.json?v=20260909r4').then(r=>{if(!r.ok)throw new Error('Leitura pontual indisponível');return r.json();}).catch(e=>{extraPromise=null;throw e;});
    state.extra=latestReadings(await extraPromise,typeof S==='undefined'?null:S);
    const enriched=enrich(data,state.extra);
    if(typeof tokensNome!=='undefined'&&typeof parecidos!=='undefined')state.discovery=discover(enriched,typeof S==='undefined'?null:S,tokensNome,parecidos);
    return enriched;
  }
  function environment(){
    const dates={};
    for(const p of S.products||[]) if(p.pub) dates[p.i]={created:p.pub,read:null,source:'Radar / data.json (data de criação)'};
    Object.assign(dates,state.extra?.anuncios||{});
    return {extrato,max:custoMaximo,cat:(a,p)=>{const c=catDe(a,p);return a.l1&&FEES.comm[a.l1]?c:p.categoria?.l1&&FEES.comm[p.categoria.l1]?p.categoria.l1:null;},
      score:pontosDe,rows:FORN_ROWS,dates,extra:state.extra,missing:state.extra?.naoRetornados,exported:forn.data.geradoEm,now:today(),catalogLimits:OPP_CATALOGO,ownLimits:OPP_PROPRIO};
  }
  function selected(){
    const query=state.q.toLocaleLowerCase('pt-BR');
    const hasMarketSignal=r=>{
      if(r.status==='Promissor')return true;
      const viableMargin=n(r.classic?.margin)!=null&&r.classic.margin>=CONFIG.margem;
      const viableEntrance=r.entrance!=='fechada'&&(!r.catalog||(r.entrance==='aberta'&&n(r.maxFloor)!=null&&r.maxFloor>r.cost));
      return r.status==='Precisa de mais análise'&&!r.researchOnly&&(n(r.market?.strong)||0)>0&&viableMargin&&viableEntrance&&!r.reviewPending&&!r.reviewRequired;
    };
    return state.rows.filter(r=>r.demand.age!=null&&r.demand.age<CONFIG.idade&&(state.all||hasMarketSignal(r))&&(!state.supplier||r.supplierId===state.supplier)&&(!state.unit||r.unit)&&(!state.own||r.catalog===false)&&(!state.color||r.radar?.cor===state.color)&&(!state.september||r.september)&&(!query||(r.name+' '+r.supplier).toLocaleLowerCase('pt-BR').includes(query)));
  }
  const provenance=(source,date)=>`<small class="ot-source">${esc(source)} · ${date?'exportado/lido em '+dateText(date):'leitura não coletada'}</small>`;
  const metric=(label,value,detail,source,date)=>`<div class="ot-metric"><span>${label}</span><strong>${value}</strong><div>${detail}</div>${provenance(source,date)}</div>`;
  function card(r,index){
    const cls=r.status==='Promissor'?'good':r.status==='Não vale o teste'?'bad':'warn';
    const strong=n(r.market?.strong),growing=n(r.market?.growing);
    const strongText=strong==null?'não coletado':num(strong)+' vendedor'+(strong===1?'':'es')+' forte'+(strong===1?'':'s');
    const growingText=growing==null?'não coletado':num(growing)+' em crescimento';
    return `<article class="ot-card ot-compact" data-url="${esc(r.url)}" data-sheet="${esc(r.url)}" data-status="${esc(r.status)}" tabindex="0" role="link" aria-label="Ver ficha de ${esc(r.name)}">
      <span class="ot-rank">${index+1}</span><img class="ot-thumbnail" src="${esc(r.img||'')}" alt="" loading="lazy">
      <div class="ot-card-name"><h3>${esc(r.name)}</h3><span class="ot-supplier">${esc(r.supplier)}</span><div class="tags"><span class="tag">${r.catalog===true?'Catálogo':r.catalog===false?'Anúncio próprio':'Tipo não coletado'}</span><span class="tag">${num(r.demand.age)} dias de criação</span>${r.approximate?'<span class="tag">Referência aproximada</span>':''}</div></div>
      <div class="ot-card-status"><span class="ot-badge ${cls}">${esc(r.status)}</span><small>${r.unit?'Aceita unidade':num(r.box)+' un. por caixa'}${r.radar?' · Radar '+esc(r.radar.cor):''}</small><small class="ot-market-line">${strongText} · ${growingText} · ${r.market?.complete?'busca concluída':'busca parcial'}</small></div>
      <div class="ot-card-value"><small>Vendas/mês</small><b>${num(r.monthly)}</b><small>estimativa da referência</small></div>
      <div class="ot-card-value"><small>Preço de venda</small><b>${money(r.price)}</b><small>Custo ${money(r.cost)}</small></div>
      <div class="ot-card-value"><small>Sobra Clássico</small><b>${money(r.classic?.profit)}</b><small>${pct(r.classic?.margin)} de margem</small></div>
      <div class="ot-card-action"><span>Ver ficha →</span><a href="https://produto.mercadolivre.com.br/${esc(String(r.ref.id).replace('MLB','MLB-'))}" target="_blank" rel="noopener">Mercado Livre ↗</a></div></article>`;
  }
  function isRecent(a,env){
    const days=age(a.criadoEm||a.adPublishDate||env.dates?.[a.id]?.created,env.now);
    return days!=null&&days<CONFIG.idade;
  }
  function closeSheet(){
    state.sheet=null;history.replaceState(null,'','#oportunidades');render();
  }
  function leave(t){
    if(t!=='oport')document.getElementById('ot-sheet')?.remove();
  }
  function renderSheet(){
    const product=state.data.produtos.find(p=>p.url===state.sheet);
    if(!product){closeSheet();return;}
    const env=environment(),r=state.rows.find(x=>x.url===state.sheet);
    const recent=(product.anuncios||[]).filter(a=>isRecent(a,env));
    const root=document.getElementById('oport-root');
    root.innerHTML='<div class="ot-sheet-heading"><span>QUICKBUY · ETAPA 1</span><h2>Oportunidade de fornecedores</h2></div><div id="ot-sheet"></div>';
    document.getElementById('forn-root').replaceChildren();
    const sheet=document.getElementById('ot-sheet');
    if(!recent.length){sheet.innerHTML='<button class="btn ot-back">← Voltar às oportunidades</button><p>Nenhum anúncio com criação comprovada há menos de 45 dias. Este produto não tem referência recente para o teste.</p>';sheet.querySelector('button').onclick=closeSheet;return;}
    forn.sup=product.fornecedor;forn.prod=product.url;forn.view='produto';
    if(!forn.calc[product.url]&&r?.price!=null&&r.quantity>0)forn.calc[product.url]={tipo:'c',cat:env.cat(r.ref,product),preco:r.price/r.quantity};
    const filtered={...product,anuncios:recent,mesma_categoria:(product.mesma_categoria||[]).filter(a=>isRecent(a,env))};
    fornProduto(sheet,state.data.fornecedores.find(f=>f.id===product.fornecedor),filtered);
    const excluded=(product.anuncios||[]).filter(a=>!isRecent(a,env));
    const old=excluded.filter(a=>age(a.criadoEm||a.adPublishDate||env.dates?.[a.id]?.created,env.now)!=null).length;
    sheet.querySelector('.ot-back').insertAdjacentHTML('afterend',`<p class="ot-age-note">Concorrentes com menos de 45 dias desde a criação. ${old} antigos e ${excluded.length-old} sem data comprovada ficaram fora desta ficha.</p>`);
    sheet.querySelector('.crumb').innerHTML=`<span>Oportunidade de fornecedores</span><span>›</span><b>${esc(product.nome)}</b>`;
    history.replaceState(null,'','#oportunidades/produto/'+encodeURIComponent(product.url));
  }
  function openSheet(url){
    state.sheet=url;renderSheet();window.scrollTo({top:0});
  }
  function renderCards(){
    const list=document.querySelector('#ot-results');if(!list)return;
    const rows=selected();document.querySelector('#ot-count').textContent=rows.length+(state.all?' produtos analisados com referência recente':' candidatos com ao menos um sinal de mercado revisado')+' · '+state.rows.filter(r=>r.status==='Promissor').length+' Promissor no universo pesquisado';
    const strong=state.rows.filter(r=>r.status==='Promissor');document.getElementById('ot-selection-note').textContent=strong.length?strong.length+' candidatos atendem às regras na base coletada. Isso indica potencial para anúncio, não venda garantida.':'Nenhum produto tem evidência suficiente para ser Promissor na base coletada. Não há indicação de teste aprovada neste momento.';
    list.innerHTML=rows.slice(0,state.limit).map(card).join('')||'<p class="empty">Nenhum produto com estes filtros. Use Ver todos os analisados para consultar casos fracos, pendentes e reprovados.</p>';
    document.querySelector('#ot-more').hidden=rows.length<=state.limit;
  }
  function csv(rows){
    const flat=r=>({produto:r.name,fornecedor:r.supplier,url:r.url,classificacao:r.status,motivo:r.reason,referencia_aproximada:r.approximate,aceita_unidade:r.unit,referencia:r.ref.id,lider_mercado:r.leader?.id,anuncios_avaliados:r.evaluated?.length,pareamento:r.ref.obs,pendencia_pareamento:r.reviewPending,pesquisa_recente:r.coverage?.buscado,paginacao_completa:r.coverage?.paginacaoCompleta,candidatos_pesquisa:r.coverage?.candidatos,candidatos_revisados:r.coverage?.revisados,vendedores_recentes_fortes:r.market?.strong,anuncios_em_crescimento:r.market?.growing,diagnostico_mercado:r.market?.diagnosis,preco:r.price,faixa_min:r.low,faixa_max:r.high,piso_catalogo:r.floor,custo_unitario:r.unitCost,qtd:r.quantity,custo_kit:r.cost,sobra_classico:r.classic?.profit,margem_classico:r.classic?.margin,sobra_premium:r.premium?.profit,margem_premium:r.premium?.margin,sobra_piso:r.floorResult?.profit,custo_maximo_20:r.maxCost,custo_maximo_piso:r.maxFloor,vendas_mes:r.monthly,vendas_semana:r.weekly,crescimento_semana_vs_mes:r.growth,media_dia:r.demand.daily,media_limite_inferior:r.demand.lowerBound,fonte_media:r.demand.source,data_leitura:r.demand.read,criacao:r.demand.created,idade:r.demand.age,dias_no_ar:r.activityDays,catalogo:r.catalog,vendedores:r.bb,avaliacoes:r.rc,entrada:r.entrance,full:r.ref.full,frete_gratis:r.ref.frete_gratis,caixa:r.box,caixa_site:r.siteBox,capital:r.capital,estoque:r.stock,semaforo:r.radar?.cor,nota_radar:r.radar?.nota,motivo_radar:r.radar?.motivo,conta:r.math,estabilidade:r.stability,pendencias:r.pending.join(' | '),plano:OPT_PLANO,exportadoEm:r.exported});
    const objects=rows.map(flat),keys=Object.keys(flat(rows[0]||{ref:{},demand:{},pending:[]}));
    const q=v=>'"'+String(v==null?'não coletado':v).replace(/^[=+@-]/,"'$&").replace(/"/g,'""')+'"';
    return [keys.map(q).join(';'),...objects.map(o=>keys.map(k=>q(o[k])).join(';'))].join('\r\n');
  }
  function render(){
    if(state.sheet){renderSheet();return;}
    const root=document.getElementById('oport-root');
    root.innerHTML=`<div class="ot-intro"><span>QUICKBUY · ETAPA 1</span><h2>Oportunidade de fornecedores</h2><p>Produtos para investir tempo no anúncio. Comprar estoque só depois de validar a venda e avaliar o pedido.</p><p>Menos de ${CONFIG.idade} dias desde a criação · pelo menos ${CONFIG.diaria} venda/dia em ${CONFIG.repeticao} vendedores comparáveis · crescimento mínimo de ${pct(CONFIG.crescimento)} no ritmo semanal · margem de ${pct(CONFIG.margem)} no Clássico · pesquisa concluída.</p><small>O crescimento compara a última semana com a média mensal do mesmo anúncio; não soma anúncios e não substitui histórico. Catálogo exportado em ${dateText(state.data.geradoEm)}. Vendas estimadas pela JoomPulse. Exportação não renova a leitura do mercado. A aba usa somente JSONs, sem tokens ou coleta.</small></div>
    <div class="ot-filters"><label>Buscar<input id="ot-query" type="search" value="${esc(state.q)}" placeholder="Nome do produto"></label><label>Fornecedor<select id="ot-supplier"><option value="">Todos</option>${state.data.fornecedores.map(f=>`<option value="${esc(f.id)}" ${state.supplier===f.id?'selected':''}>${esc(f.nome)}</option>`).join('')}</select></label><label>Semáforo<select id="ot-color"><option value="">Todos</option>${['verde','amarelo','vermelho'].map(c=>`<option ${state.color===c?'selected':''}>${c}</option>`).join('')}</select></label><label class="ot-toggle"><input id="ot-unit" type="checkbox" ${state.unit?'checked':''}> Aceita unidade</label><label class="ot-toggle"><input id="ot-own" type="checkbox" ${state.own?'checked':''}> Anúncio próprio</label><label class="ot-toggle"><input id="ot-september" type="checkbox" ${state.september?'checked':''}> Catálogo de setembro</label><button class="btn" id="ot-all" aria-pressed="${state.all}">${state.all?'Só candidatos com sinal':'Ver todos os analisados'}</button><button class="btn" id="ot-csv">Baixar CSV</button></div><p id="ot-count" role="status"></p><p id="ot-selection-note" class="ot-selection-note"></p><div id="ot-results"></div><button class="btn" id="ot-more">Mostrar mais produtos</button>`;
    const readDates=Object.values(state.extra?.anuncios||{}).map(x=>x.lidoEm).filter(Boolean).sort();
    const collection=state.extra?.auditoria?.coleta;
    if(collection)root.querySelector('.ot-intro').insertAdjacentHTML('beforeend',`<details class="ot-research"><summary>Limite da pesquisa desta rodada</summary><p>${esc(collection.mensagem)}</p><p>Renovação informada pela JoomPulse: ${dateText(collection.retomaEm)}.</p></details>`);
    const site=state.extra?.catalogoAtual;
    if(site)root.querySelector('.ot-intro').insertAdjacentHTML('beforeend',`<p class="ot-source">Site da Flexx relido em ${dateText(site.lidoEm)}: ${num(site.total)} produtos na listagem pública${site.concluido?' (listagem percorrida até o fim)':' (leitura parcial)'}. Preço publicado não confirma estoque ou prazo.</p>`);
    const discovered=Object.entries(state.discovery);
    if(discovered.length)root.querySelector('.ot-intro').insertAdjacentHTML('beforeend',`<details class="ot-research"><summary>${discovered.length} produtos com sugestões novas no Radar — conferir modelo e kit</summary><p>Cruzamento automático dos JSONs, sem tokens. Até cinco referências por produto; são candidatos por texto, não aprovações. Dados da rodada exportada em ${dateText(S.meta?.generatedAt)}.</p><ul>${discovered.map(([url,ads])=>`<li><b>${esc(state.data.produtos.find(p=>p.url===url)?.nome)}</b>: ${ads.map(a=>`${esc(a.id)} · ${esc(a.nome)} · ${money(a.preco)} · ${num(a.vendas)} vendas/mês`).join('; ')}</li>`).join('')}</ul></details>`);
    const coverage=state.extra?.cobertura;
    if(coverage)root.querySelector('.ot-intro').insertAdjacentHTML('beforeend',`<div class="ot-coverage"><b>${num(coverage.total)} produtos no catálogo</b><span>${num(coverage.pesquisadosAntes)} com pesquisa anterior</span><span>${num(coverage.buscados)} incluídos na busca recente</span><span>${num(coverage.comPareamentoRevisado)} com novas comparações revisadas</span></div><p>Um líder antigo não elimina um anúncio recente. Todos os anúncios conferidos são avaliados separadamente; vendas de anúncios diferentes nunca são somadas. Ausência de resultado na amostra não prova ausência de demanda.</p><details class="ot-research"><summary>Cobertura da pesquisa e produtos pendentes</summary><p>Busca por palavras gera candidatos, não confirma o produto. Páginas incompletas e produtos sem correspondência permanecem pendentes.</p><ul>${state.data.produtos.map(p=>{const c=coverage.produtos?.[p.url];return `<li><b>${esc(p.nome)}</b> · ${c?.buscado?(c.paginacaoCompleta?'busca concluída para os termos':'busca parcial; há mais páginas'):'pesquisa recente ainda pendente'} · ${num(c?.candidatos)} candidatos por texto · ${num(c?.revisados)} comparações revisadas</li>`;}).join('')}</ul></details>`);
    root.querySelector('.ot-intro').insertAdjacentHTML('beforeend',`<small class="ot-source">Consulta pontual de criação, preço e demanda: lido em ${dateText(readDates.at(-1))}. As datas efetivas de cada leitura estão na conta do cartão; o custo de aquisição vem do fornecedor.</small>`);
    // A decisão aparece primeiro. A auditoria completa continua a um clique.
    const intro=root.querySelector('.ot-intro'),audit=document.createElement('details'),summary=document.createElement('summary');
    audit.className='ot-research';summary.textContent=num(state.data.produtos.length)+' produtos no cadastro · '+num((state.extra?.pareamentos||[]).length)+' comparações visuais · cobertura, fontes e limites';
    audit.append(summary);[...intro.children].slice(4).forEach(el=>audit.append(el));intro.append(audit);
    for(const [id,key,kind] of [['ot-query','q','value'],['ot-supplier','supplier','value'],['ot-color','color','value'],['ot-unit','unit','checked'],['ot-own','own','checked'],['ot-september','september','checked']]) root.querySelector('#'+id).addEventListener('input',e=>{state[key]=e.target[kind];state.limit=20;renderCards();});
    root.querySelector('#ot-all').onclick=e=>{state.all=!state.all;e.target.textContent=state.all?'Só candidatos com sinal':'Ver todos os analisados';e.target.setAttribute('aria-pressed',state.all);state.limit=20;renderCards();};
    root.querySelector('#ot-more').onclick=()=>{state.limit+=20;renderCards();};
    root.querySelector('#ot-csv').onclick=()=>{const url=URL.createObjectURL(new Blob(['\ufeff'+csv(selected())],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='oportunidades-fornecedores.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    root.onclick=e=>{if(e.target.closest('a'))return;const b=e.target.closest('[data-sheet]');if(b)openSheet(b.dataset.sheet);};
    root.onkeydown=e=>{if(e.target.closest('a,button,input,select'))return;const b=e.target.closest('[data-sheet]');if(b&&(e.key==='Enter'||e.key===' ')){e.preventDefault();openSheet(b.dataset.sheet);}};
    renderCards();
  }
  async function load(){
    try{const route=location.hash.match(/^#oportunidades\/produto\/(.+)$/);if(route)state.sheet=decodeURIComponent(route[1]);await fornLoad(true);if(!forn.data)throw new Error('Catálogo indisponível');
      forn.data=await withReadings(forn.data);fornParaRadar();state.data=forn.data;state.rows=build(state.data,environment());render();}
    catch(e){document.getElementById('oport-root').innerHTML='<p role="alert">Não foi possível carregar as oportunidades. Recarregue a página. '+esc(e.message)+'</p>';}
  }
  function refresh(){if(state.data){state.rows=build(state.data,environment());if(!document.getElementById('tab-oport').hidden)render();}}
  const api={isRecent,closeSheet,leave,context:environment,load,refresh,build,analyze,classify,demand,growth,marketEvidence,age,csv,enrich,withReadings,latestReadings,discover,CONFIG,rows:()=>state.rows};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  if(global)global.RadarOportunidades=api;
})(typeof window==='undefined'?null:window);
