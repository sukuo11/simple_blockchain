import hashlib
import json
import time
from uuid import uuid4

from flask import Flask, jsonify, request

"""
和示例代码的不同
1. 交易信息的格式 (sender, recipient, amount, nonce) 加入了nonce
2. 新建了创世区块
3. 交易信息的验证 将交易信息的签名加入到了验证中
4. 工作量证明的验证 加入了交易信息
    sender = txn['sender']
    nonce = txn['nonce']
    txn_string += f"{sender}{nonce}"
    guess = f'{last_proof}{proof}{txn_string}'.encode()
5. 新挖区块的时候可以自由选择交易信息
6. 增加了mempool
7. 增加了coinbase交易, 挖矿奖励

"""

class Blockchain():
    def __init__(self):
        self.nodes = set()
        self.genesis_block = block = {
    'index': 1,
    'timestamp': time.time(),
    'transactions': [],
    'proof': 0,
    'previous_hash': "0"
}
        self.chain = []
        self.current_transactions = []
        self.chain.append(self.genesis_block)

    def new_block(self, proof, previous_hash, transactions):
        """
        生成新块
        :param proof: <int> The proof given by the Proof of Work algorithm
        :param previous_hash: (Optional) <str> Hash of previous Block
        :param transactions: <list> 交易信息
        :return: <dict> New Block
        """
        block = {
            'index': len(self.chain)+1,
            'timestamp': time.time(),
            'transactions': transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }


        for txn in transactions:
            self.current_transactions.remove(txn)
        self.chain.append(block)
        return block

    def new_transaction(self,txn_dict):
        """
        {
         "sender": "my address",
         "recipient": "someone else's address",
         "amount": 5,
         "nonce": 123456789
        }
        :param sender:
        :param recipient:
        :param amount:
        :param nonce:
        :return:
        """
        self.current_transactions.append({
            'sender': txn_dict['sender'],
            'recipient': txn_dict['recipient'],
            'amount': txn_dict['amount'],
            'nonce': txn_dict['nonce']
        })
        # 返回加入到区块的索引
        return self.last_block['index'] + 1

    def current_transactions(self):
        return self.current_transactions

    @staticmethod
    def hash_block(block):
        """
        生成块的 SHA-256 hash值
        :param block: <dict> Block
        :return: <str>
        """

        # We must make sure that the Dictionary is Ordered, or we'll have inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def valid_proof(last_proof, proof, transactions):
        """
        验证证明: 是否hash(last_proof, proof)以4个0开头?
        :param last_proof: <int> Previous Proof
        :param proof: <int> Current Proof
        :param transactions: <list> 交易信息
        :return: <bool> True if correct, False if not.
        """
        txn_string = ""
        for txn in transactions:
            sender = txn['sender']
            nonce = txn['nonce']
            txn_string += f"{sender}{nonce}"
        guess = f'{last_proof}{proof}{txn_string}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def proof_of_work(self, last_proof, transactions):
        """
        简单的工作量证明:
         - 查找一个 p' 使得 hash(pp') 以4个0开头
         - p 是上一个块的证明,  p' 是当前的证明
        :param last_proof: <int>
        :return: <int>
        """

        proof = 0
        while self.valid_proof(last_proof, proof, transactions) is False:
            proof += 1

        return proof

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid
        :param chain: <list> A blockchain
        :return: <bool> True if valid, False if not
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            # Check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check that the Proof of Work and Transactions are correct
            if not self.valid_proof(last_block['proof'], block['proof'], block['transactions']):
                return False

            last_block = block
            current_index += 1

        return True




# Instantiate our Node
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain
blockchain = Blockchain()




@app.route('/mine', methods=['POST'])
def mine():
    values = request.get_json()
    if not values:
        # if values.get('transactions') is None:
        #     return 'Missing values', 400

        required = ['sender', 'recipient', 'amount', 'nonce']
        for txn in values.get('transactions'):
            if not all(k in txn for k in required):
                return 'Missing values', 400

    transactions = values.get('transactions')

    # We run the proof of work algorithm to get the next proof...
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof, transactions)

    # 给工作量证明的节点提供奖励.
    coinbase_dict = {'sender':"coinbase",
        'recipient':node_identifier,
        'amount':1,
        'nonce':0}
    # 发送者为 "0" 表明是新挖出的币
    blockchain.new_transaction(coinbase_dict)
    previous_hash = blockchain.hash_block(blockchain.last_block)
    # Forge the new Block by adding it to the chain
    transactions.append(coinbase_dict)
    block = blockchain.new_block(proof, previous_hash, transactions)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # Check that the required fields are in the POST'ed data
    required = ['sender', 'recipient', 'amount', 'nonce']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new Transaction
    index = blockchain.new_transaction({'sender':values['sender'], 'recipient':values['recipient'], 'amount':values['amount'], 'nonce':values['nonce']})

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201



@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/mempool', methods=['GET'])
def mempool():
    response = {
        'transactions': blockchain.current_transactions,
    }
    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1234)
