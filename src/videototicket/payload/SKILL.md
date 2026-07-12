---
name: videototicket
description: Varre uma pasta de vídeos pendentes, e para cada vídeo extrai frames (ffmpeg), transcreve narração (faster-whisper), opcionalmente identifica um item pai (Epic/PBI/Feature), monta um ticket com repro steps e anexos, pede aprovação do usuário, cria o ticket na plataforma configurada (Azure DevOps, Jira ou GitHub) e move o vídeo para a pasta de processados. Use quando o usuário pedir para "criar bug/ticket a partir de vídeo", "processar os vídeos pendentes" ou equivalente. Na primeira execução em um projeto (sem config.json), conduz um setup guiado antes de processar qualquer vídeo.
---

# Fluxo: vídeo → ticket

Processa vídeos de uma pasta "pendentes", um de cada vez, criando um ticket
(Bug/Issue) na plataforma configurada para cada um, com aprovação do usuário
antes de salvar. É genérica: qualquer pessoa pode instalar esta skill (via
`videototicket install`, global ou `--project`, em Claude Code ou em
qualquer assistente compatível com Agent-Skills) e configurá-la para o
próprio time/plataforma — nada aqui é específico de uma empresa.

**Caminhos de script:** todos os comandos abaixo (`scripts/extract_frames.py`
etc.) são relativos ao diretório **desta própria skill** — ou seja, à pasta
onde este `SKILL.md` está (ex. `~/.claude/skills/videototicket/` ou
`<projeto>/.claude/skills/videototicket/`, dependendo de como foi
instalada), **não** à raiz do projeto do usuário. Resolva o caminho absoluto
a partir de onde você carregou este arquivo antes de rodar qualquer comando;
`config.json`, `config.example.json` e `scripts/` vivem todos ali, lado a
lado com este `SKILL.md`. Já a pasta de vídeos pendentes/processados
(`folders.pending`/`folders.processed` do passo 0) é relativa à raiz do
**projeto do usuário** (cwd da sessão) — são duas raízes diferentes, não
confunda uma com a outra.

## 0. Configuração inicial (só na primeira vez)

Antes de processar qualquer vídeo, verifique se `config.json` existe na raiz
desta skill (ao lado deste `SKILL.md`). **Se não existir**, é a primeira
execução neste projeto — conduza o usuário por um setup guiado antes de
seguir:

1. Copie `config.example.json` para `config.json`.
2. Pergunte ao usuário qual plataforma de ticket ele usa: **Azure DevOps**,
   **Jira** ou **GitHub**. Defina `platform` no config de acordo
   (`"azure-devops"`, `"jira"` ou `"github"`).
3. Dependendo da plataforma, pergunte os dados necessários e preencha o bloco
   correspondente:
   - **Azure DevOps**: organização (URL completa, ex.
     `https://dev.azure.com/minhaorg`), nome do projeto, time (para resolver
     a sprint atual — opcional, default `"<projeto> Team"`). Pergunte o
     método de autenticação:
     - `"pat"` (recomendado, default): peça para o usuário gerar um Personal
       Access Token com escopo "Work Items: Read & Write" em
       `https://dev.azure.com/<org>/_usersSettings/tokens` e exportá-lo como
       variável de ambiente `AZURE_DEVOPS_PAT` **antes de rodar os scripts**.
       Nunca peça para o usuário colar o token no chat — só confirme que ele
       exportou a variável.
     - `"az_cli"`: usa `az account get-access-token`, requer `az login`
       prévio (sem precisar de PAT).
   - **Jira**: URL do site (ex. `https://suaempresa.atlassian.net`), chave
     do projeto (ex. `PROJ`), e-mail do usuário. Autenticação é sempre via
     API token: peça para gerar um em
     `https://id.atlassian.com/manage-profile/security/api-tokens` e
     exportar como `JIRA_API_TOKEN`. Se o projeto Jira for "company-managed"
     com campo Epic Link (em vez de `parent` direto), pergunte o id do campo
     customizado (`epic_link_field`, ex. `"customfield_10014"`) — se o
     usuário não souber, deixe `null` e ajuste depois se a criação falhar
     reclamando de campo de hierarquia.
   - **GitHub**: repositório no formato `dono/repo`. Autenticação é via `gh`
     CLI já logada (`gh auth login`) — não precisa de token em config nem em
     variável de ambiente. Confirme que `gh auth status` funciona.
4. Pergunte se **todo ticket precisa ser filho de um item pai** (Epic/PBI/
   Feature) já existente — nem todo time trabalha assim. Se sim, defina
   `"require_parent_link": true`; senão, deixe `false` (default) e o campo
   `parent` fica opcional por ticket.
5. Pergunte defaults opcionais (pode pular e deixar vazio): responsável
   padrão (`defaults.assignee`), labels/tags padrão (`defaults.labels` para
   Jira/GitHub, `defaults.tags` para Azure DevOps), tipo de ticket
   (`ticket_type`, default `"Bug"`), idioma da narração para a transcrição
   (`language`, default `"pt"`; use `"auto"` para detecção automática).
6. As pastas de vídeo já têm um local **fixo por padrão**:
   `videototicket/pendentes` (a processar) e `videototicket/processados`
   (depois de criar o ticket), relativas à raiz do projeto — normalmente já
   criadas por `videototicket install --project`. Se não existirem ainda,
   crie-as agora. Só pergunte ao usuário se ele quiser usar outro
   caminho — nesse caso, ajuste `folders.pending`/`folders.processed` em
   `config.json` e crie as pastas informadas.
7. Salve `config.json` e mostre um resumo do que foi configurado para
   confirmação antes de seguir para o processamento de vídeos.

**Nunca escreva tokens/senhas dentro de `config.json`** — eles vivem só em
variáveis de ambiente que o próprio usuário exporta. `config.json` guarda
apenas dados não sensíveis (org, projeto, repo, e-mail, preferências).

## Pré-requisitos técnicos

- `ffmpeg`/`ffprobe` instalados e no PATH (`winget install --id=Gyan.FFmpeg -e`
  no Windows, ou via `apt`/`brew` em outros SOs).
- Pacote Python `faster-whisper` instalado (`pip install faster-whisper`) —
  na primeira transcrição baixa o modelo (~500MB, precisa de internet).
- Pacote Python `requests` instalado (`pip install requests`) — usado pelos
  backends Azure DevOps e Jira.
- Conforme a plataforma escolhida: `AZURE_DEVOPS_PAT` exportado (ou `az`
  CLI autenticado), ou `JIRA_API_TOKEN` exportado, ou `gh` CLI autenticada.
- As pastas de vídeo (`videototicket/pendentes` e `videototicket/processados`
  por padrão, ou o que estiver em `folders.pending`/`folders.processed`)
  existem na raiz do projeto — `install --project` já cria as padrão.

## Loop principal

Liste os vídeos em `folders.pending` (extensões `.mp4`, `.mov`, `.avi`,
`.mkv`, `.webm`), ordene (ex.: por nome/data) e processe **um vídeo por
vez**, repetindo os passos 1–8 abaixo para cada um. Nunca crie o ticket de um
vídeo sem aprovação explícita do usuário para aquele vídeo especificamente —
não dá para aprovar em lote silenciosamente.

Use um diretório de trabalho temporário por vídeo (no scratchpad da sessão)
para os frames e áudio extraídos.

### 1. Extrair frames

```
python "scripts/extract_frames.py" "<video>" "<pasta_frames_temp>"
```

Regra já embutida no script: `duração <= 120s` → 1 frame/segundo;
`duração > 120s` → detecção de cena. O script imprime um JSON com a lista de
frames e o timestamp (em segundos) de cada um.

### 2. Analisar os frames

Use a ferramenta de leitura de imagens para abrir os frames gerados e
identificar:
- **Tela/módulo** onde o problema ocorre.
- **Ação do usuário** (sequência de cliques/navegação) até o erro aparecer.
- **Mensagem de erro** exata, se visível em algum frame.

Se houver muitos frames (vídeos longos com scene-detection), revise todos se
for viável; se o volume for muito grande, priorize cobrir o vídeo inteiro
(início, meio e principalmente o(s) frame(s) próximos ao erro) em vez de só
olhar os primeiros.

Anote quais 1–3 frames (por timestamp) melhor mostram **o momento do erro** —
só esses serão anexados ao ticket, não todos os frames extraídos.

### 3. Transcrever áudio (se houver narração)

```
python "scripts/transcribe_audio.py" "<video>" --lang <language do config>
```

Retorna `{"has_audio": false, ...}` se o vídeo não tiver trilha de áudio (pula
esta etapa) ou `{"has_audio": true, "text": "...", "segments": [...]}` com a
transcrição. Use o texto para complementar o entendimento da ação do usuário
e do erro (ex.: o usuário narrando o que estava tentando fazer).

### 4. Encontrar o item pai (só se `require_parent_link` ou o usuário pedir)

Se `config.json` tiver `"require_parent_link": true`, todo ticket criado
**precisa** ser filho de um item pai já existente na plataforma. Use o
helper para buscar candidatos por palavra-chave da tela/funcionalidade
identificada nos frames:

```
python "scripts/list_backlog_items.py" --query "<palavra-chave>"
```

Tente algumas palavras-chave (nome da tela, do módulo, da funcionalidade) até
achar candidatos razoáveis. Se houver mais de um candidato plausível, ou
nenhum resultado óbvio, **pergunte ao usuário** qual item é o pai correto —
não escolha sozinho quando houver ambiguidade. Guarde o identificador do item
escolhido (ID numérico no Azure DevOps, chave tipo `PROJ-123` no Jira, número
da issue no GitHub).

Se `require_parent_link` for `false`, esta etapa é opcional — só faça se o
usuário pedir para linkar a um item específico.

### 5. Montar o rascunho do ticket

- **Título:** `[Área] Descrição curta do erro` (ex.: `[Faturamento] Erro 500
  ao gerar boleto`).
- **Descrição:** contexto do problema, o que se esperava vs. o que
  aconteceu, citando a narração quando relevante. Este campo é sempre
  dinâmico, gerado a partir da análise do vídeo.
- **Repro steps:** lista numerada reconstruída a partir da ação do usuário
  observada nos frames/áudio.
- **Item pai:** o identificador encontrado no passo 4, se aplicável.
- **Responsável:** usa `defaults.assignee` do config se definido; só
  pergunte ao usuário se não houver default e parecer relevante atribuir
  alguém já na criação.
- **Labels/Tags:** as de `defaults.labels`/`defaults.tags` do config são
  aplicadas automaticamente; pergunte se o usuário quer adicionar mais
  alguma além dessas.
- **Custom fields (Azure DevOps/Jira, opcional):** se `defaults.custom_fields`
  tiver entradas configuradas (ex. um campo obrigatório específico do time),
  preencha com base no conteúdo do vídeo; se não conseguir inferir, pergunte
  ao usuário.
- **Severity (opcional, Azure DevOps):** sugira com base no impacto
  observado (ex.: `1 - Critical`, `2 - High`, `3 - Medium`, `4 - Low`).
- **Anexos:** os 1–3 frames do momento do erro escolhidos no passo 2, **mais
  o vídeo original** (o arquivo inteiro, ainda em `folders.pending` nesse
  momento). No Azure DevOps e Jira os anexos sobem automaticamente. **No
  GitHub isso não é possível via API** — o script cria a issue e lista os
  arquivos num comentário para o usuário arrastar manualmente depois;
  avise disso no rascunho antes de criar.

### 6. Mostrar o rascunho e pedir aprovação

Apresente o rascunho completo ao usuário (título, descrição, repro steps,
item pai se houver, responsável, labels, severity, e quais anexos serão
incluídos) e peça aprovação explícita antes de criar. Se o usuário pedir
ajustes, revise e mostre de novo até aprovar. **Não crie o ticket sem essa
aprovação.**

### 7. Criar o ticket (só após aprovação)

Escreva um JSON com os dados finais (no scratchpad) e rode:

```
python "scripts/create_ticket.py" --input "<dados.json>"
```

Formato de `dados.json`: veja o docstring de `create_ticket.py` — os campos
não usados pela plataforma escolhida são simplesmente ignorados pelo backend
correspondente.

Rode primeiro com `--dry-run` para conferir os dados e a plataforma
resolvida (sem efeito colateral), e só depois sem `--dry-run` para criar de
verdade e subir os anexos suportados. O script imprime o ID e a URL do
ticket criado — e, no caso do GitHub, a lista de anexos que precisam ser
adicionados manualmente.

Se por algum motivo o ticket já tiver sido criado sem um anexo (ex.:
esquecimento, ou vídeo grande tratado à parte), no Azure DevOps e Jira dá
para anexar depois chamando a função `attach_file` do backend
correspondente (não há script de linha de comando dedicado — peça para o
usuário confirmar antes de rodar um trecho ad-hoc, ou adicione um pequeno
script auxiliar se isso virar rotina).

### 8. Mover o vídeo processado

Após a criação bem-sucedida do ticket, mova o vídeo de `folders.pending`
para `folders.processed` (mesmo nome de arquivo). Se a criação falhar,
**não mova** o vídeo — deixe-o em `folders.pending` para nova tentativa, e
reporte o erro ao usuário antes de seguir para o próximo vídeo.

Limpe os frames/áudio temporários gerados para aquele vídeo antes de passar
para o próximo.

## Ao final

Depois de processar todos os vídeos da pasta, apresente um resumo: quantos
vídeos foram processados, os IDs/URLs dos tickets criados, quaisquer
vídeos que falharam (e por quê) ou ficaram pendentes por falta de aprovação,
e quaisquer anexos que ainda precisam ser adicionados manualmente (GitHub).

## Notas

- Credenciais (`AZURE_DEVOPS_PAT`, `JIRA_API_TOKEN`) vivem só em variáveis de
  ambiente do usuário — os scripts nunca as imprimem/logam, e `config.json`
  nunca as contém.
- **Limite de anexo do Azure DevOps: 60 MB** (erro `TF237082` acima disso).
  `create_ticket.py` (backend `azure_devops`) já trata isso automaticamente:
  qualquer vídeo maior que ~59 MB é recomprimido com ffmpeg (bitrate
  calculado para caber em ~45 MB) antes do upload, e o comentário do anexo
  registra o tamanho original e o comprimido. Anexos não-vídeo acima de
  60 MB fazem o script falhar com uma mensagem clara.
- Jira também tem um limite de anexo configurável por instância (varia por
  site); se o upload falhar por tamanho, avise o usuário — a compressão
  automática de vídeo só está implementada para o backend Azure DevOps por
  enquanto.
- GitHub não suporta upload de anexo de vídeo/imagem via API pública —
  isso é uma limitação da plataforma, não do script. Trate como fluxo
  esperado, não como bug.
- Se `ffmpeg`/`ffprobe` não forem encontrados no PATH, os scripts tentam
  localizá-los automaticamente em
  `%LOCALAPPDATA%\Microsoft\WinGet\Packages` (Windows); se ainda assim não
  encontrarem, reinicie o terminal ou reinstale com
  `winget install --id=Gyan.FFmpeg -e`.
- Se o usuário quiser reconfigurar a plataforma ou dados depois (trocar de
  time, projeto, etc.), edite `config.json` diretamente — não precisa
  refazer o setup guiado do zero, só os campos que mudaram.
