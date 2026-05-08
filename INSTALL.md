# Install perplexity-cli

Single wheel file. Cross-platform. Requires Python ≥ 3.12.

## Quickest (recommended)

```bash
pipx install ./perplexity_cli-0.1.0-py3-none-any.whl
```

`pipx` installs into an isolated venv and exposes `perplexity-cli` on your PATH.

Don't have pipx?
```bash
# macOS
brew install pipx && pipx ensurepath
# Linux / other
python3 -m pip install --user pipx && python3 -m pipx ensurepath
```

## Alternative: uv

```bash
uv tool install ./perplexity_cli-0.1.0-py3-none-any.whl
```

## Alternative: plain pip (not recommended — pollutes global env)

```bash
python3 -m pip install ./perplexity_cli-0.1.0-py3-none-any.whl
```

## Set API key

```bash
export PERPLEXITY_API_KEY="pplx-..."
```

Add to `~/.zshrc` or `~/.bashrc` to persist.

## Verify

```bash
perplexity-cli --text ask "hello"
```

## Uninstall

```bash
pipx uninstall perplexity-cli
# or
uv tool uninstall perplexity-cli
```
