# Video to Ticket

Transforme uma gravação de tela em um ticket pronto para revisão. A skill analisa o vídeo, seleciona os melhores frames, transcreve a narração, sugere passos para reproduzir o problema e cria o item no **Azure DevOps**, **Jira** ou **GitHub**.

Antes de criar qualquer ticket, o assistente sempre apresenta um rascunho e pede sua aprovação.

## Comece aqui

### 1. Instale os pré-requisitos

Você precisa de:

- Python 3.9 ou mais recente;
- `ffmpeg` e `ffprobe` disponíveis no PATH;
- as dependências Python da skill.

Instale o FFmpeg:

```powershell
# Windows
winget install --id Gyan.FFmpeg -e
```

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### 2. Instale o pacote

Para usar a versão publicada no GitHub:

```bash
python -m pip install "videototicket[full] @ git+https://github.com/caioreigota/videototicket.git"
```

Para desenvolver ou testar este repositório localmente:

```bash
python -m pip install -e ".[full]"
```

> Use `python -m pip` para instalar as dependências no mesmo Python que executará os scripts da skill. Ambientes isolados do `pipx` podem exigir uma configuração adicional e não são o caminho recomendado para o primeiro uso.

### 3. Registre a skill no seu assistente

Escolha apenas um dos comandos:

```bash
# Codex: instala em $CODEX_HOME/skills (por padrão, ~/.codex/skills)
videototicket install --platform codex

# Claude Code: instala em ~/.claude/skills
videototicket install --platform claude

# Clientes que adotam a convenção Agent-Skills: instala em ~/.agents/skills
videototicket install --platform agents
```

Para manter a skill somente no projeto atual, acrescente `--project`:

```bash
videototicket install --platform codex --project
```

No Codex, essa opção usa `.agents/skills/videototicket/` dentro do repositório.

Nesse modo, o instalador também cria:

```text
videototicket/
├── pendentes/      coloque os vídeos aqui
└── processados/    vídeos com ticket criado
```

### 4. Use em linguagem natural

Abra o assistente na raiz do projeto e diga, por exemplo:

> Configure o Video to Ticket para o meu projeto.

Na primeira execução, o assistente perguntará qual plataforma você usa e criará o `config.json`. Depois:

1. Coloque um vídeo em `videototicket/pendentes/`.
2. Diga: **“Crie um ticket a partir dos vídeos pendentes.”**
3. Revise o rascunho apresentado.
4. Aprove ou peça ajustes.

O ticket só será criado após sua aprovação explícita. Quando a criação terminar com sucesso, o vídeo será movido para `videototicket/processados/`.

## O que acontece com o vídeo

Para cada arquivo `.mp4`, `.mov`, `.avi`, `.mkv` ou `.webm`, a skill:

1. extrai frames com FFmpeg;
2. identifica a tela, as ações e mensagens de erro;
3. transcreve a narração localmente com `faster-whisper`;
4. procura um item pai, se essa regra estiver habilitada;
5. monta título, descrição, resultado esperado, resultado atual e passos de reprodução;
6. mostra o rascunho para aprovação;
7. cria o ticket e envia os anexos compatíveis;
8. move o vídeo somente após a criação bem-sucedida.

## Configuração e credenciais

O arquivo `config.json` fica ao lado do `SKILL.md` instalado. Ele guarda apenas preferências e dados não sensíveis, como organização, projeto, repositório, responsável e labels.

Nunca coloque tokens no `config.json` nem os envie no chat. Configure a autenticação no terminal usado para iniciar o assistente:

```powershell
# Azure DevOps — PowerShell, somente na sessão atual
$env:AZURE_DEVOPS_PAT = "seu-token"

# Jira — PowerShell, somente na sessão atual
$env:JIRA_API_TOKEN = "seu-token"
```

```bash
# Azure DevOps — macOS/Linux, somente na sessão atual
export AZURE_DEVOPS_PAT="seu-token"

# Jira — macOS/Linux, somente na sessão atual
export JIRA_API_TOKEN="seu-token"
```

Alternativas de autenticação:

- Azure DevOps: `az login` e `azure_devops.auth` igual a `az_cli`;
- GitHub: `gh auth login` e `gh auth status` funcionando.

O modelo completo está em [`config.example.json`](src/videototicket/payload/config.example.json).

## Plataformas suportadas

| Plataforma | Criação | Frames e vídeo | Autenticação |
|---|---:|---:|---|
| Azure DevOps | automática | automáticos | PAT ou Azure CLI |
| Jira Cloud | automática | automáticos, conforme limite do site | API token |
| GitHub Issues | automática | anexação manual | GitHub CLI |

O GitHub não oferece upload público de anexos por API nesse fluxo. A issue é criada com a lista dos arquivos que devem ser arrastados manualmente no navegador.

## Atualizar ou remover

Repita a mesma combinação de plataforma e escopo usada na instalação:

```bash
# Atualizar
videototicket install --platform codex

# Remover
videototicket uninstall --platform codex
```

A atualização preserva o `config.json`. A desinstalação remove toda a pasta da skill, inclusive o `config.json`.

## Solução de problemas

| Problema | Como resolver |
|---|---|
| `videototicket` não é reconhecido | Reabra o terminal ou execute `python -m videototicket.cli --help`. Confirme se o diretório de scripts do Python está no PATH. |
| O assistente não encontra a skill | Confirme a plataforma com `videototicket install --help`, reinstale com a flag correta e reinicie/abra uma nova sessão do assistente. |
| `ffmpeg` não foi encontrado | Execute `ffmpeg -version` e `ffprobe -version`; reinstale o FFmpeg e abra um terminal novo. |
| `ModuleNotFoundError` para `faster_whisper` ou `requests` | Execute `python -m pip install faster-whisper requests` no Python usado pelo assistente. |
| A primeira transcrição está lenta | O `faster-whisper` baixa o modelo na primeira execução. Mantenha a conexão com a internet e aguarde o download. |
| O token não foi encontrado | Exporte a variável no mesmo terminal que inicia o assistente. Variáveis definidas em outra janela não são compartilhadas. |
| Jira rejeitou o campo pai | Configure `jira.epic_link_field`, por exemplo `customfield_10014`, conforme o seu projeto. |
| GitHub não anexou os arquivos | É o fluxo esperado: arraste no navegador os arquivos listados no comentário da issue. |

## Para quem desenvolve a skill

```text
src/videototicket/
├── cli.py                 comandos install e uninstall
├── installer.py           resolve o destino e copia o payload
└── payload/
    ├── SKILL.md           workflow seguido pelo assistente
    ├── config.example.json
    ├── requirements.txt
    └── scripts/
        ├── extract_frames.py
        ├── transcribe_audio.py
        ├── create_ticket.py
        ├── list_backlog_items.py
        └── backends/      Azure DevOps, Jira e GitHub
```

Validação rápida antes de enviar mudanças:

```bash
python -m compileall -q src
python -m videototicket.cli --help
python src/videototicket/payload/scripts/create_ticket.py --help
```

## Limitações conhecidas

- Azure DevOps limita anexos a 60 MB; vídeos grandes são recomprimidos automaticamente antes do envio.
- O limite de anexos do Jira varia por instância e não há recompressão automática nesse backend.
- O GitHub exige anexação manual de imagens e vídeos.
- A transcrição é local, mas o modelo do `faster-whisper` precisa ser baixado na primeira utilização.
