# videototicket

Skill para **Claude Code** e **Codex** (e qualquer outro assistente
compatível com a spec aberta [Agent-Skills](https://github.com/anthropics/skills))
que transforma uma gravação de tela (bug, feedback, gravação de uso) em um
ticket completo — frames do erro, transcrição da narração e repro steps —
na sua ferramenta de tickets: **Azure DevOps**, **Jira** ou **GitHub**.

Genérica: não há organização, projeto, responsável ou campo customizado
fixo — tudo é configurado por você na primeira execução, para o seu próprio
time/plataforma.

---

## 0. Compatibilidade

| Assistente | Convenção usada | Comando de instalação | Pasta (perfil do usuário) | Pasta (projeto) |
|---|---|---|---|---|
| **Claude Code** | nativa do Claude Code | `videototicket install` (`--platform claude` é o default) | `~/.claude/skills/videototicket/` | `./.claude/skills/videototicket/` |
| **Codex** (e outros compatíveis) | spec aberta [Agent-Skills](https://github.com/anthropics/skills) | `videototicket install --platform agents` | `~/.agents/skills/videototicket/` | `./.agents/skills/videototicket/` |

O conteúdo instalado é **idêntico** nos dois casos (`SKILL.md` + `scripts/` +
`config.example.json`) — só muda a pasta de destino, para bater com a
convenção de descoberta de cada assistente. Nos dois, a skill é acionada por
**linguagem natural** dentro da conversa (ex. "criar ticket a partir de
vídeo"), não por um comando de barra tipo `/videototicket`.

> Se o Codex (ou outro assistente) que você usa não descobrir a skill
> automaticamente em `.agents/skills/`, confira a documentação da versão que
> você tem instalada — o suporte à spec Agent-Skills pode variar entre
> clientes/versões.

O restante deste guia (pré-requisitos, configuração, uso diário) vale para
os dois assistentes; as únicas diferenças estão marcadas explicitamente nas
seções [2](#2-instalação-passo-a-passo) (instalação) e
[6](#6-desinstalar) (desinstalação).

---

## Índice

0. [Compatibilidade](#0-compatibilidade)
1. [Pré-requisitos](#1-pré-requisitos)
2. [Instalação passo a passo](#2-instalação-passo-a-passo)
3. [Configuração inicial (primeira execução)](#3-configuração-inicial-primeira-execução)
4. [Uso do dia a dia — passo a passo](#4-uso-do-dia-a-dia--passo-a-passo)
5. [Atualizar a skill](#5-atualizar-a-skill)
6. [Desinstalar](#6-desinstalar)
7. [Estrutura do repositório](#7-estrutura-do-repositório)
8. [Solução de problemas](#8-solução-de-problemas)
9. [Limitações conhecidas](#9-limitações-conhecidas)

---

## 1. Pré-requisitos

### 1.1. Para instalar o CLI (obrigatório)

| Requisito | Mínimo | Verificar |
|---|---|---|
| Python | 3.9+ | `python --version` |
| pip | qualquer | `pip --version` |

O instalador em si (`videototicket install`) não tem outras dependências.

### 1.2. Para a skill funcionar de verdade (scripts chamados pelo assistente)

| Requisito | Para quê | Instalar |
|---|---|---|
| `ffmpeg` + `ffprobe` no PATH | extrair frames e áudio do vídeo | Windows: `winget install --id=Gyan.FFmpeg -e` · macOS: `brew install ffmpeg` · Linux: `sudo apt install ffmpeg` |
| `faster-whisper` (Python) | transcrever a narração localmente | `pip install faster-whisper` (baixa um modelo de ~500MB na primeira transcrição — precisa de internet nessa hora) |
| `requests` (Python) | chamar a API REST do Azure DevOps/Jira | `pip install requests` |

Esses dois pacotes Python **precisam estar no mesmo interpretador Python que
o seu assistente vai usar** para rodar `python scripts/...` — não
necessariamente o mesmo ambiente onde você instalou o CLI do instalador.
Se não souber qual é, rode `pip install -e ".[full]"` dentro deste repo, que
resolve os dois de uma vez no ambiente ativo.

### 1.3. Conforme a plataforma de tickets que você for usar

Só precisa configurar a de baixo que você realmente vai usar:

- **Azure DevOps**: um Personal Access Token com escopo *Work Items: Read &
  Write* (gerado em `https://dev.azure.com/<sua-org>/_usersSettings/tokens`),
  **ou** a `az` CLI autenticada (`az login`).
- **Jira**: um API token da Atlassian, gerado em
  `https://id.atlassian.com/manage-profile/security/api-tokens`.
- **GitHub**: a `gh` CLI instalada e autenticada (`gh auth login` →
  `gh auth status` deve funcionar).

### 1.4. No seu projeto

Uma pasta para os vídeos "a processar" e outra para os "já processados".
Isso é automático: `videototicket install --project` já cria a estrutura
padrão (`videototicket/pendentes/` e `videototicket/processados/`) na
raiz do projeto — veja o Passo 2 da instalação. O caminho é configurável
depois em `config.json`, se você preferir outro nome/local.

---

## 2. Instalação passo a passo

Existem dois jeitos de instalar o pacote — escolha um. Depois de qualquer um
dos dois, os passos seguintes (registrar a skill no assistente) são iguais.

### Opção A — direto do GitHub (repositório público, sem clonar)

O repositório é público — qualquer pessoa (inclusive você, em outra máquina)
instala com um único comando, sem precisar clonar nem baixar nada
manualmente:

```bash
pip install "git+https://github.com/caioreigota/videototicket.git"
```

Com as dependências dos *scripts* (faster-whisper + requests) já incluídas:

```bash
pip install "videototicket[full] @ git+https://github.com/caioreigota/videototicket.git"
```

Ou via `pipx` (ambiente isolado, recomendado para CLIs Python):

```bash
pipx install "git+https://github.com/caioreigota/videototicket.git"
```

Quer travar numa versão/branch específica em vez do padrão do repositório
(`master`)? Acrescente `@<branch-ou-tag-ou-commit>` no final da URL, antes das
aspas:

```bash
pip install "git+https://github.com/caioreigota/videototicket.git@v0.1.0"
```

Esse método instala uma cópia fixa do pacote (não editável) — bom para quem
só quer *usar* a skill. Se você quiser editar o código depois, use a Opção B.

### Opção B — clonar/copiar localmente primeiro (para editar o código)

- **Repositório no GitHub**:
  ```bash
  git clone https://github.com/caioreigota/videototicket.git
  cd videototicket
  ```
- **Já está nesta máquina** (ex. você está lendo isto de dentro da pasta
  `videototicket/`): só entre nela num terminal —
  `cd caminho/para/videototicket`.
- **Sem git/GitHub**: copie a pasta `videototicket/` inteira por outro
  meio (pendrive, rede, zip) e `cd videototicket`.

Depois, instale em modo editável:

```bash
pip install -e .
# com as dependências dos scripts também:
pip install -e ".[full]"
# ou, em ambiente isolado:
pipx install -e .
```

### Passo 2 — registre a skill no seu assistente

Escolha o bloco do seu assistente. O restante do guia (configuração, uso
diário) é **idêntico** depois disso.

#### Claude Code

```bash
videototicket install              # perfil do usuário: ~/.claude/skills/videototicket/
videototicket install --project    # só neste projeto: ./.claude/skills/videototicket/ (+ cria pasta de vídeos)
```

`--platform claude` é o default — não precisa escrever.

#### Codex (ou outro assistente compatível com Agent-Skills)

```bash
videototicket install --platform agents              # perfil do usuário: ~/.agents/skills/videototicket/
videototicket install --platform agents --project    # só neste projeto: ./.agents/skills/videototicket/ (+ cria pasta de vídeos)
```

`agents` é o nome da plataforma porque segue a spec aberta **Agent-Skills**,
não uma convenção exclusiva do Codex — o mesmo comando serve para qualquer
outro assistente (ex. Cursor) que leia skills nesse formato.

> Diferente de skills que se invocam com `/nome-da-skill`, esta aqui é
> acionada por linguagem natural em ambos os assistentes — peça "criar
> ticket a partir de vídeo" (ou equivalente) na conversa, não um comando de
> barra.

**Com `--project`, o instalador também cria a pasta de vídeos**, pronta pra
usar, na raiz do projeto atual:

```
<seu-projeto>/
  videototicket/
    pendentes/       ← coloque os vídeos a processar aqui
    processados/     ← destino automático depois que o ticket é criado
```

Rodar `install --project` de novo não apaga nem mexe no que já estiver
dentro dessas pastas — só cria o que ainda não existir.

### Passo 3 — confirme que instalou certo

**Claude Code:**

```bash
# Windows (PowerShell):
Get-ChildItem "$env:USERPROFILE\.claude\skills\videototicket" -Recurse

# macOS/Linux:
find ~/.claude/skills/videototicket -type f
```

**Codex / Agent-Skills (instalado com `--platform agents`):**

```bash
# Windows (PowerShell):
Get-ChildItem "$env:USERPROFILE\.agents\skills\videototicket" -Recurse

# macOS/Linux:
find ~/.agents/skills/videototicket -type f
```

Se você instalou com `--project`, troque `$env:USERPROFILE`/`~` pelo
caminho do projeto (`./.claude/skills/...` ou `./.agents/skills/...`).

Você deve ver `SKILL.md`, `config.example.json`, `requirements.txt` e a
pasta `scripts/`. Se não aparecer nada, revise o Passo 2 — provavelmente o
`videototicket` do PATH não é o do ambiente onde você rodou `pip install`
(veja [Solução de problemas](#8-solução-de-problemas)).

Pronto — a instalação acabou aqui. A configuração (próxima seção) acontece
dentro da conversa com o assistente, não por linha de comando.

---

## 3. Configuração inicial (primeira execução)

Isso acontece **uma vez**, dentro do assistente (Claude Code, Codex ou
equivalente), não no terminal.

1. Abra o assistente (Claude Code ou Codex) no projeto onde você quer usar a skill.
2. Peça algo como **"criar ticket a partir de vídeo"** ou **"processar os
   vídeos pendentes"**.
3. Como ainda não existe `config.json` ao lado do `SKILL.md` instalado, o
   assistente entra automaticamente no modo de setup guiado e vai
   perguntar, em ordem:

   | Pergunta | O que ele quer saber |
   |---|---|
   | Plataforma | `azure-devops`, `jira` ou `github` |
   | Dados da plataforma | org/projeto (Azure DevOps), site/projeto/e-mail (Jira), ou `dono/repo` (GitHub) |
   | Método de autenticação | PAT ou `az` CLI (Azure DevOps); API token (Jira); `gh` CLI (GitHub) — **nunca cole o token no chat**, o assistente só confirma que você exportou a variável de ambiente |
   | Vínculo obrigatório a item pai? | sim/não — a maioria dos times responde "não" |
   | Defaults opcionais | responsável, labels/tags, tipo de ticket, idioma da narração (`pt`, `en`, `auto`, etc.) |

   Pastas de vídeo **não são perguntadas** — usam o padrão fixo
   `videototicket/pendentes` e `videototicket/processados` (já criado se
   você instalou com `--project`; senão, o assistente cria na hora). Só
   entram na conversa se você pedir explicitamente para usar outro
   caminho — nesse caso ele ajusta `folders.pending`/`folders.processed`.

4. No final, o assistente salva `config.json` (copiado de
   `config.example.json` e preenchido com suas respostas) e mostra um
   resumo para você conferir antes de seguir.

**Prefere configurar na mão, sem o wizard por chat?** Copie
`config.example.json` para `config.json` na pasta onde a skill foi
instalada e edite os campos diretamente — é só um JSON, os nomes dos campos
batem exatamente com a tabela acima. Segredos (`AZURE_DEVOPS_PAT`,
`JIRA_API_TOKEN`) continuam indo só em variável de ambiente, nunca no
arquivo.

Depois de configurado uma vez, esse passo não se repete — só se você quiser
mudar algo (edite `config.json` direto, não precisa refazer o wizard do
zero).

---

## 4. Uso do dia a dia — passo a passo

1. **Grave** um vídeo (`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`) mostrando o
   bug/feedback — com ou sem narração falada.
2. **Coloque** o arquivo em `videototicket/pendentes/` na raiz do seu
   projeto (ou na pasta que você configurou em `folders.pending`).
3. **Peça** ao assistente para processar (ex. "processa os vídeos
   pendentes" ou "cria o ticket desse vídeo").
4. O assistente, para cada vídeo, **um de cada vez**:
   - extrai frames (1/segundo se o vídeo tiver ≤2min, ou por detecção de
     cena se for mais longo);
   - analisa os frames pra identificar tela, ação do usuário e mensagem de
     erro;
   - transcreve a narração, se houver;
   - (opcional, só se você ativou vínculo obrigatório) busca um item pai
     candidato e pergunta se houver ambiguidade;
   - monta um **rascunho** do ticket (título, descrição, repro steps,
     anexos) e **mostra pra você antes de criar qualquer coisa**.
5. **Revise o rascunho.** Peça ajustes se precisar — o assistente reapresenta
   até você aprovar.
6. **Aprove.** Só depois da sua aprovação explícita o ticket é criado de
   verdade na plataforma configurada.
7. O assistente imprime o **ID e a URL** do ticket criado e move o vídeo da
   pasta de pendentes para a de processados.
8. **No GitHub**, como a API não permite anexar arquivos automaticamente, o
   assistente cria a issue, comenta com a lista de arquivos e avisa que você
   precisa arrastá-los manualmente para a issue no navegador.
9. Ao final de um lote, o assistente resume: quantos vídeos processou, os
   tickets criados, e quaisquer falhas ou pendências de aprovação.

---

## 5. Atualizar a skill

Se você (ou alguém) alterou o `SKILL.md`/scripts neste repositório e quer
atualizar a versão instalada:

```bash
videototicket install            # mesma combinação de flags que você usou na instalação
```

Rodar `install` de novo **sobrescreve só os arquivos da skill**
(`SKILL.md`, `scripts/`, `config.example.json`, `requirements.txt`) — o
`config.json` que você já configurou **não é tocado**, porque ele nunca fez
parte do payload instalado.

---

## 6. Desinstalar

```bash
# Claude Code:
videototicket uninstall                              # perfil do usuário
videototicket uninstall --project                    # só o projeto atual

# Codex / Agent-Skills:
videototicket uninstall --platform agents             # perfil do usuário
videototicket uninstall --platform agents --project   # só o projeto atual
```

Isso remove a pasta inteira da skill instalada (incluindo o `config.json`,
se você quiser reinstalar do zero depois). Use a mesma combinação de flags
(`--platform`/`--project`) que você usou na instalação, senão o comando vai
procurar em outro lugar.

---

## 7. Estrutura do repositório

```
videototicket/
  pyproject.toml                    empacotamento do instalador (hatchling)
  src/videototicket/
    cli.py                          `videototicket install|uninstall`
    installer.py                    resolve destino por plataforma e copia o payload
    payload/                        ISTO é o que vira .claude/skills/videototicket/ (ou .agents/skills/videototicket/ no Codex)
      SKILL.md                      instruções que o assistente segue
      config.example.json           template de configuração
      requirements.txt              deps dos scripts (faster-whisper, requests)
      scripts/
        ffmpeg_utils.py
        extract_frames.py           extração de frames (fps=1 ou scene-detection)
        transcribe_audio.py         transcrição local com faster-whisper
        create_ticket.py            dispatcher: cria o ticket na plataforma configurada
        list_backlog_items.py       dispatcher: busca item pai (Epic/PBI/Feature) opcional
        backends/
          common.py                 config loader compartilhado
          azure_devops.py           REST API do Azure Boards (PAT ou az CLI)
          jira.py                   REST API do Jira Cloud (API token)
          github.py                 gh CLI (issues)
```

---

## 8. Solução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| `videototicket: command not found` após instalar | o diretório de scripts do Python/pipx não está no PATH | reabra o terminal; ou rode `python -m videototicket.cli install` direto |
| `ffmpeg não encontrado no PATH` | ffmpeg não instalado ou terminal não reiniciado após instalar | instale via winget/brew/apt (seção 1.2) e abra um terminal novo |
| Transcrição muito lenta na primeira vez | faster-whisper está baixando o modelo (~500MB) | normal, só acontece uma vez; garanta internet disponível |
| `ModuleNotFoundError: faster_whisper` ou `requests` ao rodar um script | esses pacotes foram instalados num Python diferente do que o assistente chama | rode `pip install faster-whisper requests` no mesmo interpretador que aparece quando você digita `python` no terminal que o assistente usa |
| Erro `TF237082` do Azure DevOps | anexo de vídeo passou de 60MB | não deveria acontecer — o backend Azure DevOps já recomprime vídeos automaticamente; se persistir, avise que é um bug |
| Jira reclama de campo de hierarquia ao criar com `parent` | projeto Jira "company-managed" usa Epic Link em vez de `parent` direto | defina `jira.epic_link_field` (ex. `"customfield_10014"`) em `config.json` |
| GitHub: anexos não aparecem na issue | limitação da API do GitHub, não é um bug | anexe manualmente arrastando os arquivos listados no comentário da issue |
| `config.json não encontrado` mesmo após configurar | você rodou `videototicket install` de novo com `--project` numa pasta diferente, ou trocou de `--platform` | confirme em qual pasta o `config.json` foi salvo (veja o Passo 3 da instalação) e mantenha o mesmo `--project`/`--platform` sempre |

---

## 9. Limitações conhecidas

- **GitHub**: a API pública não permite anexar arquivos a uma issue — a
  skill cria a issue e lista os arquivos (frames/vídeo) num comentário para
  anexação manual.
- **Jira**: o limite de tamanho de anexo varia por instância; a compressão
  automática de vídeos grandes só está implementada para o Azure DevOps
  (limite fixo de 60 MB documentado pela Microsoft).
- Vinculação a item pai (Epic/PBI/Feature) é opcional por padrão
  (`require_parent_link: false` em config.json); ative se seu time exige
  todo bug vinculado a um item de backlog.
- Ticket é criado via REST API + token do usuário (ou `gh` CLI no GitHub),
  não pelos MCPs oficiais das plataformas — nenhum deles faz upload de
  anexo, que é o valor central desta skill.
