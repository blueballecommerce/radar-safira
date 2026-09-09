import importlib.util
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def load_script(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_classificacao_e_conta_compartilhada():
    result=subprocess.run(['node',str(ROOT/'tests/oportunidades_rules.cjs')],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stdout+result.stderr


def test_integracao_idempotente_preserva_outras_abas():
    html=(ROOT/'docs/index.html').read_text('utf-8')
    integration=load_script('integrar_oportunidades')
    assert integration.integrate(html)==html
    for text in ['data-tab="conc"','data-tab="forn"','data-tab="ped"','data-tab="oport"','id="oport-root"']:
        assert text in html


def test_veredito_direto_duas_chaves_sem_alterar_outros(tmp_path):
    v=load_script('veredito');(tmp_path/'docs').mkdir();(tmp_path/'data').mkdir()
    source=tmp_path/'docs/fornecedores.json';source.write_text(json.dumps({'produtos':[{'url':'u','anuncios':[{'id':'MLB1','chave':'cat:xyz','qtd':2}]}]}))
    output=tmp_path/'data/fornecedor_veredito.json';output.write_text(json.dumps({'outro':{'veredito':'igual'}}))
    before=source.read_bytes()
    v.registrar_direto([{'url':'u','id':'MLB1','veredito':'diferente','obs':'Confirmado pelo usuário'}],tmp_path)
    data=json.loads(output.read_text('utf-8'))
    assert data['u|MLB1']==data['u|cat:cat:xyz']
    assert data['u|MLB1']['qtd']==2 and data['outro']['veredito']=='igual'
    assert source.read_bytes()==before


def test_veredito_direto_valida_lote_antes_de_gravar(tmp_path):
    import pytest
    v=load_script('veredito');(tmp_path/'docs').mkdir();(tmp_path/'data').mkdir()
    (tmp_path/'docs/fornecedores.json').write_text(json.dumps({'produtos':[]}))
    path=tmp_path/'data/fornecedor_veredito.json';path.write_text('{}')
    with pytest.raises(ValueError):v.registrar_direto([{'url':'x','id':'MLB1','veredito':'diferente'}],tmp_path)
    assert path.read_text()=='{}'


def test_exportacao_pontual_preserva_datas_da_fonte(tmp_path):
    from radar.oportunidades import exportar
    folder=tmp_path/'data/oportunidades';folder.mkdir(parents=True)
    doc={'lidoEm':'2026-09-09T15:00:00Z','fonte':'JoomPulse','requestedIds':['MLB1','MLB2'],
         'pages':[{'columns':['id','date','adPublishDate','orderCount1m','listingStatus'],
                   'data':[['MLB1','2026-09-08','2026-08-25',20,'active']]}]}
    (folder/'datas.json').write_text(json.dumps(doc))
    result=exportar(tmp_path)
    assert result['anuncios']['MLB1']['read']=='2026-09-08'
    assert result['anuncios']['MLB1']['lidoEm']==doc['lidoEm']
    assert result['naoRetornados']==['MLB2']


def test_busca_parcial_nao_vira_pesquisa_completa_nem_pareamento(tmp_path):
    from radar.oportunidades import exportar
    folder=tmp_path/'data/oportunidades/auditoria';folder.mkdir(parents=True)
    (folder/'plano.json').write_text(json.dumps({'catalogo':2,'grupos':[{'terms':['caneta','3d'],'urls':['u1','u2']}]}))
    doc={'lidoEm':'2026-09-09T18:00:00Z','fonte':'JoomPulse','groups':[['caneta','3d']],
         'pages':[{'query':{'limit':1},'columns':['id','productName','date','adPublishDate','priceAmount','orderCount1m','catalogProduct'],
                   'data':[['MLB1','Caneta 3d','2026-09-08','2026-08-20',50,40,True]]}]}
    (folder/'busca-00-000.json').write_text(json.dumps(doc))
    result=exportar(tmp_path)
    assert result['pareamentos']==[]
    assert result['cobertura']['buscados']==2
    assert result['cobertura']['produtos']['u1']['paginacaoCompleta'] is False
    assert result['cobertura']['produtos']['u1']['candidatosIds']==['MLB1']
    assert result['anuncios']['MLB1']['ad']['preco_min'] is None
    assert result['anuncios']['MLB1']['ad']['preco']==50


def test_preco_e_demanda_sao_atualizados_juntos_sem_apagar_criacao(tmp_path):
    from radar.oportunidades import exportar
    folder=tmp_path/'data/oportunidades';folder.mkdir(parents=True)
    for name,date,created,price,sales in [('a','2026-09-07','2026-08-20',60,100),('b','2026-09-08',None,45,30)]:
        doc={'pages':[{'columns':['id','date','adPublishDate','priceAmount','orderCount1m'],'data':[['MLB1',date,created,price,sales]]}]}
        (folder/(name+'.json')).write_text(json.dumps(doc))
    result=exportar(tmp_path)['anuncios']['MLB1']
    assert result['created']=='2026-08-20'
    assert result['ad']['preco']==45 and result['monthly']==30
