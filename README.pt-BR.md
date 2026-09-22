# Hosts Editor para o Omarchy

Adiciona, bloqueia e liga/desliga entradas do `/etc/hosts` por um menu, sem abrir um editor
como root. É o
[PowerToys Hosts File Editor](https://learn.microsoft.com/windows/powertoys/hosts-file-editor)
portado para o [Omarchy](https://omarchy.org).

*[Read in English](README.md)*

```bash
omarchy-hosts                            # o menu: tudo listado, um clique para alternar
omarchy-hosts add 192.168.15.20 dev.local api.dev.local
omarchy-hosts block ads.example.com      # aponta para 0.0.0.0
omarchy-hosts toggle dev.local           # desliga por ora, sem tirar do arquivo
```

## O que o torna seguro em cima do /etc/hosts

- **Seu arquivo volta do jeito que estava.** Toda linha que você não mexeu é gravada byte a
  byte — o cabeçalho da distribuição, seus comentários, as linhas em branco, até o tab duplo
  com que alguém alinhou o `::1`. Só as linhas que mudaram são reescritas.
- **Desligar uma entrada não a apaga.** Ela vira comentário, então ligá-la de volta é um
  clique e a sua anotação de por que ela existe continua ali.
- **Toda gravação deixa um backup** ao lado do arquivo
  (`/etc/hosts.bak-20260922-113000`), e o `omarchy-hosts backups` lista todos.
- **Ele se recusa a gravar um hosts sem entrada de loopback.** Apagar o
  `127.0.0.1 localhost` quebra a resolução de nomes da própria máquina de um jeito que
  ninguém liga a uma edição do hosts feita uma hora antes — então esse erro específico não
  está disponível.
- **IPs e nomes são validados** antes de qualquer gravação, e um nome que já aponta para outro
  lugar é recusado em vez de ser silenciosamente sombreado.

## ⚠️ Nomes .local não resolvem, e a culpa não é desta ferramenta

O Arch — e portanto o Omarchy — traz o `/etc/nsswitch.conf` com
`mdns_minimal [NOTFOUND=return]` **antes** de `files`. Qualquer coisa terminada em `.local` é
respondida por mDNS e nunca chega ao `/etc/hosts`: a entrada está lá, parece certa, e o nome
continua sem resolver.

O `omarchy-hosts` avisa no momento em que você digita um nome assim. Use `.test`, `.internal`
ou um domínio que seja realmente seu.

## Comandos

```
omarchy-hosts                        o menu
omarchy-hosts list                   todas as entradas, com as desligadas marcadas
omarchy-hosts add <ip> <nome…>       --note "por que isso existe"
omarchy-hosts block <domínio…>       aponta para 0.0.0.0
omarchy-hosts remove <nome|ip>       tira a linha
omarchy-hosts toggle <nome|ip>       liga ↔ desliga
omarchy-hosts enable|disable <nome>  quando você já sabe para que lado quer
omarchy-hosts edit                   o seu $EDITOR, com validação antes de instalar
omarchy-hosts backups                as cópias deixadas pelas gravações anteriores
```

Gravar exige root: `sudo` quando você está no terminal e o diálogo de senha do próprio
ambiente (`pkexec`) quando você veio do menu. A variável `$OMARCHY_HOSTS_ELEVATOR` substitui
os dois, para `doas` ou para uma configuração sem senha.

## Instalação

### Arch / Omarchy

```bash
sudo pacman -U omarchy-hosts-editor-*-any.pkg.tar.zst   # dos Releases
```

Um atalho, no `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + ALT + H", "Arquivo hosts", "omarchy-hosts")
```

### Em outras distros

`pipx install git+https://github.com/andrebbruno/omarchy-hosts-editor`. Nada aqui é específico
do Hyprland, exceto o menu, que cai para o `gum` e depois para um prompt simples.

## Desenvolvimento

```bash
python -m pytest tests -q     # 45 testes, nenhum deles precisa de root
```

O `ohosts/hostsfile.py` separa o arquivo em entradas e *todo o resto*, e guarda o texto
original de cada linha até que algo nela mude — é isso que o teste de ida e volta byte a byte
fixa. A suíte inteira roda contra um arquivo temporário com `$OMARCHY_HOSTS_ELEVATOR` valendo
`env`, então o caminho privilegiado é exercitado sem nunca ser privilegiado.

## Licença

MIT © Andre Bruno
