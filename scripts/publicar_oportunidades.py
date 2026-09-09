"""Publica a aba na pasta viva, com backup e exportação apenas da correção confirmada."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime
from integrar_oportunidades import integrate
from veredito import registrar_direto

ROOT=Path(__file__).resolve().parents[1]
SERVER=Path('C:/Projeto - Radar Safira')
ASSETS=['docs/oportunidades-ficha.js','pytest.ini','docs/oportunidades.js','docs/oportunidades.css','docs/oportunidades.json','radar/oportunidades.py','data/oportunidades/datas-2026-09-09.json','scripts/integrar_oportunidades.py',
        'scripts/publicar_oportunidades.py','scripts/publicar.ps1','scripts/veredito.py','radar/fornecedor_export.py',
        'tests/test_oportunidades.py','tests/oportunidades_rules.cjs','tests/oportunidades_ui.test.cjs',
        'tests/oportunidades_browser.py','data/oportunidades/NOTAS.md','data/oportunidades/FECHAMENTO.md','data/oportunidades/confirmados.json','data/oportunidades/pendentes.json']
ASSETS += ['scripts/auditar_oportunidades.py','scripts/revisar_pares_oportunidades.py','scripts/atualizar_catalogo_oportunidades.py','data/oportunidades/pareamentos-revisados.json']
ASSETS += ['scripts/triar_referencias_oportunidades.py','data/oportunidades/auditoria/status.json']
ASSETS += [str(p.relative_to(ROOT)).replace('\\','/') for pattern in ['busca-*.json','detalhes-*.json','plano.json','catalogo-site.json'] for p in (ROOT/'data/oportunidades/auditoria').glob(pattern)]
INPUTS=['fornecedor.json','fornecedor_busca.json','fornecedor_categorias.json','fornecedor_veredito.json','fornecedor_logospan.json','fornecedor_logospan_busca.json']
def sha(b):return hashlib.sha256(b).hexdigest()

def publish():
    dest=SERVER.resolve()
    if dest!=Path('C:/Projeto - Radar Safira').resolve():raise RuntimeError('Destino inválido')
    before={rel:(dest/rel).read_bytes() for rel in ['docs/index.html','docs/fornecedores.json','docs/data.json','GUIA.md','BRIEFING_ASSISTENTE.md','scripts/publicar.ps1','scripts/veredito.py','radar/fornecedor_export.py']+['data/'+f for f in INPUTS]}
    index=integrate(before['docs/index.html'].decode('utf-8-sig').replace('\r\n','\n'))
    # Arquivos compartilhados só são copiados se ainda forem a base inspecionada.
    for rel in ['scripts/publicar.ps1','scripts/veredito.py','radar/fornecedor_export.py']:
        baseline=ROOT/'data/oportunidades/base'/rel
        if baseline.exists() and baseline.read_bytes()!=before[rel] and before[rel]!=(ROOT/rel).read_bytes():raise RuntimeError('Arquivo mudou desde a preparação: '+rel)
    backup=ROOT/'data/oportunidades'/('publicacao-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True)
    for rel,body in before.items():
        p=backup/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
    for rel in ASSETS:
        if (dest/rel).exists() and rel not in before:
            p=backup/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((dest/rel).read_bytes())
    stage=backup/'exportacao';(stage/'data').mkdir(parents=True);(stage/'docs').mkdir()
    for name in INPUTS:(stage/'data'/name).write_bytes(before['data/'+name])
    (stage/'docs/fornecedores.json').write_bytes(before['docs/fornecedores.json'])
    decisions=json.loads((ROOT/'data/oportunidades/confirmados.json').read_text('utf-8'))
    registrar_direto(decisions,stage)
    subprocess.run([sys.executable,'-X','utf8','-m','radar.fornecedor_export'],cwd=ROOT,env={**os.environ,'RADAR_ROOT':str(stage)},check=True)
    old=json.loads(before['docs/fornecedores.json']);new=json.loads((stage/'docs/fornecedores.json').read_text('utf-8'))
    oldp={p['url']:p for p in old['produtos']};newp={p['url']:p for p in new['produtos']}
    changed={key for key in oldp.keys()|newp.keys() if oldp.get(key)!=newp.get(key)}
    if not changed.issubset({d['url'] for d in decisions}) or oldp.keys()!=newp.keys():
        raise RuntimeError('Exportação alteraria outros produtos; nada publicado: '+str(changed))
    for rel,body in before.items():
        if (dest/rel).read_bytes()!=body:raise RuntimeError('Trabalho concorrente alterou '+rel+'; nada publicado')
    payload={rel:(ROOT/rel).read_bytes() for rel in ASSETS}
    payload['docs/index.html']=index.encode('utf-8')
    payload['docs/fornecedores.json']=(stage/'docs/fornecedores.json').read_bytes()
    payload['data/fornecedor_veredito.json']=(stage/'data/fornecedor_veredito.json').read_bytes()
    note=(ROOT/'data/oportunidades/NOTAS.md').read_text('utf-8')
    guide=before['GUIA.md'].decode('utf-8-sig')
    heading='## Oportunidade de fornecedores — Etapa 1 (09/09/2026)'
    if heading not in guide:guide+='\n\n'+note+'\n'
    else:
        start=guide.index(heading);end=guide.find('\n## ',start+len(heading))
        guide=guide[:start]+note+'\n'+(guide[end:] if end>=0 else '')
    payload['GUIA.md']=guide.encode('utf-8')
    briefing=before['BRIEFING_ASSISTENTE.md'].decode('utf-8-sig')
    line='| `oportunidades.js`, `oportunidades.css` | Aba Oportunidade de fornecedores: Etapa 1, contas compartilhadas, até 40 dias de criação e 1 venda/dia. Integração/publicação: `scripts/integrar_oportunidades.py` e `scripts/publicar_oportunidades.py`. |'
    line=line.replace('`oportunidades.css`','`oportunidades.css`, `oportunidades-ficha.js`').replace('Etapa 1, contas compartilhadas','Etapa 1, cartões compactos que abrem a ficha e comparação de fotos por anúncio, contas compartilhadas')
    if '`oportunidades.js`, `oportunidades.css`' in briefing:
        briefing='\n'.join(line if row.startswith('| `oportunidades.js`,') else row for row in briefing.split('\n'))
    else:
        anchor='| `data.json` (~1,8 MB) |';pos=briefing.find(anchor)
        if pos<0:raise RuntimeError('Mapa do briefing mudou')
        briefing=briefing[:pos]+line+'\n'+briefing[pos:]
    payload['BRIEFING_ASSISTENTE.md']=briefing.encode('utf-8')
    for rel,body in payload.items():
        p=(dest/rel).resolve()
        if not p.is_relative_to(dest):raise RuntimeError('Destino fora do Radar')
        p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.oportunidades-tmp');tmp.write_bytes(body);os.replace(tmp,p)
    if (dest/'docs/data.json').read_bytes()!=before['docs/data.json']:raise RuntimeError('Dados do Radar mudaram durante a publicação; verificar rodada concorrente')
    manifest={'publicadoEm':datetime.now().astimezone().isoformat(),'backup':str(backup),'arquivos':{rel:sha(body) for rel,body in payload.items()},'produtosCorrigidos':sorted(changed)}
    (backup/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true',required=True);parser.parse_args();publish()
