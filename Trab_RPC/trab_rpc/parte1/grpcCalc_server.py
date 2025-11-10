import grpc
from concurrent import futures
import grpcCalc_pb2
import grpcCalc_pb2_grpc

# Implementação do serviço de calculadora
class CalculatorService(grpcCalc_pb2_grpc.apiServicer):
    def add(self, request, context):
        resultado = request.numOne + request.numTwo
        return grpcCalc_pb2.result(num=resultado)

    def sub(self, request, context):
        resultado = request.numOne - request.numTwo
        return grpcCalc_pb2.result(num=resultado)

    def mul(self, request, context):
        resultado = request.numOne * request.numTwo
        return grpcCalc_pb2.result(num=resultado)

    def div(self, request, context):
        if request.numTwo == 0:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Erro: Divisão por zero")
            return grpcCalc_pb2.result()
        resultado = request.numOne / request.numTwo
        return grpcCalc_pb2.result(num=resultado)

# Função para iniciar o servidor gRPC
def start_server():
    # Cria o servidor gRPC com um pool de threads
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    grpcCalc_pb2_grpc.add_apiServicer_to_server(CalculatorService(), server)
    
    # Define a porta de escuta
    server.add_insecure_port('[::]:8080')
    
    # Inicia o servidor
    server.start()
    print("Servidor gRPC em execução na porta 8080...")
    
    # Aguarda até que o servidor seja interrompido
    server.wait_for_termination()

# Executa a função de inicialização do servidor se o script for o principal
if __name__ == '__main__':
    start_server()
