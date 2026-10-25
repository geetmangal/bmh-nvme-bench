.PHONY: test lint quick standard fixtures clean

test:
	python3 -m unittest discover -s tests -v

lint:
	bash -n bench.sh
	@if command -v shellcheck >/dev/null 2>&1; then shellcheck -x bench.sh; else echo "shellcheck not installed, skipped"; fi
	python3 -m py_compile report.py

quick:
	./bench.sh --profile quick --no-prompt --label "$$(hostname -s)-quick"

standard:
	./bench.sh --profile standard --no-prompt --label "$$(hostname -s)-standard"

fixtures:
	python3 tests/fixtures/gen_runs.py

clean:
	rm -rf bench-tmp tests/fixtures/run-*/summary.* tests/fixtures/run-*/blog.md __pycache__ tests/__pycache__
