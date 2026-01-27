.PHONY: install update dev check uninstall clean test help

install:
	./install.sh

update:
	./install.sh --update

dev:
	./install.sh --dev

check:
	./install.sh --check

uninstall:
	./install.sh --uninstall

clean:
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

test:
	@if [ -f .venv/bin/activate ]; then \
		. .venv/bin/activate && pytest tests/ -v; \
	else \
		echo "Run 'make dev' first to set up development environment"; \
		exit 1; \
	fi

help:
	@echo "Targets:"
	@echo "  install   - Install tagiato globally (pipx)"
	@echo "  update    - Update existing installation"
	@echo "  dev       - Set up development environment"
	@echo "  check     - Check prerequisites"
	@echo "  uninstall - Remove tagiato completely"
	@echo "  clean     - Remove build artifacts (keeps .venv)"
	@echo "  test      - Run tests (requires dev mode)"
