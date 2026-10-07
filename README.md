<h1 align="center">
  <a href="https://github.com/henriquesebastiao/downtify" target="_blank" rel="noopener noreferrer">
    <picture>
      <img width="150"src="docs/public/logo.png" alt="Logo di Violarr" width="180">
    </picture>
  </a>
  <br>
  Violarr
</h1>

<p align="center">
  <strong>Wrapper self-hosted per usare ICVDB come indexer Prowlarr</strong>
</p>

<div align="center">

[![CI](https://img.shields.io/github/actions/workflow/status/xbit18/violarr/ci.yml?label=test
)](https://github.com/xbit18/violarr/actions/workflows/ci.yml)
[![GitHub Release](https://img.shields.io/github/v/release/xbit18/violarr)](https://github.com/xbit18/violarr/releases)
[![GitHub License](https://img.shields.io/github/license/xbit18/violarr)](/LICENSE)
[![Visitors](https://api.visitorbadge.io/api/visitors?path=xbit18%2Fviolarr&label=repository%20visits&countColor=%231182c3&style=flat)](https://github.com/xbit18/violarr)

[Documentazione](xbit18.github.io/violarr) ·
[Installazione](https://xbit18.github.io/violarr/getting-started/installation) ·
[Utilizzo](https://xbit18.github.io/violarr/configuration/webui) ·
[Changelog](https://github.com/xbit18/violarr/blob/main/CHANGELOG.md)

</div>

## Funzionalità

- Cerca film, serie TV e anime da Prowlarr.
- Configura tutto dalla WebUI in italiano o inglese.
- Preferisci i risultati italiani o crea regole personalizzate.
- Mantieni il database aggiornato automaticamente.

## Avvio rapido

```bash
docker run -d \
  --name icvdb-torznab \
  -p 8000:8000 \
  -v icvdb_torznab_data:/data \
  --restart unless-stopped \
  ghcr.io/xbit18/violarr:latest
```

Quando il servizio è pronto, apri `http://localhost:8000/` e completa la
[prima configurazione](https://xbit18.github.io/violarr/getting-started/first-setup).

## Documentazione

- [Installazione, configurazione e utilizzo](https://xbit18.github.io/violarr/)
- [Architecture](ARCHITECTURE.md)
- [Changelog](CHANGELOG.md)

## Licenza

MIT
