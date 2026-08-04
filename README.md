# Bot de Registro de Metas — Lisboa Criadores

Bot em Python (discord.py) com 3 funções principais, iguais ao painel que você mandou:

- **📊 Registrar Meta** — abre um formulário com **NOME RP, ID RP, DIA DA LIVE, HORAS FEITAS** e depois pede o **print comprovante** (anexo de imagem) na sequência.
- **📈 Meu Progresso** — mostra quantas horas o usuário já fez no ciclo atual, meta mínima, % de progresso e quanto falta.
- **🏆 Ver Ranking** — menu com 8 opções (Ciclo Atual/Semanal × Tier 4/Tier 3/Tier 2/Tier 1), mostrando a hierarquia de horas de cada criador (🥇🥈🥉 + lista numerada).

## Estrutura dos arquivos

```
registro_metas_bot/
├── main.py            # inicia o bot e registra os comandos
├── config.py           # todas as configurações (token, cargos, canais, meta mínima...)
├── database.py         # salva e consulta os registros (SQLite, arquivo metas.db)
├── ui_components.py    # botões, formulário (modal) e menus
├── requirements.txt
└── README.md
```

## 1. Criar a aplicação no Discord

1. Acesse https://discord.com/developers/applications e crie uma aplicação.
2. Vá em **Bot** → **Reset Token** → copie o token.
3. Ainda em **Bot**, ative:
   - **Message Content Intent** (obrigatório — é como o bot lê o print comprovante enviado no chat)
   - **Server Members Intent** (obrigatório — é como o bot sabe qual é o seu Tier pelo cargo)
4. Em **OAuth2 → URL Generator**, marque `bot` e `applications.commands`, com permissões: `Send Messages`, `Embed Links`, `Attach Files`, `Manage Messages` (para apagar o print depois de salvo), `Read Message History`. Use o link gerado para convidar o bot ao seu servidor.

## 2. Configurar o projeto

1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Defina o token como variável de ambiente (recomendado):
   ```bash
   export DISCORD_TOKEN="seu_token_aqui"      # Linux/Mac
   set DISCORD_TOKEN=seu_token_aqui           # Windows (cmd)
   ```
   Ou edite diretamente `TOKEN` em `config.py`.
3. Abra `config.py` e preencha:
   - `CARGO_TIER_4_ID`, `CARGO_TIER_3_ID`, `CARGO_TIER_2_ID`, `CARGO_TIER_1_ID` — IDs dos 4 cargos de tier dos criadores.
   - `CARGO_ADMIN_IDS` — lista com os 3 cargos que podem usar `/enviar_painel` e `/resetar_ranking`.
   - `CANAL_LOG_TIER_4_ID`, `CANAL_LOG_TIER_3_ID`, `CANAL_LOG_TIER_2_ID`, `CANAL_LOG_TIER_1_ID` — um canal de log separado para cada tier (organiza os comprovantes por tier).
   - `META_MINIMA_HORAS` — meta mínima mensal (padrão: 36h).
   - `META_MINIMA_HORAS_SEMANAL` — meta mínima semanal, se quiser usar.
   - `TAMANHO_RANKING` — quantas pessoas entram no ranking no total (padrão: 200, dá pra aumentar).
   - `TAMANHO_PAGINA_RANKING` — quantas pessoas aparecem por página do ranking (padrão: 15).

## 3. Rodar o bot

```bash
python main.py
```

## 4. Publicar o painel

Dentro do canal desejado (ex: `#registro-metas`), rode o comando de barra:

```
/enviar_painel
```

Isso publica a mensagem com os 3 botões, exatamente como no exemplo que você mandou.

## Como funciona o registro (passo a passo do usuário)

1. Clica em **📊 Registrar Meta**.
2. Se ainda não tiver nenhum dos 4 cargos de tier, o bot pergunta qual tier ele é (Tier 4, 3, 2 ou 1).
3. Abre o formulário com: **NOME RP**, **ID RP**, **DIA DA LIVE**, **HORAS FEITAS** (sem nenhum texto de exemplo nos campos).
4. Ao enviar o formulário, aparece um painel pedindo pra **anexar o print comprovante** ali no chat.
5. Assim que o print é enviado, o bot baixa a imagem, salva o registro, confirma pro usuário (ephemeral, com a imagem já visível no embed) e **gera uma log automática e bem formatada no canal daquele tier** (ex: Tier 1 vai pro canal de log do Tier 1, Tier 2 pro canal do Tier 2, e assim por diante — cada tier fica organizado no seu próprio canal), com nome, ID, tier, dia, horas e a foto do comprovante, tudo junto no mesmo card.
   - A mensagem original com o print é apagada do chat público depois — mas como a imagem é baixada e reenviada pelo próprio bot antes disso, ela continua aparecendo normalmente no embed da log (isso corrige o bug de a imagem sumir).

## Ranking com muita gente (150-200 pessoas)

O **Ver Ranking** agora é paginado: mostra 15 pessoas por página (configurável em `TAMANHO_PAGINA_RANKING`), com botões **◀️ Anterior** e **Próxima ▶️** para navegar. Isso evita o problema de a mensagem estourar o limite de caracteres do Discord quando o servidor tem muitos criadores ativos — suporta até `TAMANHO_RANKING` pessoas no total (padrão: 200).

## Persistência dos dados no Railway (evitar perder dados no redeploy)

Por padrão, o sistema de arquivos de um serviço no Railway é **efêmero**: a cada redeploy, o container é recriado do zero e qualquer arquivo que não esteja num Volume é apagado — incluindo o `metas.db`. Para os dados sobreviverem aos redeploys:

1. No painel do Railway, abra o serviço do bot → aba **Volumes** → **New Volume**.
2. Defina um *mount path*, por exemplo `/data`.
3. Nas variáveis de ambiente do serviço, defina:
   ```
   DB_PATH=/data/metas.db
   ```
4. Faça o redeploy. A partir daí, o `metas.db` passa a viver dentro do Volume e continua existindo mesmo quando o container é recriado.

Se `DB_PATH` não for definido, o padrão continua sendo `metas.db` na pasta do projeto (ok para rodar localmente, mas não persiste em produção sem Volume).

## Observações importantes

- O **ranking mensal reseta sozinho automaticamente**, pois é sempre calculado com base no mês atual — não precisa apagar nada na virada do mês. O comando `/resetar_ranking` serve para forçar uma limpeza manual/antecipada, se precisar.
- Os dados ficam salvos em `metas.db` (SQLite) na mesma pasta do bot — faça backup desse arquivo periodicamente.
- Como a view do painel usa `custom_id` fixos, os botões continuam funcionando mesmo depois de reiniciar o bot (não precisa reenviar o painel).
- Quer trocar a meta mínima, os textos dos embeds ou adicionar mais campos no formulário? Tudo isso está isolado em `config.py` e `ui_components.py`, então dá pra ajustar sem mexer no resto.
