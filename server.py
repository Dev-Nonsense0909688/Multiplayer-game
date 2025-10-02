import asyncio
import json
import os
from websockets.server import serve
import websockets

HOST = '0.0.0.0'  # Required for Render.com (binds to all interfaces)
PORT = int(os.environ.get('PORT', 12345))  # Render sets PORT env var

class TicTacToeServer:
    def __init__(self):
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        self.players = {}  # WebSocket: player_symbol ('X' or 'O')
        self.spectators = set()  # Set of spectator WebSockets
        self.current_player = 'X'
        self.game_over = False
        self.winner = None
        print(f"Server initializing on {HOST}:{PORT}")

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

    async def broadcast(self, data, exclude=None):
        message = json.dumps(data) + '\n'
        disconnected = []
        for ws in list(self.players.keys()) + list(self.spectators):
            if ws == exclude:
                continue
            try:
                await ws.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(ws)
        # Clean up disconnected
        for ws in disconnected:
            if ws in self.players:
                self.players.pop(ws)
            if ws in self.spectators:
                self.spectators.discard(ws)

    async def handle_client(self, websocket, path):
        print(f"New connection from {websocket.remote_address}")
        
        # Assign player if slots available
        if len(self.players) < 2:
            player_symbol = 'X' if len(self.players) == 0 else 'O'
            self.players[websocket] = player_symbol
            await websocket.send(json.dumps({
                'type': 'assign',
                'player': player_symbol,
                'board': self.board,
                'current': self.current_player
            }))
            
            if len(self.players) == 2:
                await self.broadcast({
                    'type': 'start',
                    'message': 'Game started! X goes first.'
                })
        else:
            # Add as spectator
            self.spectators.add(websocket)
            await websocket.send(json.dumps({
                'type': 'spectator',
                'board': self.board,
                'current': self.current_player
            }))
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data['type'] == 'move' and websocket in self.players:
                        player = self.players[websocket]
                        if player == self.current_player and not self.game_over:
                            row, col = data['row'], data['col']
                            if self.is_valid_move(row, col):
                                self.board[row][col] = player
                                self.winner = self.check_winner()
                                
                                if self.winner:
                                    self.game_over = True
                                    await self.broadcast({
                                        'type': 'game_over',
                                        'winner': self.winner,
                                        'board': self.board
                                    })
                                else:
                                    self.current_player = 'O' if self.current_player == 'X' else 'X'
                                    await self.broadcast({
                                        'type': 'update',
                                        'board': self.board,
                                        'current': self.current_player
                                    })
                    elif data['type'] == 'reset' and websocket in self.players:
                        await self.reset_game()
                        await self.broadcast({
                            'type': 'reset',
                            'message': 'Game reset by player.'
                        }, exclude=websocket)
                except json.JSONDecodeError:
                    continue
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # Cleanup on disconnect
            if websocket in self.players:
                player = self.players.pop(websocket)
                print(f"Player {player} disconnected")
                await self.reset_game()
                await self.broadcast({
                    'type': 'reset',
                    'message': f'Player {player} disconnected. Game reset.'
                })
            elif websocket in self.spectators:
                self.spectators.discard(websocket)
                print("Spectator disconnected")

    async def reset_game(self):
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'
        self.game_over = False
        self.winner = None

    async def run(self):
        async with serve(self.handle_client, HOST, PORT, path="/ws"):  # /ws path for WebSocket
            print(f"WebSocket server running on ws://{HOST}:{PORT}/ws")
            await asyncio.Future()  # Run forever

if __name__ == "__main__":
    server = TicTacToeServer()
    asyncio.run(server.run())
