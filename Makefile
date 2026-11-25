.PHONY: up down build logs test test-backend build-frontend dev-backend dev-frontend clean help

help:            ## list commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  make %-16s %s\n",$$1,$$2}'

.env:
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example - add your real LLM_API_KEYS, then re-run." && exit 1)

up: .env       ## build and start everything (frontend :3000, backend :8000)
	docker compose up --build -d
	@echo "Frontend: http://localhost:3000   Backend: http://localhost:8000/health"

down:          ## stop containers (the chat_data volume is kept)
	docker compose down

build:         ## build both images
	docker compose build

logs:          ## follow logs
	docker compose logs -f

test: test-backend build-frontend  ## backend tests + frontend production build

test-backend:  ## run pytest (needs: pip install -r backend/requirements-dev.txt)
	cd backend && python -m pytest -q

build-frontend: ## type-check and build the frontend
	cd frontend && npm install --no-audit --no-fund && npm run build

dev-backend:   ## run API locally with reload (no Docker)
	cd backend && DATABASE_URL=sqlite:///./local.db uvicorn app.main:create_app --factory --reload --port 8000

dev-frontend:  ## run Vite dev server on :3000
	cd frontend && npm run dev

clean:         ## stop containers AND delete the database volume
	docker compose down -v
