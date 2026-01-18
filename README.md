# AI-WhiteMind

## Flags

### `--abort-after N`

Aborta a execução após `N` segundos (onde `N >= 1`). O timer inicia após o preflight e após a confirmação Y/N.
Quando o timer expira, a execução é interrompida imediatamente, é registrado um evento no JSONL e é gerado
o `task.result.json` com `status="aborted"` e `reason="timeout_abort"`.

#### Exemplo

```bash
python app/main.py --abort-after 30
```
