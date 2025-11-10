import grpc
import grpcCalc_pb2
import grpcCalc_pb2_grpc
import pybreaker

# Configura o circuit breaker
circuit_breaker = pybreaker.CircuitBreaker(fail_max=2, reset_timeout=2)

# Função para rodar o cliente
@circuit_breaker
def start_client():
    # Estabelece a conexão com o servidor gRPC
    channel = grpc.insecure_channel('localhost:8080')
    stub = grpcCalc_pb2_grpc.apiStub(channel)

    while True:
        print("\n Calculadora")
        print("1 - Soma")
        print("2 - Subtração")
        print("3 - Multiplicação")
        print("4 - Divisão")
        print("0 - Sair")
        
        option = input("Escolha a operação: ").strip()

        # Encerra o programa se o usuário escolher a opção 0
        if option == '0':
            print("Finalizando cliente.")
            break

        try:
            # Captura os valores de entrada
            num1 = float(input("Digite o primeiro número: "))
            num2 = float(input("Digite o segundo número: "))
        except ValueError:
            print("Entrada inválida. Tente novamente.")
            continue

        try:
            # Realiza a operação selecionada
            if option == '1':
                response = stub.add(grpcCalc_pb2.args(numOne=num1, numTwo=num2))
            elif option == '2':
                response = stub.sub(grpcCalc_pb2.args(numOne=num1, numTwo=num2))
            elif option == '3':
                response = stub.mul(grpcCalc_pb2.args(numOne=num1, numTwo=num2))
            elif option == '4':
                response = stub.div(grpcCalc_pb2.args(numOne=num1, numTwo=num2))
            else:
                print("Opção inválida. Por favor, escolha novamente.")
                continue

            print(f"Resultado: {response.num}")
        
        # Trato de erros no RPC
        except grpc.RpcError as rpc_error:
            print(f"Erro RPC: {rpc_error.code().name} - {rpc_error.details()}")
        
        # Caso o circuit breaker tenha sido acionado
        except pybreaker.CircuitBreakerError:
            print("Circuit breaker ativado, tente novamente mais tarde.")

# Executa o cliente se o script for o principal
if __name__ == '__main__':
    start_client()
