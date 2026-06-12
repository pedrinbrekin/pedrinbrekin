# GitHub Stats — pedrinbrekin

Três cartões SVG animados para o perfil, gerados localmente a partir da API do GitHub.

```
github-stats/
├── gen_stats.py            # gerador (roda local)
├── templates/              # SVGs com placeholders {{ ... }}
│   ├── overview.svg
│   ├── languages.svg
│   └── activity.svg
└── generated/              # SVGs prontos (criados ao rodar o script)
```

## Como gerar

1. Crie um **Personal Access Token** (clássico) em GitHub → Settings → Developer settings →
   Tokens (classic), com os escopos: `repo`, `read:user`, `read:org`.
2. Rode na pasta `github-stats/`:

   **PowerShell**
   ```powershell
   $env:GITHUB_TOKEN="ghp_xxx"
   python gen_stats.py
   ```
   **CMD**
   ```cmd
   set GITHUB_TOKEN=ghp_xxx
   python gen_stats.py
   ```

Os SVGs preenchidos aparecem em `github-stats/generated/`.

## Como publicar no perfil

1. No repositório especial `pedrinbrekin/pedrinbrekin`, suba a pasta `generated/`.
2. No `README.md` do perfil, cole:

```html
<div align="center">
  <img src="https://raw.githubusercontent.com/pedrinbrekin/pedrinbrekin/main/generated/overview.svg" width="450" alt="Overview" />
  <img src="https://raw.githubusercontent.com/pedrinbrekin/pedrinbrekin/main/generated/languages.svg" width="450" alt="Languages" />
</div>
<div align="center">
  <img src="https://raw.githubusercontent.com/pedrinbrekin/pedrinbrekin/main/generated/activity.svg" width="450" alt="Activity" />
</div>
```

> Troque `main` pelo nome do seu branch padrão se for diferente.

## Notas de compatibilidade (GitHub)

- **Fontes:** o GitHub bloqueia o download de fontes externas dentro do SVG, então os cartões
  usam uma pilha de fontes monoespaçadas do sistema (`ui-monospace, Cascadia Code, JetBrains
  Mono, SF Mono, Menlo, Consolas, DejaVu Sans Mono`). Isso garante uma monoespaçada limpa em
  Windows, macOS e Linux. Para uma fonte **idêntica em todos os aparelhos**, dá pra embutir um
  `.woff2` em base64 no `<style>` — me mande o arquivo da fonte que eu embuto.
- **Animações:** funcionam via CSS dentro do SVG (rodam a cada carregamento). Sem JavaScript,
  sem emojis — só ícones desenhados em SVG, que renderizam igual em qualquer lugar.
- **Cache:** o GitHub faz cache das imagens pelo proxy (Camo). Depois de atualizar os SVGs,
  pode levar alguns minutos para o perfil refletir; um hard-refresh ajuda.
- **Automação (opcional):** dá pra rodar `gen_stats.py` por GitHub Actions em agenda (ex.: diário)
  guardando o token em *repository secrets*. Posso montar o workflow se quiser.
