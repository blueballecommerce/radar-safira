/* Pedir pesquisa: foto da prateleira + formulário curto -> fila -> busca na JoomPulse.
 *
 * A página é um arquivo estático: não existe servidor para receber o formulário. Por
 * isso o pedido é gravado PRIMEIRO no próprio aparelho (IndexedDB — foto não cabe no
 * localStorage) e só depois entregue ao coletor, quando ele estiver alcançável. Assim
 * dá para fotografar a loja inteira sem sinal e sincronizar na volta.
 *
 * O coletor é o scripts/coletor.py, atrás do Tailscale no mesmo endereço da página
 * (/api). Pela página pública do GitHub ele nunca responde — HTTPS não conversa com
 * servidor local — e aí o pedido fica guardado no aparelho até você abrir pelo
 * endereço da tailnet.
 */
(function () {
  'use strict';

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ESCAPES[c]);
  const brl = n => (n == null || n === '') ? '—' : Number(n).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

  const API = 'api';              // mesmo endereço da página
  const FOTO_MAX = 1600;          // px no lado maior: a etiqueta continua legível
  const FOTO_Q = 0.85;

  const ESTADOS = {
    guardado: { rot: 'guardado no aparelho', cls: 'esp' },
    entregue: { rot: 'entregue, na fila', cls: 'ok' },
    buscando: { rot: 'buscando no Mercado Livre…', cls: 'ativo' },
    pronto: { rot: 'pesquisa pronta', cls: 'bom' },
    erro: { rot: 'deu problema', cls: 'ruim' },
  };

  /* ---------------- guarda no aparelho (IndexedDB) ----------------
     localStorage tem ~5 MB e guarda só texto; uma foto de celular estoura sozinha.
     O IndexedDB guarda Blob direto e não tem esse teto. */
  let _db;
  function db() {
    if (_db) return _db;
    _db = new Promise((ok, nao) => {
      const r = indexedDB.open('radar-pedidos', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('pedidos', { keyPath: 'id' });
      r.onsuccess = () => ok(r.result);
      r.onerror = () => nao(r.error);
    });
    return _db;
  }
  function comLoja(modo, fn) {
    return db().then(d => new Promise((ok, nao) => {
      const t = d.transaction('pedidos', modo);
      const req = fn(t.objectStore('pedidos'));
      t.oncomplete = () => ok(req ? req.result : undefined);
      t.onerror = () => nao(t.error);
      t.onabort = () => nao(t.error);
    }));
  }
  const salvar = p => comLoja('readwrite', s => s.put(p));
  const apagar = id => comLoja('readwrite', s => s.delete(id));
  const todos = () => comLoja('readonly', s => s.getAll());
  const um = id => comLoja('readonly', s => s.get(id));

  /* ---------------- foto: encolhe antes de guardar ----------------
     Uma foto de iPhone tem ~4 MB. Em 1600px e qualidade 0.85 ela cai para ~400 KB
     sem perder a etiqueta — que é justamente o que eu preciso conseguir ler. */
  function encolhe(file) {
    return new Promise((ok, nao) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        URL.revokeObjectURL(url);
        const escala = Math.min(1, FOTO_MAX / Math.max(img.width, img.height));
        const c = document.createElement('canvas');
        c.width = Math.round(img.width * escala);
        c.height = Math.round(img.height * escala);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        c.toBlob(b => b ? ok(b) : nao(new Error('não consegui converter a foto')), 'image/jpeg', FOTO_Q);
      };
      img.onerror = () => { URL.revokeObjectURL(url); nao(new Error('não consegui abrir a foto')); };
      img.src = url;
    });
  }
  const paraDataURL = blob => new Promise(ok => { const r = new FileReader(); r.onload = () => ok(r.result); r.readAsDataURL(blob); });

  /* ---------------- o coletor ---------------- */
  let coletor = { vivo: false, buscaPossivel: false, motivo: 'ainda não perguntei' };

  async function pergunta(caminho, opts, msTimeout) {
    const corta = new AbortController();
    const t = setTimeout(() => corta.abort(), msTimeout || 4000);
    try {
      const r = await fetch(API + '/' + caminho, Object.assign({ signal: corta.signal, cache: 'no-store' }, opts || {}));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return await r.json();
    } finally { clearTimeout(t); }
  }

  /* O que o coletor tem. Sem isto a lista mostraria só os pedidos feitos NESTE
     aparelho: o que ele fotografou pelo celular sumiria ao abrir no PC. */
  let remotos = [];

  async function checaColetor() {
    try {
      const s = await pergunta('saude');
      coletor = { vivo: true, buscaPossivel: !!s.busca_possivel, motivo: s.motivo || '' };
    } catch (e) {
      coletor = { vivo: false, buscaPossivel: false, motivo: e.name === 'AbortError' ? 'não respondeu' : 'não alcancei' };
      remotos = [];
    }
    return coletor;
  }

  async function puxaRemotos() {
    if (!coletor.vivo) { remotos = []; return remotos; }
    try { remotos = await pergunta('pedidos'); } catch (e) { /* fica com a lista anterior */ }
    return remotos;
  }

  async function entrega(p) {
    const fotos = await Promise.all((p.fotos || []).map(paraDataURL));
    const r = await pergunta('pedido', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: p.id, criado: p.criado, nome: p.nome, fornecedor: p.fornecedor,
        custo: p.custo, qtd_caixa: p.qtdCaixa, obs: p.obs, fotos: fotos,
      }),
    }, 120000);
    p.status = r.status || 'entregue';
    p.entregueEm = new Date().toISOString();
    p.motivo = r.motivo || '';
    await salvar(p);
    return p;
  }

  /* Sobe tudo que ainda está só no aparelho. Roda ao abrir a aba e depois de enviar. */
  async function sincroniza() {
    if (!coletor.vivo) return 0;
    const pend = (await todos()).filter(p => p.status === 'guardado');
    let n = 0;
    for (const p of pend) {
      try { await entrega(p); n++; }
      catch (e) { p.motivo = 'não consegui entregar: ' + e.message; await salvar(p); }
    }
    return n;
  }

  /* Enquanto houver pedido em andamento, pergunta o estado ao coletor. */
  let relogio = null;
  function acompanha() {
    clearInterval(relogio);
    const passo = async () => {
      if (!coletor.vivo) { clearInterval(relogio); return; }
      const antes = JSON.stringify(remotos);
      const lista = await puxaRemotos();
      const meus = await todos();
      let mudou = false;
      for (const p of meus) {
        const r = lista.find(x => x.id === p.id);
        if (!r) continue;
        if (r.status !== p.status || JSON.stringify(r.resultado || null) !== JSON.stringify(p.resultado || null)) {
          p.status = r.status; p.resultado = r.resultado; p.motivo = r.motivo || '';
          await salvar(p); mudou = true;
        }
      }
      if (mudou || JSON.stringify(remotos) !== antes) desenha();
      const emAndamento = p => p.status === 'buscando' || p.status === 'entregue';
      if (!meus.some(emAndamento) && !remotos.some(emAndamento)) clearInterval(relogio);
    };
    relogio = setInterval(passo, 4000);
    passo();
  }

  /* ---------------- a tela ---------------- */
  let rascunho = { fotos: [] };
  const urls = [];                                     // para devolver a memória depois
  function urlDe(blob) { const u = URL.createObjectURL(blob); urls.push(u); return u; }
  function soltaUrls() { while (urls.length) URL.revokeObjectURL(urls.pop()); }

  function aviso() {
    if (coletor.vivo && coletor.buscaPossivel) {
      return '<div class="ped-aviso ok">Coletor ligado. O pedido entra na fila e a busca começa sozinha.</div>';
    }
    if (coletor.vivo) {
      return '<div class="ped-aviso atencao"><b>Coletor ligado, mas a busca não pode rodar agora:</b> ' +
        esc(coletor.motivo || 'motivo não informado') +
        '. O pedido fica guardado na fila e a busca roda assim que isso for resolvido.</div>';
    }
    const publico = location.hostname.indexOf('github.io') >= 0;
    return '<div class="ped-aviso atencao"><b>Coletor não alcançado</b> — o pedido fica guardado no seu aparelho e sobe sozinho ' +
      'quando você abrir a página com o coletor ligado. ' +
      (publico
        ? 'Você está na página pública: o envio só chega pelo endereço da tailnet (<code>dojoo.tailce25ed.ts.net:8444</code>), porque uma página https não conversa com servidor local.'
        : 'Confira se o coletor está rodando no PC.') +
      '</div>';
  }

  /* `p` pode vir de dois lugares: do aparelho (foto é Blob, dá para apagar) ou do
     coletor (foto é um endereço, e apagar teria de ser lá). Os nomes dos campos
     também mudam — no coletor eles vêm como o Python grava. */
  function fichaPedido(p, remoto) {
    const e = ESTADOS[p.status] || ESTADOS.guardado;
    const caixa = remoto ? p.qtd_caixa : p.qtdCaixa;
    const fotos = remoto
      ? (p.fotos || []).map(a => '<img src="' + API + '/foto/' + encodeURIComponent(p.id) + '/' + encodeURIComponent(a) + '" alt="">').join('')
      : (p.fotos || []).map(b => '<img src="' + urlDe(b) + '" alt="">').join('');
    const res = p.resultado
      ? '<div class="ped-res"><b>' + esc(p.resultado.catalogos) + '</b> catálogo(s) encontrado(s) no Mercado Livre' +
        (p.resultado.anuncios ? ' · ' + esc(p.resultado.anuncios) + ' anúncios' : '') +
        '. <span class="ped-nota">Falta a conferência foto a foto — essa parte eu faço olhando.</span></div>'
      : '';
    return '<article class="ped-item" data-id="' + esc(p.id) + '">' +
      '<div class="ped-fotos">' + (fotos || '<span class="ped-semfoto">sem foto</span>') + '</div>' +
      '<div class="ped-corpo">' +
        '<h4>' + esc(p.nome) + '</h4>' +
        '<div class="ped-meta">' + esc(p.fornecedor || 'fornecedor não informado') +
          ' · custo ' + brl(p.custo) +
          (caixa ? ' · caixa com ' + esc(caixa) : '') +
          ' · ' + new Date(p.criado).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) +
          (remoto ? ' · <span class="ped-fonte">veio de outro aparelho</span>' : '') + '</div>' +
        (p.obs ? '<div class="ped-obs">' + esc(p.obs) + '</div>' : '') +
        res +
        (p.motivo ? '<div class="ped-motivo">' + esc(p.motivo) + '</div>' : '') +
      '</div>' +
      '<div class="ped-lado">' +
        '<span class="ped-estado ' + e.cls + '">' + e.rot + '</span>' +
        (remoto ? '' : '<button class="btn ghost ped-apagar" type="button">Apagar</button>') +
      '</div>' +
    '</article>';
  }

  async function desenha() {
    const raiz = $('#ped-root');
    if (!raiz) return;
    soltaUrls();
    // os deste aparelho primeiro (têm a foto em mãos); do coletor, só o que não
    // estiver aqui — senão o mesmo pedido apareceria duas vezes
    const meus = await todos();
    const idsLocais = new Set(meus.map(p => p.id));
    const lista = meus.map(p => ({ p: p, remoto: false }))
      .concat(remotos.filter(r => !idsLocais.has(r.id)).map(r => ({ p: r, remoto: true })))
      .sort((a, b) => String(b.p.criado || '').localeCompare(String(a.p.criado || '')));
    raiz.innerHTML =
      '<h2>Pedir pesquisa de um produto</h2>' +
      '<p class="lead">Tire a foto do produto na prateleira, diga o que é e quanto custa, e envie. O pedido entra na fila ' +
      'e a busca pelos anúncios iguais no Mercado Livre começa em seguida. Funciona sem sinal: o pedido fica guardado ' +
      'no aparelho e sobe sozinho depois.</p>' +
      aviso() +
      '<div class="ped-form card">' +
        '<div class="ped-botoes">' +
          '<label class="btn primary">📷 Tirar foto' +
            '<input type="file" accept="image/*" capture="environment" multiple hidden id="ped-camera"></label>' +
          '<label class="btn">🖼️ Escolher do celular' +
            '<input type="file" accept="image/*" multiple hidden id="ped-galeria"></label>' +
        '</div>' +
        '<div class="ped-preview" id="ped-preview"></div>' +
        '<div class="ped-campos">' +
          '<label class="ped-campo larga"><span>O que é o produto <b class="ped-obrig">*</b></span>' +
            '<input id="ped-nome" type="text" placeholder="ex.: arma lança dardos com mira laser" autocomplete="off">' +
            '<small>É por este nome que eu procuro no Mercado Livre. Escreva como o anúncio seria.</small></label>' +
          '<label class="ped-campo"><span>Fornecedor</span>' +
            '<select id="ped-forn">' +
              '<option value="Logospan">Logospan</option>' +
              '<option value="Flexx Imports">Flexx Imports</option>' +
              '<option value="outro">outro…</option>' +
            '</select></label>' +
          '<label class="ped-campo" id="ped-outro-wrap" hidden><span>Qual fornecedor</span>' +
            '<input id="ped-outro" type="text" placeholder="nome da loja" autocomplete="off"></label>' +
          '<label class="ped-campo"><span>Custo por unidade (R$)</span>' +
            '<input id="ped-custo" type="number" inputmode="decimal" step="0.01" min="0" placeholder="9.98"></label>' +
          '<label class="ped-campo"><span>Unidades na caixa</span>' +
            '<input id="ped-qtd" type="number" inputmode="numeric" step="1" min="1" placeholder="12"></label>' +
          '<label class="ped-campo larga"><span>Observação</span>' +
            '<textarea id="ped-obs" rows="2" placeholder="ex.: só tinha 3 na prateleira; a etiqueta estava cortada"></textarea></label>' +
        '</div>' +
        '<div class="ped-acoes">' +
          '<button class="btn primary" type="button" id="ped-enviar">Enviar e buscar</button>' +
          '<button class="btn ghost" type="button" id="ped-limpar">Limpar</button>' +
          '<span class="ped-status" id="ped-status" role="status"></span>' +
        '</div>' +
      '</div>' +
      '<h3 class="ped-titulo-lista">Pedidos' + (lista.length ? ' <span class="ped-conta">' + lista.length + '</span>' : '') + '</h3>' +
      (lista.length ? lista.map(x => fichaPedido(x.p, x.remoto)).join('')
                    : '<div class="empty">Nenhum pedido ainda. O primeiro aparece aqui assim que você enviar.</div>');
    liga();
    pintaPreview();
  }

  function pintaPreview() {
    const el = $('#ped-preview');
    if (!el) return;
    el.innerHTML = rascunho.fotos.map((b, i) =>
      '<div class="ped-mini"><img src="' + urlDe(b) + '" alt="">' +
      '<button type="button" data-i="' + i + '" aria-label="tirar esta foto">×</button></div>').join('');
    $$('button', el).forEach(b => b.onclick = () => { rascunho.fotos.splice(+b.dataset.i, 1); pintaPreview(); });
  }

  const diz = (t, ruim) => { const el = $('#ped-status'); if (el) { el.textContent = t; el.classList.toggle('ruim', !!ruim); } };

  async function pegaFotos(input) {
    const arqs = [].slice.call(input.files);
    input.value = '';
    if (!arqs.length) return;
    diz('preparando ' + arqs.length + ' foto(s)…');
    for (const a of arqs) {
      try { rascunho.fotos.push(await encolhe(a)); }
      catch (e) { diz('uma foto não abriu: ' + e.message, true); }
    }
    diz('');
    pintaPreview();
  }

  function liga() {
    const cam = $('#ped-camera'), gal = $('#ped-galeria');
    if (cam) cam.onchange = () => pegaFotos(cam);
    if (gal) gal.onchange = () => pegaFotos(gal);

    const forn = $('#ped-forn');
    if (forn) forn.onchange = () => { $('#ped-outro-wrap').hidden = forn.value !== 'outro'; };

    const limpar = $('#ped-limpar');
    if (limpar) limpar.onclick = () => { rascunho = { fotos: [] }; desenha(); };

    const enviar = $('#ped-enviar');
    if (enviar) enviar.onclick = envia;

    $$('.ped-apagar').forEach(b => b.onclick = async () => {
      await apagar(b.closest('.ped-item').dataset.id);
      desenha();
    });
  }

  async function envia() {
    const nome = ($('#ped-nome').value || '').trim();
    if (!nome) { diz('Escreva o que é o produto — é por ele que eu busco.', true); $('#ped-nome').focus(); return; }
    const sel = $('#ped-forn').value;
    const p = {
      id: 'ped-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 6),
      criado: new Date().toISOString(),
      nome: nome,
      fornecedor: sel === 'outro' ? ((($('#ped-outro') || {}).value || '').trim() || 'outro') : sel,
      custo: $('#ped-custo').value ? Number($('#ped-custo').value) : null,
      qtdCaixa: $('#ped-qtd').value ? Number($('#ped-qtd').value) : null,
      obs: ($('#ped-obs').value || '').trim(),
      fotos: rascunho.fotos.slice(),
      status: 'guardado',
    };
    diz('guardando…');
    await salvar(p);
    rascunho = { fotos: [] };

    await checaColetor();
    if (coletor.vivo) {
      diz('entregando ao coletor…');
      try { await entrega(await um(p.id)); }
      catch (e) { diz('guardei no aparelho, mas não consegui entregar: ' + e.message, true); }
    }
    await desenha();
    diz(coletor.vivo ? 'pedido enviado.' : 'guardado no aparelho — sobe sozinho quando o coletor estiver ligado.');
    acompanha();
  }

  async function load() {
    await desenha();                 // o que está no aparelho aparece na hora
    await checaColetor();
    await puxaRemotos();             // e o que está no coletor entra em seguida
    await desenha();
    if (await sincroniza()) { await puxaRemotos(); await desenha(); }
    acompanha();
  }

  window.RadarPedidos = { load: load };
})();
