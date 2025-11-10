import hashlib
import random
import threading
import time
from concurrent import futures
import grpc

import grpcCalc_pb2 as pb
import grpcCalc_pb2_grpc as pbg


# -------------------- Tabela de transações (memória) --------------------
class TxTable:
    def __init__(self):
        self.lock = threading.Lock()
        self.current_id = 0
        self.table = {}
        self._new_tx(initial=True)

    def _new_tx(self, initial: bool = False):
        difficulty = random.randint(1, 20)
        with self.lock:
            if not initial:
                self.current_id += 1
            self.table[self.current_id] = {
                "id": self.current_id,
                "difficulty": difficulty,
                "solution": "",
                "winner": -1,
            }

    def get_tx(self, txid: int):
        with self.lock:
            return self.table.get(txid)

    def get_current_id(self) -> int:
        need_new = False
        with self.lock:
            cur = self.table[self.current_id]
            if cur["winner"] != -1:
                need_new = True
            cid = self.current_id
        if need_new:
            self._new_tx()
            with self.lock:
                cid = self.current_id
        return cid

    def resolve(self, txid: int, solution: str, client_id: int) -> int:
        need_new = False
        with self.lock:
            tx = self.table.get(txid)
            if tx is None:
                return -1
            if tx["winner"] != -1:
                return 2
            tx["solution"] = solution
            tx["winner"] = client_id
            need_new = True
        if need_new:
            self._new_tx()
        return 1


TXS = TxTable()


# -------------------- Regra de validação --------------------
def valid_solution(solution: str, difficulty: int) -> bool:
    required = max(1, min(int(difficulty), 20))
    h = hashlib.sha1(solution.encode("utf-8")).hexdigest()
    return h.startswith("0" * required)


# -------------------- Implementação das RPCs --------------------
class MinerServicer(pbg.MinerAPIServicer):
    def getTransactionID(self, request, context):
        resp = pb.TransactionID(id=TXS.get_current_id())
        return resp

    def getChallenge(self, request, context):
        tx = TXS.get_tx(request.id)
        diff = -1 if tx is None else tx["difficulty"]
        return pb.Challenge(difficulty=diff)

    def getTransactionStatus(self, request, context):
        tx = TXS.get_tx(request.id)
        status = -1 if tx is None else (0 if tx["winner"] != -1 else 1)
        return pb.Status(status=status)

    def submitChallenge(self, request, context):
        tx = TXS.get_tx(request.transactionID)
        if tx is None:
            return pb.SubmitReply(code=-1)
        if tx["winner"] != -1:
            return pb.SubmitReply(code=2)

        if valid_solution(request.solution, tx["difficulty"]):
            code = TXS.resolve(request.transactionID, request.solution, request.clientID)
            return pb.SubmitReply(code=code)

        return pb.SubmitReply(code=0)

    def getWinner(self, request, context):
        tx = TXS.get_tx(request.id)
        cid = -1 if tx is None else (0 if tx["winner"] == -1 else tx["winner"])
        return pb.WinnerReply(clientID=cid)

    def getSolution(self, request, context):
        tx = TXS.get_tx(request.id)
        if tx is None:
            return pb.SolutionReply(status=-1, solution="", difficulty=-1)

        status = 0 if tx["winner"] != -1 else 1
        solution = tx["solution"] if tx["winner"] != -1 else ""
        diff = tx["difficulty"]

        return pb.SolutionReply(status=status, solution=solution, difficulty=diff)


# -------------------- Bootstrap do servidor --------------------
def serve(host: str = "0.0.0.0:8080", max_workers: int = 10):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    pbg.add_MinerAPIServicer_to_server(MinerServicer(), server)
    server.add_insecure_port(host)
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=None)


if __name__ == "__main__":
    serve()
