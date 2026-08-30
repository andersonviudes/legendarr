# legendarr — ícone e paleta

Marca: **Caption Stack** — uma tela com duas linhas de legenda e dois pontos.
Acento: **latão `#d9b98a`** sobre grafite `#0f1011`.

---

## 1. Arquivos

| Arquivo | Uso |
|---|---|
| `legendarr-icon.svg` | ícone em latão, transparente — header, sidebar, 24–48px |
| `legendarr-icon-mono.svg` | usa `currentColor` — herda a cor do contexto (hover, ativo, disabled) |
| `legendarr-icon-onlight.svg` | versão grafite para fundo claro / README |
| `legendarr-icon-small.svg` | simplificado, sem os pontos — obrigatório em ≤ 24px |
| `legendarr-tile.svg` | tile com fundo grafite e cantos arredondados |
| `favicon.ico` | 16 + 32 + 48 embutidos |
| `favicon-16.png` `favicon-32.png` `favicon-48.png` | PNGs individuais |
| `apple-touch-icon-180.png` | iOS / PWA |
| `legendarr-512.png` `legendarr-1024.png` | Docker Hub, Unraid CA, GitHub social preview, README |

### Instalação no `index.html`

```html
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/svg+xml" href="/icon/legendarr-icon.svg">
<link rel="apple-touch-icon" href="/icon/apple-touch-icon-180.png">
<meta name="theme-color" content="#0f1011">
```

### Regras de uso

- Espaço livre em volta: no mínimo 12% da largura do ícone.
- Nunca esticar, girar, inclinar ou aplicar sombra/gradiente.
- Abaixo de 24px use `legendarr-icon-small.svg` — os dois pontos empastam.
- Sobre foto ou cor: use o tile, não o ícone solto.
- Wordmark em minúsculas: `legendarr`. Nunca "LegendArr" ou "Legendarr" no produto.

---

## 2. Paleta — tema escuro (padrão)

### Superfícies (3 degraus, do fundo para a frente)

| Token | Hex | Onde |
|---|---|---|
| `--bg` | `#0f1011` | fundo da página |
| `--surface` | `#16171a` | cards, sidebar, header, modais |
| `--surface-hover` | `#1c1e22` | hover de linha e de card |
| `--border` | `#26282c` | bordas, divisores, contorno de input |

### Texto

| Token | Hex | Onde |
|---|---|---|
| `--text` | `#f0ece6` | títulos, números grandes, item de menu ativo |
| `--text-muted` | `#b8b2aa` | corpo, labels |
| `--text-dim` | `#857e75` | metadados, timestamps, hints |

### Acento e estados

| Token | Hex | Onde |
|---|---|---|
| `--accent` | `#d9b98a` | marca, indicador do item ativo, botão primário, foco |
| `--accent-press` | `#c9a672` | hover/active do botão primário |
| `--accent-soft` | `rgba(217,185,138,0.12)` | fundo de badge, faixa do item ativo |
| `--success` | `#7fae8a` | legenda encontrada, sync ok |
| `--warning` | `#d9b98a` | fila, pendente |
| `--danger` | `#c97a6d` | falha de provider, erro |
| `--info` | `#8aa2b8` | tradução em andamento |

### Três decisões que fazem a diferença

1. **Ouro é escasso.** Só marca, estado ativo, botão primário e anel de foco. Títulos de página ("Dashboard", "Providers", "Live Activity") em `--text`, não em dourado — hoje eles competem com a navegação.
2. **Item ativo = ponto + texto claro**, não texto dourado. Um marcador de 8px ou uma faixa de 2px em `--accent`, com o label em `--text`.
3. **Estados não são dourados.** Se badge, erro e menu ativo forem todos âmbar, nada é destaque. Use as cores funcionais dessaturadas acima.

---

## 3. Paleta — tema claro

Mesma marca, mesma estrutura de tokens: só os valores mudam. O latão precisa escurecer no claro (`#d9b98a` sobre branco tem contraste baixo demais) — use `--accent` para superfícies preenchidas e `--accent-ink` quando o âmbar for texto ou ícone.

### Superfícies

| Token | Hex | Onde |
|---|---|---|
| `--bg` | `#faf8f5` | fundo da página — branco quente, não #fff puro |
| `--surface` | `#ffffff` | cards, sidebar, header, modais |
| `--surface-hover` | `#f2eee8` | hover de linha e de card |
| `--border` | `#e2dcd3` | bordas, divisores, contorno de input |

### Texto

| Token | Hex | Onde |
|---|---|---|
| `--text` | `#16171a` | títulos, números grandes, item de menu ativo |
| `--text-muted` | `#4f4a44` | corpo, labels |
| `--text-dim` | `#807a72` | metadados, timestamps, hints |

### Acento e estados

| Token | Hex | Onde |
|---|---|---|
| `--accent` | `#b8873f` | botão primário, indicador ativo, anel de foco |
| `--accent-ink` | `#8a6224` | âmbar como texto ou ícone (AA sobre branco) |
| `--accent-press` | `#9c6f2c` | hover/active do botão primário |
| `--accent-soft` | `rgba(184,135,63,0.10)` | fundo de badge, faixa do item ativo |
| `--success` | `#3f7a52` | legenda encontrada, sync ok |
| `--warning` | `#8a6224` | fila, pendente |
| `--danger` | `#a8483a` | falha de provider, erro |
| `--info` | `#3f6480` | tradução em andamento |

### Cuidados no claro

- Sombra em vez de borda pesada nos cards: `0 1px 2px rgba(22,23,26,0.06)` + borda `--border`.
- O ícone vira `legendarr-icon-onlight.svg` (grafite) ou latão escuro `#8a6224` — nunca `#d9b98a` sobre branco.
- Sem branco puro no fundo da página: `#faf8f5` mantém o parentesco quente com o latão.

---

## 4. Prompt para aplicar no projeto

Cole isto num agente de código (Claude Code, Cursor, Copilot) na raiz do repositório:

```text
Contexto: este é o legendarr, um app web para baixar e traduzir legendas,
integrado a Sonarr e Radarr. Vamos padronizar o tema de cores em DOIS temas —
escuro (padrão) e claro — usando o mesmo conjunto de tokens. Hoje o acento âmbar
(#e3b27a e variações) está espalhado e usado também como cor de texto, o que
deixa a interface plana, e não existe tema claro.

Tarefa: refatorar as cores para tokens semânticos, criar os dois temas e aplicar
as regras abaixo. Não mude layout, espaçamento, tipografia, componentes ou
comportamento — só cor.

1. Descubra o sistema de estilo em uso (Tailwind config, CSS variables,
   styled-components, MUI theme) e defina os tokens NELE, na convenção que o
   projeto já usa. Não introduza uma segunda forma de tematizar.

   token          escuro (padrão)          claro
   bg             #0f1011                  #faf8f5
   surface        #16171a                  #ffffff
   surface-hover  #1c1e22                  #f2eee8
   border         #26282c                  #e2dcd3
   text           #f0ece6                  #16171a
   text-muted     #b8b2aa                  #4f4a44
   text-dim       #857e75                  #807a72
   accent         #d9b98a                  #b8873f
   accent-ink     #d9b98a                  #8a6224
   accent-press   #c9a672                  #9c6f2c
   accent-soft    rgba(217,185,138,0.12)   rgba(184,135,63,0.10)
   success        #7fae8a                  #3f7a52
   warning        #d9b98a                  #8a6224
   danger         #c97a6d                  #a8483a
   info           #8aa2b8                  #3f6480

   Use accent para superfícies preenchidas (botão, indicador) e accent-ink
   quando o âmbar for texto ou ícone — no claro os dois divergem.

2. Implemente a troca de tema: escuro é o padrão, tema claro sob
   [data-theme="light"] no <html> (ou o mecanismo que o projeto já tiver).
   Respeite prefers-color-scheme na primeira visita, persista a escolha em
   localStorage e adicione um toggle discreto no header. Sem flash de tema
   errado no carregamento.

3. Substitua TODO hex, rgb() ou cor nomeada hardcoded nos componentes pelo token
   equivalente. Liste ao final qualquer cor que não mapeou para um token.

4. Aplique estas regras:
   - Fundo da página = bg. Cards, sidebar, header e modais = surface com borda
     border (1px). Os cards do dashboard hoje quase desaparecem no fundo:
     garanta o degrau de contraste entre bg e surface.
   - Títulos de seção e página ("Dashboard", "Providers", "Live Activity") e
     números grandes de métrica = text. NÃO dourado.
   - Item de navegação ativo: label em text + indicador em accent (ponto de 8px
     ou barra de 2px à esquerda) + fundo accent-soft. Item inativo: text-muted;
     hover: text + surface-hover.
   - Botão primário: fundo accent, texto #14100b; hover accent-press. Botão
     secundário: fundo transparente, borda border, texto text.
   - Anel de foco visível em todo elemento interativo: 2px accent com 2px de
     offset. Nunca remover outline sem substituto.
   - Badges e status usam as cores funcionais (success/danger/info/warning) com
     fundo na mesma cor a 12% de opacidade e texto na cor cheia. Badges de tipo
     de evento (ex. acquire_bulk) são neutros: fundo surface-hover, texto
     text-dim.
   - Legendas/metadados e timestamps = text-dim.
   - No tema claro: cards ganham sombra 0 1px 2px rgba(22,23,26,0.06) além da
     borda; nada de branco puro no fundo da página.

5. Ícone: use os arquivos de /icon (já no repositório). No header, troque o
   ícone atual por legendarr-icon.svg em 32px; abaixo de 24px use
   legendarr-icon-small.svg. Registre favicon.ico, o SVG e o
   apple-touch-icon-180.png no index.html, com <meta name="theme-color"
   content="#0f1011">. No tema claro use legendarr-icon-onlight.svg (ou o mono
   em #8a6224) — nunca #d9b98a sobre branco. Wordmark sempre em minúsculas:
   legendarr.

6. Verifique contraste AA NOS DOIS TEMAS: text sobre surface, text-muted sobre
   surface, accent-ink sobre surface e accent sobre bg. Corrija o que ficar
   abaixo de 4.5:1 (3:1 para texto ≥ 24px) e me diga o que mudou.

Entregue um diff enxuto e um resumo dos arquivos tocados.
```
