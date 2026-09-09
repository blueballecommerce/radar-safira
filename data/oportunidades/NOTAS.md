## Oportunidade de fornecedores — Etapa 1 (09/09/2026)

A aba **Oportunidade de fornecedores** reúne produtos para investir tempo no anúncio de teste da QuickBuy. A compra só é avaliada depois de validar venda; uma venda não autoriza comprar uma caixa inteira. A aba usa apenas JSONs existentes e as contas do Simulador; nenhuma coleta ou chamada de IA foi acrescentada à rotina diária.

Regras confirmadas por João nesta conversa, que substituem os valores do prompt inicial:

- Anúncio concorrente criado há no máximo **40 dias**, com média mínima de **1 venda por dia** desde a criação. Não há piso de 200 vendas mensais.
- Sem teto fixo de capital. Cada caixa mostra quantidade e custo para decisão caso a caso.
- Produtos similares entram com **referência aproximada**, quando o fornecedor vende unidade. Isso não transforma o parecido em igual.
- QuickBuy com reputação amarela, sem Full e com ponto de coleta. João confirmou entrega padrão. A opção de envio subsidiado entre R$ 19 e R$ 78,99 inicia ligada; o desconto de frete acima de R$ 79 fica em 0% até confirmar o desconto real.
- Após a primeira venda, observar novas vendas, avaliar o investimento e o prazo para atender os pedidos. Mais vendas reforçam o sinal; a decisão de compra continua humana.

**Promissor** exige margem mínima de 20% no Clássico, criação e demanda comprovadas nos dados e entrada viável. Catálogo com 6 ou mais vendedores nunca é Promissor; de 3 a 5 a entrada é disputada. Para catálogo aberto, a conta precisa permitir ficar abaixo do piso com 20%. Margem zero/negativa, criação acima de 40 dias ou demanda comprovadamente insuficiente descartam o teste. Informações insuficientes deixam **Precisa de mais análise**. Os descartados aparecem em **Mostrar tudo**.

Data de criação e dias de atividade são diferentes. A aba usa `criadoEm`/`adPublishDate`, ou `pub` de `data.json` ligado pelo mesmo MLB; jamais calcula criação subtraindo dias de atividade. A média usa uma estimativa de vendas desde a criação. Quando só existe uma janela de 30 ou 7 dias menor que a idade, calcula um **limite inferior** da média: isso pode comprovar a meta, mas não comprova fracasso se ficar abaixo dela. Vendas de anúncios/variações não são somadas. Falta de dados aparece como **não coletado**. Uma única observação não demonstra estabilidade.

As contas usam `extrato`, `custoMaximo`, `FEES` e as premissas atuais do Simulador, inclusive quantidade por kit. A correção do frete está no Simulador: entre R$ 19 e R$ 78,99, entrega padrão elegível é paga pelo ML; abaixo de R$ 19, frete grátis oferecido sai do vendedor; a partir de R$ 79 aplica-se a tabela de peso e reputação. Há também opção para oferecer frete grátis abaixo de R$ 79 na simulação. Alterar qualquer premissa recalcula o Radar, Fornecedores e a aba nova. Peso e dimensões do produto continuam pendentes; a faixa de peso selecionada é hipótese, não medição.

Os dados do fornecedor são uma exportação, não confirmação de estoque em tempo real. Catálogo de setembro e site são diferenciados. Divergência entre caixa do catálogo e caixa do site fica explícita; nenhuma é silenciosamente substituída. “Risco zero” significa somente ausência de estoque comprado antes da venda; não elimina risco de disponibilidade, prazo ou devolução.

O semáforo é reutilizado de `FORN_ROWS`, sem nova fórmula. Produtos só com parecido não têm semáforo inventado. A classificação da Etapa 1 é separada do semáforo. Correspondências contestadas aguardam confirmação na lupa e não podem ser Promissor enquanto pendentes.

**Consulta pontual:** foram consultadas as datas de criação e estimativas dos anúncios de referência, uma consulta por vez. A fonte bruta fica em `data/oportunidades/datas-2026-09-09.json`. `python -m radar.oportunidades` transforma esses registros em `docs/oportunidades.json`, sem rede. A aba mostra quando foram lidos e a data efetiva do dado. A coleta pontual não entra na rotina diária. Preços, custos e composição permanecem na exportação de fornecedores para manter as contas iguais entre abas; a média desde a criação usa a consulta pontual identificada no cartão.

**Correções visuais:** apenas Pulverizador × MLB4552614487 foi confirmado como diferente por João e gravado nas duas chaves pelo modo `--direto` de `scripts/veredito.py`. Os quatro pares em `data/oportunidades/pendentes.json` aguardam confirmação individual. Depois de confirmar, registrar decisões pelo modo direto e regenerar `python -m radar.fornecedor_export`. Não alterar os JSONs de `docs` à mão. A quantidade do kit de munição também permanece pendente e impede classificá-lo como Promissor.

Arquivos: `docs/oportunidades.js` contém regras e tela; `docs/oportunidades.css`, o visual. `scripts/integrar_oportunidades.py` aplica somente os pontos de entrada e a correção de frete à página atual. `scripts/publicar_oportunidades.py --publish` copia com backup para a pasta viva, preservando os demais trabalhos. Commit e `scripts/publicar.ps1` são executados na pasta viva. O relatório antigo `validacao-etapa1.md` é histórico e não alimenta a aba; seu gerador saiu da exportação de fornecedores.

Testes: `python -m pytest -q`; `node --test tests/oportunidades_ui.test.cjs` com `RADAR_TEST_PYTHON` apontando para o Python que tem Playwright. O teste abre Chromium limpo e um servidor local na porta 8090, sem usar perfil da JoomPulse nem alterar os dados reais.

Publicação a partir da pasta viva: `scripts/publicar.ps1` reconhece `C:\Projeto - Radar Safira`, envia ao GitHub e ao repositório `central` local, sem tentar SSH para a própria máquina. O caminho de publicação pelo notebook continua igual.
