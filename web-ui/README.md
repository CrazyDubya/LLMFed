# LLMFed Web UI

This directory contains the newer React 19 + TypeScript + Vite frontend for LLMFed.

## Stack

- React and React Router
- TypeScript
- Vite
- Tailwind CSS
- TanStack Query

## Development

From this directory:

```bash
bun install
bun run dev --host 0.0.0.0
```

The Vite development server uses port `3000` by default and proxies the following backend paths to `http://localhost:8091`:

- `/game`
- `/scheduler`
- `/worlds`
- `/ws`

The backend must be running separately. See the repository [README](../README.md) for backend setup.

## Checks

```bash
bun run lint
bun run build
```

## Release status

`web-ui/` is the supported frontend candidate. `frontend/` is retained as a legacy static UI and should not receive new product work. The release deployment still needs verification: build this directory with `bun run build`, serve the generated `dist/` assets, and configure the backend API origin/proxy for the target environment. Track remaining release work in [docs/STATUS.md](../docs/STATUS.md).

Before changing API calls, verify the current backend contract in the generated FastAPI OpenAPI document rather than relying on legacy examples under `docs/`.
