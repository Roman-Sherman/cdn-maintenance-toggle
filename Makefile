# Copyright The Linux Foundation and each contributor to LFX.
# SPDX-License-Identifier: MIT

.PHONY: all clean test

all:
	@echo 'no default: supported targets are "requirements.txt", ".venv", "clean" and "sync"' >&2
all: requirements.txt

clean:
	rm -Rf requirements.txt __pycache__ .venv .ruff_cache megalinter-reports

lint:
	docker pull oxsecurity/megalinter-python:v7
	docker run --rm --platform linux/amd64 -v '$(CURDIR):/tmp/lint:rw' oxsecurity/megalinter-python:v7

test:
	@echo "No tests to run ... would you like to 'make lint'?" >&2

requirements.txt: requirements.in
	cat .license-header > requirements.txt
	uv pip compile requirements.in >> requirements.txt

.venv:
	uv venv .venv

sync: .venv requirements.txt
	uv pip sync requirements.txt

fmt:
	uv tool -q run black *.py
	uv tool -q run isort *.py
