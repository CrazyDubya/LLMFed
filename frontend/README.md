# LLMFed Legacy Frontend

A legacy static web interface for the LLMFed API. The repository also contains the newer Vite/React application in `web-ui/`; the supported frontend and deployment path are still release work. See [../docs/STATUS.md](../docs/STATUS.md).

## Features

- Create and manage agents
- View federation status
- Control simulation engine
- Monitor system health

## Setup

1. Ensure the API server is running on port 8091
2. Open `index.html` in a web browser
3. Or serve it with a simple HTTP server:

```bash
# Python 3
python3 -m http.server 8080

# Node.js
npx http-server -p 8080

# Or use any other static file server
```

## Usage

1. **Create Agents**: Fill in the form to create new wrestling agents
2. **View Agents**: See all active agents in the federation
3. **Run Simulation**: Advance the engine by specified ticks
4. **Monitor Status**: Check API, database, and engine health

## Current limitations

This legacy UI does not document or guarantee parity with the current `/game/*` API. Use it for reference only until the supported frontend is selected. Potential UI work belongs in the consolidated backlog at [../docs/STATUS.md](../docs/STATUS.md).