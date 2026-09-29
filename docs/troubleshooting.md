# Troubleshooting

The commands below use the development file `docker-compose.yml`. With the production file, add `-f docker-compose.prod.yml` after `docker compose`.

## Check logs
```bash
docker compose logs -f cms
docker compose logs -f website
```

## Restart services
```bash
docker compose restart
```

## Stop services
```bash
docker compose down
```

## Rebuild after code changes
```bash
docker compose build --no-cache cms
docker compose up -d
```

## Reporting a bug

Open an issue at https://github.com/GeiserX/Way-CMS/issues with the Way-CMS version (the image tag), single-tenant or multi-tenant mode, what you did, what you expected, and the output of `docker compose logs cms`. Remove passwords and secret keys from the logs first.
