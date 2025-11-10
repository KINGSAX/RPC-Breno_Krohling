import argparse
import hashlib
import os
import time
import grpc
import grpcCalc_pb2 as pb
import grpcCalc_pb2_grpc as pbg
import threading
import queue

# Função para gerar o hash SHA1
def generate_sha1_hash(input_str: str) -> str:
    return hashlib.sha1(input_str.encode("utf-8")).hexdigest()

# Função para validar se o hash tem o número correto de zeros no início
def is_solution_valid(solution: str, difficulty: int) -> bool:
    required_zeros = max(1, int(difficulty))
    return generate_sha1_hash(solution).startswith("0" * required_zeros)

# Função para realizar a mineração local
def mine_solution(txid: int, client_id: int, difficulty: int, num_threads: int | None = None):
    prefix = f"{txid}:{client_id}:"
    num_threads = num_threads or max(1, (os.cpu_count() or 2))
    stop_event = threading.Event()  # Evento para controle de parada
    result_queue = queue.Queue()  # Fila para armazenar os resultados

    # Função trabalhadora para minerar com diferentes intervalos de nonce
    def mining_worker(start_nonce: int, step: int):
        nonce = start_nonce
        while not stop_event.is_set():
            current_string = prefix + str(nonce)
            if is_solution_valid(current_string, difficulty):
                result_queue.put(current_string)
                stop_event.set()  # Interrompe as outras threads quando a solução é encontrada
                return
            nonce += step

    threads = []
    for i in range(num_threads):
        thread = threading.Thread(target=mining_worker, args=(i, num_threads), daemon=True)
        thread.start()
        threads.append(thread)

    try:
        solution = result_queue.get(timeout=3600)  # Aguarda até 1 hora
    except queue.Empty:
        solution = ""

    stop_event.set()
    for t in threads:
        t.join(timeout=0.1)
    
    return solution


# Função para exibir o menu de opções
def display_menu():
    print("\n Miner", flush=True)
    print("1 - getTransactionID")
    print("2 - getChallenge")
    print("3 - getTransactionStatus")
    print("4 - getWinner")
    print("5 - getSolution")
    print("6 - Minerar")
    print("0 - Sair")


# Função principal do cliente
def run_client():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="localhost:8080", help="endereço host:port do servidor")
    parser.add_argument("--client-id", type=int, default=1, help="seu ClientID (inteiro)")
    parser.add_argument("--threads", type=int, default=0, help="threads para minerar (0 = cpu_count)")
    parser.add_argument("--pause", action="store_true", help="pausa após operações para ver a saída")
    args = parser.parse_args()

    # Configuração de keepalive para garantir a conexão estável com o servidor
    channel = grpc.insecure_channel(
        args.server,
        options=[
            ("grpc.keepalive_time_ms", 30_000),
            ("grpc.keepalive_timeout_ms", 10_000),
            ("grpc.http2.min_time_between_pings_ms", 30_000),
            ("grpc.http2.max_pings_without_data", 0),
            ("grpc.keepalive_permit_without_calls", 1),
        ],
    )
    stub = pbg.MinerAPIStub(channel)

    try:
        print(f"\n Cliente {args.client_id} ")

        while True:
            try:
                display_menu()
                choice = input(f"Cliente {args.client_id} - Escolha: ").strip()

                if choice == "0":
                    print(f"Cliente {args.client_id} - Encerrando.")
                    break

                elif choice == "1":
                    txid = stub.getTransactionID(pb.Empty(), timeout=5).id
                    print(f"Cliente {args.client_id} - TransactionID atual: {txid}")

                elif choice == "2":
                    txid = int(input("TransactionID: "))
                    challenge = stub.getChallenge(pb.TransactionID(id=txid), timeout=5)
                    diff = challenge.difficulty
                    print(f"Cliente {args.client_id} - Desafio (difficulty): {diff}")

                elif choice == "3":
                    txid = int(input("TransactionID: "))
                    status = stub.getTransactionStatus(pb.TransactionID(id=txid), timeout=5).status
                    status_message = {0: "RESOLVIDO", 1: "PENDENTE", -1: "INVÁLIDO"}.get(status, f"desconhecido({status})")
                    print(f"Cliente {args.client_id} - Status: {status_message}")

                elif choice == "4":
                    txid = int(input("TransactionID: "))
                    winner = stub.getWinner(pb.TransactionID(id=txid), timeout=5).clientID
                    if winner == -1:
                        print("TransactionID inválido.")
                    elif winner == 0:
                        print("Ainda sem vencedor.")
                    else:
                        print(f"Cliente {args.client_id} - Vencedor (ClientID): {winner}")

                elif choice == "5":
                    txid = int(input("TransactionID: "))
                    solution = stub.getSolution(pb.TransactionID(id=txid), timeout=5)
                    status_message = {0: "RESOLVIDO", 1: "PENDENTE", -1: "INVÁLIDO"}.get(solution.status, f"desconhecido({solution.status})")
                    print(f"Cliente {args.client_id} - Status: {status_message} | Diff: {solution.difficulty} | Solution: {solution.solution}")

                elif choice == "6":
                    # 1) Obter o TransactionID atual
                    txid = stub.getTransactionID(pb.Empty(), timeout=5).id
                    # 2) Obter o desafio (difficulty)
                    challenge = stub.getChallenge(pb.TransactionID(id=txid), timeout=5)
                    difficulty = challenge.difficulty
                    print(f"Cliente {args.client_id} - Minerando tx={txid} com dificuldade={difficulty} ...", flush=True)

                    # 3) Minerar localmente
                    threads = args.threads if args.threads > 0 else None
                    solution = mine_solution(txid, args.client_id, difficulty, num_threads=threads)

                    if not solution:
                        print("Falha ao minerar (tempo/threads insuficientes).")
                        continue

                    print(f"Cliente {args.client_id} - Solução local: '{solution}' | sha1={generate_sha1_hash(solution)}", flush=True)

                    # 4) Submeter a solução
                    try:
                        response = stub.submitChallenge(
                            pb.Submission(transactionID=txid, clientID=args.client_id, solution=solution),
                            timeout=5,
                        )
                        result_code = response.code
                        result_message = {1: "VÁLIDA/ACEITA", 0: "INVÁLIDA", 2: "JÁ SOLUCIONADO", -1: "ID INVÁLIDO"}.get(result_code, str(result_code))
                        print(f"Cliente {args.client_id} - Resposta do servidor: {result_message}", flush=True)
                    except grpc.RpcError as e:
                        print(f"Erro ao submeter: {e.code().name} - {e.details()}")

                else:
                    print("Opção inválida.")
                
                if args.pause:
                    input("Pressione <Enter> para continuar...")

            except ValueError:
                print("Entrada inválida. Tente novamente.")
            except grpc.RpcError as e:
                print(f"Erro RPC: {e.code().name} - {e.details()} (continuando...)")

    except KeyboardInterrupt:
        print(f"\nCliente {args.client_id} - Interrompido pelo usuário. Saindo...")


if __name__ == "__main__":
    run_client()