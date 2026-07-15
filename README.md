# legendarr

Companheiro self-hosted para **Radarr** e **Sonarr** que traduz legendas automaticamente —
na linha do [Bazarr](https://www.bazarr.media/), mas com perfis de idioma mais flexíveis e
capaz de traduzir qualquer legenda, inclusive as embutidas (embedded) dentro do vídeo.

## Arquitetura

O projeto é um monorepo Python com dois módulos, empacotados em um único build (uma imagem
Docker, um `uv.lock`):

- **`modules/backend`** (`legendarr_backend`) — domínio: integração com Radarr/Sonarr,
  descoberta e extração de legendas, tradução, perfis de idioma e o agendador que roda tudo
  isso periodicamente.
- **`modules/web`** (`legendarr_web`) — interface web (FastAPI + Jinja2/HTMX), consome os
  serviços do backend diretamente e inicia o agendador do backend no próprio processo.

Dentro de cada módulo, o código é organizado por **Screaming Architecture + Vertical Slice
Architecture**: as pastas de topo levam o nome das capacidades de negócio
(`media_providers`, `subtitle_discovery`, `subtitle_translation`, `language_profiles`, ...),
não de camadas técnicas. Cada slice contém o que precisa para funcionar de ponta a ponta;
código realmente compartilhado (config, banco de dados, logging, templates) fica em
`shared_kernel/`.

## Rodando localmente

Pré-requisitos: [uv](https://docs.astral.sh/uv/) e Python 3.12+.

```bash
make install   # uv sync --all-packages
make run       # sobe a web (e o agendador do backend) em http://localhost:8000
```

Configuração via variáveis de ambiente (veja `.env.example`), prefixo `LEGENDARR_`:
URLs e API keys do Radarr/Sonarr, intervalo de sincronização, diretório de dados, etc.

## Testes e lint

```bash
make test
make lint
```

## Docker

Um único `Dockerfile` builda os dois módulos e roda a web (que sobe o agendador do backend
internamente):

```bash
make docker-build
docker run -p 8000:8000 -v ./data:/config legendarr:local
```

## CI

O workflow em `.github/workflows/ci.yml` roda lint + testes em toda PR e push para `main`,
e builda/publica a imagem Docker em `ghcr.io` a cada push na `main`.
