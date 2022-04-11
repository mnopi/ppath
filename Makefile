.PHONY: build clean publish tests

SHELL := $(shell bash -c 'command -v bash')
msg := fix: first
export msg


build:
	@python3.10 -m build --wheel -o $$(mktemp -d)
	@rm -rf build dist

clean:
	@rm -rf build dist

publish: tests build clean
	@git add .
	@git commit --quiet -a -m "$${msg:-auto}" || true
	@git push --quiet

tests:
	@pytest

