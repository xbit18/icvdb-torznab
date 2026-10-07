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
  <strong>Self-hosted wrapper to use ICVDB as a Prowlarr indexer</strong>
</p>

<div align="center">

[![CI](https://img.shields.io/github/actions/workflow/status/xbit18/violarr/ci.yml?label=test
)](https://github.com/xbit18/violarr/actions/workflows/ci.yml)
[![GitHub Release](https://img.shields.io/github/v/release/xbit18/violarr)](https://github.com/xbit18/violarr/releases)
[![GitHub License](https://img.shields.io/github/license/xbit18/violarr)](/LICENSE)
[![Visitors](https://api.visitorbadge.io/api/visitors?path=xbit18%2Fviolarr&label=repository%20visits&countColor=%231182c3&style=flat)](https://github.com/xbit18/violarr)

[Documentation](https://xbit18.github.io/violarr/en) ·
[Installation](https://xbit18.github.io/violarr/en/getting-started/installation) ·
[How to use](https://xbit18.github.io/violarr/en/configuration/webui) ·
[Changelog](https://github.com/xbit18/violarr/blob/main/CHANGELOG.md)

</div>

## Features

- Search movies, TV, and anime from Prowlarr.
- Configure everything from the WebUI in Italian or English.
- Prefer Italian results or build custom rules.
- Keep the database updated automatically.

## Quick start

```bash
docker run -d \
  --name icvdb-torznab \
  -p 8000:8000 \
  -v icvdb_torznab_data:/data \
  --restart unless-stopped \
  ghcr.io/xbit18/violarr:latest
```

When the service is ready, open `http://localhost:8000/` and complete the
[first setup](https://xbit18.github.io/violarr/en/getting-started/first-setup).

## Documentation

- [Installation, setup, and usage](https://xbit18.github.io/violarr/en/)
- [Architecture](ARCHITECTURE.md)
- [Changelog](CHANGELOG.md)

## License

MIT
