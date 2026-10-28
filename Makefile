# Concours. Every target is a thin wrapper around scripts/*.sh so it also works without make
# (this Mac's make needs `sudo xcodebuild -license accept` or `brew install make`).
.PHONY: dev demo backend frontend data test images clean

dev:        ## start backend (8000) and frontend (3000)
	./scripts/dev.sh

demo:       ## reset workspace, fetch data, seed the three demo projects
	./scripts/demo.sh

backend:
	./scripts/dev.sh backend

frontend:
	./scripts/dev.sh frontend

data:
	backend/.venv/bin/python -I scripts/fetch_data.py

test:
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && pnpm test

clean:
	rm -rf workspace/* && mkdir -p workspace
