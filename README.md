# Travel Radar

Sistema de inteligência de preço de passagem + orçamento de viagem, multi-destino
por config ("tenant"/roteiro). O primeiro roteiro configurado é a **Península de
Maraú** (`config/destinations/marau.yaml`), partindo do Rio de Janeiro
(GIG/SDU), janela jan-fev/2027, evitando a semana de Carnaval (06-10/fev/2027),
com 10 noites como duração alvo. **Hospedagem/Airbnb não fazem parte do
escopo** — o foco é 100% aéreo (+ traslado terrestre quando fizer sentido).

## O que ele faz

1. Consulta preço de passagem (Amadeus, grátis) pra várias combinações de data
   de ida + duração, **em cada rota alternativa configurada** (ex: voo direto
   até Ilhéus vs. voo até Salvador + ferry/ônibus/lancha).
2. Salva tudo num histórico local (SQLite) — o preço de hoje nunca se perde.
3. Compara as rotas lado a lado (aéreo + traslado) em 3 cenários: otimista /
   realista / conservador, e aponta a mais barata.
4. Rankeia os melhores dias já observados pra rota vencedora.
5. Se o roteiro estiver marcado `status: active` no yaml, confere de verdade
   no Google Voos (via SerpApi) as top-N datas mais promissoras — não é só
   estimativa, é preço real, mas limitado pra não estourar a cota grátis.
6. Dispara alerta no Telegram e por e-mail quando acha um novo menor preço
   (de qualquer fonte, inclusive a conferência real do Google Voos).
7. Gera um dashboard HTML (`data/dashboard_<tenant>.html`) com tudo isso, mais
   um guia cultural/turístico e sugestão de roteiro de dias pro destino.
8. Cada linha da tabela de "melhores dias" tem link que abre a mesma busca já
   pronta no Google Voos, pra você conferir/comprar com um clique.

Sem nenhuma API configurada, ele roda em modo "estimativa" (baseado na
pesquisa que fizemos: R$1.040–2.800 ida/volta por pessoa na rota RJ-Ilhéus)
só pra não ficar vazio — mas isso **não é preço real**, é placeholder até você
conectar a Amadeus.

## De onde vêm os preços (e por que não "todas as agências")

Não existe uma API que junte literalmente tudo, e o cenário mudou bem
recentemente: **a Amadeus fechou o cadastro self-service pra devs novos em
17/07/2026** (portal inteiro descontinuado — quem já tinha conta antes disso
continua funcionando, quem se cadastra agora não consegue mais chave grátis).
Isso encerrou a era do "GDS grátis pra projeto pessoal". O que dá pra usar de
verdade hoje:

- **Travelpayouts / Aviasales Data API** (espinha dorsal atual, roda toda
  execução, explora toda a faixa de durações): grátis, cadastro sem
  verificação de negócio. É dado real (cache de buscas reais no Aviasales,
  até 7 dias), não é cotação garantida ao vivo — por isso a SerpApi ainda
  confere as melhores datas de verdade antes de decidir.
- **Duffel**: testado e descartado como fonte real — o modo de teste só
  devolve dados fictícios ("Duffel Airways"), e o "Go live" pede verificação
  de negócio que pessoa física normalmente não passa. Mantido no código só
  por documentação/caso alguém tenha acesso corporativo.
- **Amadeus**: mantido no código só pro caso de você já ter uma conta de
  antes do fechamento (self-service novo não é mais possível).
- **Kiwi (Tequila)**: opcional, hoje só por convite pra devs novos.
- **SerpApi (Google Voos real)**: não existe API oficial do Google Voos — um
  scraper caseiro quebraria com bloqueio/CAPTCHA deles e violaria os termos de
  uso. A SerpApi roda uma sessão de navegador de verdade contra o Google Voos
  e devolve o preço em JSON. Plano grátis dá **100 buscas/mês**; se precisar
  de mais, os planos pagos começam em ~$25/mês (1.000 buscas) e sobem até
  ~$275/mês (30.000 buscas) — não tem opção de "ilimitado grátis" em lugar
  nenhum, isso é limite genuíno da indústria, não meu. Por isso só é usada
  pras poucas datas já pré-selecionadas como melhores
  (`serpapi_top_n_check` no yaml, default 3) e só quando o roteiro está
  `status: active`.

Um preço da Duffel e um do Google Voos podem legitimamente ser diferentes —
cada um consulta um conjunto distinto de companhias/tarifas — por isso ter as
duas fontes (e o link de conferência manual) é útil, não redundante.

## Avião + carro: comparando rotas alternativas

Cada rota em `route_options` (no yaml do tenant) é aéreo até um aeroporto +
traslado terrestre (van/ônibus/ferry/lancha) até o destino final. O sistema
busca passagem pra CADA rota e soma o traslado, e aponta qual dá mais barato
no total — ex: voo direto até Ilhéus (traslado curto) vs. voo até Salvador
(geralmente mais barato/mais frequente) + traslado mais longo até Barra
Grande. Pra adicionar uma rota nova, copie um bloco em `route_options` e ajuste
aeroporto + estimativa de traslado.

## Buscar qualquer cidade/país do mundo

`src/geo/airports.py` usa o dataset aberto da [OurAirports](https://ourairports.com/data/)
(domínio público, ~86 mil aeródromos, todos os países) pra resolver cidade →
aeroporto sem precisar de API paga de geocoding:

```python
from src.geo.airports import best_airport_for_city, search_countries

search_countries("Franc")              # -> ['France']
best_airport_for_city("Japan", "Osaka") # -> Airport(iata='ITM', ...)
```

## Guia cultural/turístico

Cada tenant pode ter um `config/destinations/<tenant>_guide.html` com contexto
cultural/histórico e sugestão de roteiro de dias — o dashboard exibe esse
conteúdo automaticamente se o arquivo existir. O de Maraú já está pronto
(`marau_guide.html`, com sugestão de roteiro pras 10 noites). Pra um destino
novo, esse conteúdo é gerado numa sessão de pesquisa (é isso que uso Claude +
busca na web pra fazer) — não é algo que roda sozinho no script Python.

## Setup

### 1. Instalar dependências

```bash
cd travel-radar
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Pegar as chaves de API (você faz isso, eu não posso criar conta por você)

**Travelpayouts / Aviasales Data API (obrigatório — é a espinha dorsal do sistema hoje)**
1. Crie conta em https://www.travelpayouts.com/programs/100/tools/api
2. Pegue o token (grátis, sem verificação de negócio, sem cartão)
3. Cole em `TRAVELPAYOUTS_TOKEN`

**Duffel (opcional — testamos e não dá pra usar pra dado real)**
Modo de teste só devolve avião fictício ("Duffel Airways"); o "Go live" pede
verificação de negócio que pessoa física normalmente não consegue passar.
Deixe `DUFFEL_ACCESS_TOKEN` em branco, a menos que você tenha acesso corporativo.

**Amadeus (opcional — só se você já tinha conta antes de 17/07/2026)**
A Amadeus fechou o cadastro self-service pra devs novos nessa data. Se você
já tem chave antiga, cole em `AMADEUS_CLIENT_ID`/`AMADEUS_CLIENT_SECRET` e ela
ainda funciona. Se não tem, pule — não tem como criar uma nova.

**SerpApi (opcional, mas é o que dá preço real do Google Voos)**
1. Crie conta em https://serpapi.com/users/sign_up
2. O plano grátis (100 buscas/mês) já aparece ativado, chave fica no dashboard.
3. Cole em `SERPAPI_KEY`.

**Kiwi.com Tequila (opcional — hoje só por convite)**
Em 2026 a Kiwi fechou o cadastro self-service pra devs novos; só dá pra usar se
você já tiver acesso de parceiro. Se não tiver, ignore.

**Telegram (grátis)**
1. Fale com `@BotFather` no Telegram → `/newbot` → siga o assistente → copie o token.
2. Mande "oi" pro seu bot recém-criado.
3. Acesse `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates` no navegador e
   pegue o número em `"chat":{"id": ...}` → esse é o `TELEGRAM_CHAT_ID`.

**E-mail (Gmail)**
1. Ative verificação em 2 etapas na conta Google.
2. Gere uma "Senha de app" em https://myaccount.google.com/apppasswords
3. Use essa senha (não a senha normal) em `SMTP_PASSWORD`.

### 3. Configurar o `.env`

```bash
copy .env.example .env
```
Preencha os valores que você conseguiu no passo 2. Pode deixar em branco o que
ainda não tiver — o sistema pula a fonte/alerta correspondente e avisa no log.

### 4. Rodar manualmente

```bash
python src/main.py --tenant marau --open
```

`--open` abre o dashboard no navegador ao final. `--max-dates` controla quantas
datas de ida testar por execução (default 20 — suficiente pro tier grátis da
Amadeus, que tem limite de chamadas/mês).

### 5. Agendar execução diária (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_task.ps1
```

Isso registra uma tarefa no Agendador de Tarefas do Windows rodando todo dia às
08:00. Não precisa deixar nada aberto — só o PC ligado no horário.

## Adicionar outro destino/roteiro

Copie `config/destinations/marau.yaml` para `config/destinations/<novo>.yaml`,
ajuste origem, `route_options`, janela de datas, blackout e custos. Rode com
`python src/main.py --tenant <novo>`. Comece com `status: draft` (só usa fontes
grátis) e mude pra `active` quando o roteiro estiver realmente definido, pra
ligar a conferência real via SerpApi.

## Dois modos de rodar: manual (explorando) vs. automático (roteiro definido)

- **Manual, a qualquer momento** (`scripts/run_now.ps1`, ou
  `python src/main.py --tenant marau --open`): roda na hora, não olha
  `status`. É o que você usa enquanto ainda está mexendo em filtros — origem,
  datas, rota, duração — decidindo o roteiro. Sempre executa, mesmo com
  `status: draft`.
- **Automático, de hora em hora** (`scripts/register_task.ps1`, passa
  `--scheduled`): registrado no Agendador de Tarefas do Windows, dispara
  todo hora. Só faz alguma coisa de verdade se o yaml estiver
  `status: active` — se ainda for `draft`, ele roda e sai na hora, sem gastar
  1 chamada de API sequer. Isso evita pagar Duffel/SerpApi de hora em hora
  em cima de um roteiro que ainda nem foi decidido.

Não existe um agente de IA pensando em tempo real 24h — nem o próprio
"acompanhar preço" do Google Flights funciona assim. O que roda de verdade é
esse job agendado comparando contra o histórico salvo a cada execução.

Isso é 100% local (PC precisa estar ligado na hora certa). Se no futuro você
quiser que rode independente do PC, dá pra mover esse agendamento pra nuvem
via agendamento nativo do Claude Code — mas isso é uma decisão à parte, não
mexi nisso agora.

## Limitações honestas

- Não existe uma API que cubra "todas" as companhias/agências ao mesmo tempo;
  Duffel cobre GDS+NDC+LCC, mas promoção muito pontual de agência específica
  pode escapar.
- **Amadeus self-service fechou pra devs novos em 17/07/2026** — não é mais
  possível pegar chave grátis nova; Duffel assumiu o lugar de espinha dorsal
  e é pago por uso (barato, mas não é "grátis pra sempre").
- SerpApi (Google Voos real) tem cota de 100 buscas/mês grátis — por isso só
  confere as top-N datas de roteiros `active`, não a janela inteira. Mais
  cota custa a partir de ~$25/mês.
- Alertas de e-mail/Telegram só disparam se as credenciais estiverem no `.env`.
- Sem Airbnb/hotel — hospedagem não faz parte do sistema, por decisão do
  usuário.
