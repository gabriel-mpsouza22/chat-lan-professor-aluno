# ◈ LAN Chat — Sistema de Chat para Sala de Aula

Sistema leve de chat em rede local (LAN) para professores e alunos, com interface gráfica, descoberta automática de servidor e persistência de histórico por sessão.

---

## Requisitos

- Python 3.8 ou superior — [python.org](https://python.org)
- Windows 10/11
- **Sem dependências externas** — usa apenas a biblioteca padrão do Python (`tkinter`, `socket`, `json`, etc.)

---

## Como usar

### 👨‍🏫 Professor (servidor)

1. Execute o servidor:
   ```
   python server.py
   ```
2. Clique em **▶ Iniciar Servidor**
3. O servidor começa a transmitir um sinal na rede LAN automaticamente — os alunos o detectarão sozinhos

### 🎓 Aluno (cliente)

1. Execute o cliente:
   ```
   python client.py
   ```
2. Digite seu nome na tela de entrada
3. Clique em **🔍 Buscar e Conectar**
4. O cliente encontrará o servidor automaticamente

---

## Funcionalidades

### O professor pode
- ✦ Enviar mensagens de texto para todos
- ✦ Enviar links clicáveis (abre o navegador nos PCs dos alunos)
- ✦ Enviar arquivos (até 50 MB) para todos os alunos
- ✦ Ver quem está conectado em tempo real
- ✦ Iniciar e parar o servidor com 1 clique

### Os alunos recebem
- ✦ Mensagens de texto
- ✦ Links clicáveis com 1 clique
- ✦ Arquivos com caixa de diálogo para salvar
- ✦ Histórico completo ao entrar (mesmo que tenham entrado depois)

### Persistência de histórico
- Se o aluno 5 entrar depois do professor mandar um link, o aluno 5 ainda vê o link — o histórico é reproduzido automaticamente.
- Quando o professor fecha o servidor, **tudo é apagado** (histórico do servidor + telas dos clientes) para que a próxima aula comece sem resíduos.

### Descoberta automática
- O servidor transmite via UDP broadcast a cada 2 segundos
- O cliente escuta por até 8 segundos e se conecta sozinho
- Funciona em qualquer sub-rede comum (ex: `192.168.x.x`)

---

## Rede — Firewall e Portas

| Protocolo | Porta | Uso |
|-----------|-------|-----|
| TCP | 54321 | Comunicação professor ↔ alunos |
| UDP | 54322 | Descoberta automática (broadcast) |

Se o Windows pedir permissão de firewall ao rodar, clique em **"Permitir acesso"** para ambas as portas.

Para liberar manualmente via PowerShell (executar como Administrador):

```powershell
netsh advfirewall firewall add rule name="LAN Chat TCP" protocol=TCP dir=in localport=54321 action=allow
netsh advfirewall firewall add rule name="LAN Chat UDP" protocol=UDP dir=in localport=54322 action=allow
```

---

## Dicas

- Professor e alunos devem estar na **mesma rede Wi-Fi ou cabo**
- Funciona **sem internet** — apenas rede local
- Para criar atalhos: clique com botão direito no `.py` → *Criar atalho* → renomeie para `LAN Chat Servidor` ou `LAN Chat Aluno`
- Testado com até ~30 alunos simultâneos

---

## Arquitetura

```
server.py  →  TCP listener (aceita clientes) + UDP broadcaster
client.py  →  UDP listener (descobre servidor) + TCP client
Protocolo  →  JSON com length-prefix (4 bytes big-endian)
Histórico  →  mantido em memória no servidor, reproduzido
               para novos clientes via replay automático
```
