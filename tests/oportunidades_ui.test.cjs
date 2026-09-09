// Chromium limpo via Playwright Python já instalado; nunca usa perfil JoomPulse.
const {test}=require('node:test'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process'),path=require('node:path');
test('aba, cartões, ficha, frete compartilhado e celular sem erros', {timeout:120000},()=>{
 const python=process.env.RADAR_TEST_PYTHON||'python';
 const result=spawnSync(python,['-X','utf8',path.join(__dirname,'oportunidades_browser.py')],{encoding:'utf8',timeout:110000});
 assert.equal(result.status,0,result.stdout+'\n'+result.stderr);console.log(result.stdout);
});
