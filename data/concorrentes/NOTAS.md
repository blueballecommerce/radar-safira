## Concorrentes — pesquisa inicial de 08/09/2026

A aba **Concorrentes**, ao lado de Fornecedores, começa com COMERCIALBRINKANDO e MERCADOKIDS,
encontrados respectivamente nos produtos de bolhas de sabão e conjuntos infantis do Radar.
Abra um vendedor para buscar seus produtos, filtrar categorias e ordenar por vendas, faturamento
ou preço do anúncio principal. Abra a ficha para ver características, variações e anúncios vinculados.

Foram coletados todos os 208 anúncios ativos disponíveis na JoomPulse para esses vendedores
(147 + 61), com referência de 07/09/2026. Isso não garante a cobertura de toda a loja no Mercado Livre.
A contagem de produtos é diferente da contagem de anúncios: inclui variações identificadas e agrupa
anúncios com identidade comprovada. Título parecido sozinho não elimina um anúncio.
O principal é o de maior estimativa mensal; em empate, usa o indicador público acumulado e o ID.
Cores, tamanhos e quantidades diferentes ficam separados. Uma opção sem anúncio correspondente
na fonte fica sem preço/vendas confirmados; a venda do anúncio vizinho não é atribuída a ela.

As vendas e receitas mensais/semanais são **estimativas**, não totais oficiais nem janelas móveis.
As vendas concluídas em 365 dias no perfil vêm do dado de transações do Mercado Livre.
A fonte não informa vendas por variação nem a data da primeira venda. Tempo e avaliações de catálogo
podem ser compartilhados. O custo e a margem do concorrente não são públicos.

A pesquisa é uma fotografia desta data; esta aba não foi incluída na rotina automática das 5h.
Os registros originais e as características observadas ficam em **data/concorrentes/**.
Para reconstruir a tela a partir deles: `python -m radar.concorrentes`.
O resultado é **docs/concorrentes.json**; a interface está em **docs/concorrentes.js** e **docs/concorrentes.css**.
A integração no índice preserva as outras abas. O teste específico é
`python -m unittest discover -s tests -p test_concorrentes.py`.
