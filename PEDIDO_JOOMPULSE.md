# Pedido de client_id OAuth à JoomPulse

Enviar para: **contato@joompulse.com**
(assunto e corpo abaixo, é só copiar)

---

**Assunto:** Solicitação de client_id OAuth para uso próprio do MCP

Olá,

Sou cliente da JoomPulse (conta de João/Fernando, administrador — telefone +55 11 97292 8835)
e uso o conector MCP pelo Claude, que funciona normalmente.

Estou construindo uma ferramenta interna nossa que consulta o MCP de vocês diretamente,
sem passar por Claude ou ChatGPT — sempre dentro da nossa própria conta e do nosso plano.

O servidor de vocês anuncia suporte a client metadata document:

    GET https://joompulse.com/.well-known/oauth-authorization-server
    -> "client_id_metadata_document_supported": true

Seguindo isso, publiquei o documento de metadados do cliente em HTTPS, com
Content-Type: application/json:

    https://blueballecommerce.github.io/radar-safira/oauth-client.json

Conteúdo:

    {
      "redirect_uris": ["http://localhost:8765/callback"],
      "token_endpoint_auth_method": "none",
      "grant_types": ["authorization_code", "refresh_token"],
      "response_types": ["code"],
      "scope": "mcp",
      "client_name": "Radar Safira",
      "client_id": "https://blueballecommerce.github.io/radar-safira/oauth-client.json",
      "client_uri": "https://blueballecommerce.github.io/radar-safira"
    }

Porém, ao iniciar o fluxo em /oauth2/authorize com esse client_id (já autenticado no
dashboard, com sessão ativa), a resposta é sempre:

    {"error":"invalid_client","error_description":"client authentication failed"}

O mesmo erro ocorre no /noauth/oauth2/token. Testei também com outros valores de client_id
e o erro é idêntico, o que sugere que apenas clientes pré-registrados por vocês são aceitos.

Minhas perguntas:

1. O suporte a client metadata document está de fato ativo? Se sim, há alguma restrição de
   host ou algum requisito adicional no documento que eu não esteja atendendo?
2. Se não estiver ativo, vocês podem registrar um client_id para uso próprio da nossa conta?
   Preciso apenas de:
   - grant types: authorization_code + refresh_token (PKCE S256)
   - redirect_uri: http://localhost:8765/callback
   - scope: mcp
   - sem client_secret (token_endpoint_auth_method: none)
3. Existe alternativa oficial, como um token de API de longa duração para a conta?

O volume é modesto: cerca de 60 a 80 chamadas por rodada, duas rodadas por dia.

Obrigado,
João / Blue Ball Ecommerce
blue.ballecommerce@gmail.com
