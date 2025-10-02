import socket
import threading
import json
import time

class TicTacToeServer:
    def __init__(self, host='localhost', port=12345):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(2)
        
        self.players = {}  # client_socket: player_symbol
        self.spectators = set()
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'
        self.game_over = False
        self.winner = None
        
        print(f"Server started on {self.host}:{self.port}")
        print("Waiting for players to connect...")

    def is_valid_move(self, row, col):
        return 0 <= row < 3 and 0 <= col < 3 and self.board[row][col] == ' '

    def check_winner(self):
        # Check rows
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] != ' ':
                return self.board[i][0]
        
        # Check columns
        for i in range(3):
            if self.board[0][i] == self.board[1][i] == self.board[2][i] != ' ':
                return self.board[0][i]
        
        # Check diagonals
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != ' ':
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != ' ':
            return self.board[0][2]
        
        # Check for tie
        if all(self.board[i][j] != ' ' for i in range(3) for j in range(3)):
            return 'Tie'
        
        return None

    def broadcast(self, data):
        message = json.dumps(data) + '\n'
        for client in list(self.players.keys()) + list(self.spectators):
            try:
                client.send(message.encode())
            except:
                # Remove disconnected clients
                if client in self.players:
                    self.players.pop(client)
                if client in self.spectators:
                    self.spectators.remove(client)

    def handle_client(self, client_socket, address):
        print(f"New connection from {address}")
        
        # Assign player if slots available
        if len(self.players) < 2:
            player_symbol = 'X' if len(self.players) == 0 else 'O'
            self.players[client_socket] = player_symbol
            client_socket.send(json.dumps({
                'type': 'assign',
                'player': player_symbol,
                'board': self.board,
                'current': self.current_player
            }).encode() + b'\n')
            
            if len(self.players) == 2:
                self.broadcast({
                    'type': 'start',
                    'message': 'Game started! X goes first.'
                })
        else:
            # Add as spectator
            self.spectators.add(client_socket)
            client_socket.send(json.dumps({
                'type': 'spectator',
                'board': self.board,
                'current': self.current_player
            }).encode() + b'\n')
        
        while True:
            try:
                data = client_socket.recv(1024).decode()
                if not data:
                    break
                
                for line in data.split('\n'):
                    if not line:
                        continue
                    
                    message = json.loads(line)
                    if message['type'] == 'move' and client_socket in self.players:
                        player = self.players[client_socket]
                        if player == self.current_player and not self.game_over:
                            row, col = message['row'], message['col']
                            if self.is_valid_move(row, col):
                                self.board[row][col] = player
                                self.winner = self.check_winner()
                                
                                if self.winner:
                                    self.game_over = True
                                    self.broadcast({
                                        'type': 'game_over',
                                        'winner': self.winner,
                                        'board': self.board
                                    })
                                else:
                                    self.current_player = 'O' if self.current_player == 'X' else 'X'
                                    self.broadcast({
                                        'type': 'update',
                                        'board': self.board,
                                        'current': self.current_player
                                    })
            
            except (ConnectionResetError, json.JSONDecodeError):
                break
        
        # Remove client on disconnect
        if client_socket in self.players:
            player = self.players.pop(client_socket)
            print(f"Player {player} disconnected")
            
            # Reset game if a player disconnects
            self.reset_game()
            self.broadcast({
                'type': 'reset',
                'message': f'Player {player} disconnected. Game reset.'
            })
        elif client_socket in self.spectators:
            self.spectators.remove(client_socket)
            print("Spectator disconnected")
        
        client_socket.close()

    def reset_game(self):
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'
        self.game_over = False
        self.winner = None

    def run(self):
        try:
            while True:
                client_socket, address = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_socket, address), daemon=True).start()
        except KeyboardInterrupt:
            print("Shutting down server...")
        finally:
            self.server_socket.close()

if __name__ == "__main__":
    server = TicTacToeServer()
    server.run()
