import os
import socket
import sys
import threading

PORTA = 11550
N_ARGS = {"CUMP": 1, "PEGA": 1, "LIST": 0, "TERM": 0}

def analisar(linha):
    partes = linha.decode("ascii", "replace").split(" ")
    if len(partes) < 2 or not partes[0].isdigit() or partes[1] not in N_ARGS:
        return None
    seq, cmd, args = partes[0], partes[1], partes[2:]
    if N_ARGS[cmd] == 0:
        return None if args else (seq, cmd, None)
    return (seq, cmd, args[0]) if args and args[0] else None  # "PEGA a b", só considera "a"


def pedidos(conn):
    while bloco := conn.recv(4096):
        yield from filter(None, bloco.replace(b"\r", b"").split(b"\n"))


def ler_arquivo(pasta, nome):
    if os.path.basename(nome) != nome:  # bloqueia ../ e caminhos
        return None
    try:
        with open(os.path.join(pasta, nome), "rb") as f:
            return f.read()
    except OSError:  # inexistente, diretório, sem permissão
        return None


def atender(conn, pasta, usuarios):
    pronto = False
    with conn:
        for linha in pedidos(conn):
            msg = analisar(linha)
            seq, cmd, arg = msg or (linha.split(b" ")[0].decode("ascii", "replace"), None, None)

            def enviar(corpo, dados=b""):
                conn.sendall(f"{seq} {corpo}".encode() + dados)

            if not pronto:  # Esperando: só CUMP de usuário válido; qualquer outra coisa fecha
                pronto = cmd == "CUMP" and arg in usuarios
                enviar("OK" if pronto else "NOK")
                if not pronto:
                    return
            elif cmd == "LIST":
                try:
                    nomes = sorted(n for n in os.listdir(pasta) if os.path.isfile(os.path.join(pasta, n)))
                    enviar(f"ARQS {len(nomes)} {','.join(nomes)}")
                except OSError:
                    enviar("NOK")
            elif cmd == "PEGA" and (dados := ler_arquivo(pasta, arg)) is not None:
                enviar(f"ARQ {len(dados)} ", dados)
            elif cmd == "TERM":
                enviar("OK")
                return
            else:  # CUMP repetido, PEGA sem arquivo ou mensagem inválida: NOK sem fechar
                enviar("NOK")


def main():
    args = sys.argv[1:]
    pasta = args[0] if args else "files"
    with open(args[1] if len(args) > 1 else "users.txt", encoding="ascii") as f:
        usuarios = set(f.read().split())
    with socket.create_server(("", PORTA)) as srv:
        print(f"PTA ouvindo na porta {PORTA}, servindo '{pasta}'")
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=atender, args=(conn, pasta, usuarios), daemon=True).start()


if __name__ == "__main__":
    main()
