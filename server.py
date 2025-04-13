import threading
import socket
import random
import json


class ChatServer:
    def __init__(self, host="0.0.0.0", port=547):
        self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.tcp_server.bind((host, port))
        except Exception as e:
            print(e)
            exit(0)
        self.players = {}
        self.waiting_players = []
        self.rooms = {}
        self.tcp_server.listen(128)
        print("服务器已开启,正在等待用户连接...")
        while True:
            new_tcp_client, client_info = self.tcp_server.accept()
            print(f"新连接: {client_info}")
            threading.Thread(
                target=self.start_connection, args=(new_tcp_client,)
            ).start()

    def start_connection(self, client):
        player_id = str(random.randint(10000, 99999))
        while player_id in self.players:
            player_id = str(random.randint(10000, 99999))

        self.players[player_id] = {
            "client": client,
            "room_id": None,
            "status": "waiting",
            "player_number": None,
        }

        try:
            self.send_message(client, {"type": "connect", "player_id": player_id})

            while True:
                data = client.recv(1024).decode("utf-8")
                if not data:
                    break

                try:
                    message = json.loads(data)
                    self.handle_message(player_id, message)
                except json.JSONDecodeError:
                    print(f"无效的JSON数据: {data}")
        except Exception as e:
            print(f"连接错误: {e}")
        finally:
            self.handle_disconnect(player_id)

    def handle_message(self, player_id, message):
        message_type = message.get("type")

        if message_type == "match":
            self.match_player(player_id)

        elif message_type == "move":
            room_id = self.players[player_id]["room_id"]
            if room_id and room_id in self.rooms:
                col = message.get("col")
                row = message.get("row")
                self.handle_move(player_id, room_id, col, row)

        elif message_type == "quit":
            self.handle_quit_room(player_id)

    def match_player(self, player_id):
        if self.players[player_id]["room_id"] is not None:
            print(f"玩家 {player_id} 已经在房间中")
            return

        if player_id not in self.waiting_players:
            self.waiting_players.append(player_id)

        if len(self.waiting_players) >= 2:
            player1_id = self.waiting_players.pop(0)
            player2_id = self.waiting_players.pop(0)

            room_id = f"room_{random.randint(1000, 9999)}"
            while room_id in self.rooms:
                room_id = f"room_{random.randint(1000, 9999)}"

            self.rooms[room_id] = {
                "players": [player1_id, player2_id],
                "board": [[0] * 15 for _ in range(15)],
                "current_player": player1_id,
                "status": "playing",
            }

            self.players[player1_id]["room_id"] = room_id
            self.players[player1_id]["status"] = "playing"
            self.players[player1_id]["player_number"] = 1

            self.players[player2_id]["room_id"] = room_id
            self.players[player2_id]["status"] = "playing"
            self.players[player2_id]["player_number"] = 2

            self.send_message(
                self.players[player1_id]["client"],
                {
                    "type": "matched",
                    "room_id": room_id,
                    "player_number": 1,
                    "opponent_id": player2_id,
                },
            )

            self.send_message(
                self.players[player2_id]["client"],
                {
                    "type": "matched",
                    "room_id": room_id,
                    "player_number": 2,
                    "opponent_id": player1_id,
                },
            )

            print(f"创建房间 {room_id}: {player1_id} vs {player2_id}")

    def handle_move(self, player_id, room_id, col, row):
        room = self.rooms[room_id]

        if room["current_player"] != player_id:
            return

        if col < 0 or col >= 15 or row < 0 or row >= 15 or room["board"][col][row] != 0:
            return

        player_number = self.players[player_id]["player_number"]
        room["board"][col][row] = player_number

        opponent_id = (
            room["players"][0]
            if room["players"][1] == player_id
            else room["players"][1]
        )

        room["current_player"] = opponent_id

        move_info = {
            "type": "move",
            "player_id": player_id,
            "col": col,
            "row": row,
            "player_number": player_number,
        }

        self.send_message(self.players[player_id]["client"], move_info)
        self.send_message(self.players[opponent_id]["client"], move_info)

        winner = self.check_winner(room["board"], col, row, player_number)
        if winner:
            game_over_info = {
                "type": "game_over",
                "winner": player_id,
                "winner_number": player_number,
            }
            self.send_message(self.players[player_id]["client"], game_over_info)
            self.send_message(self.players[opponent_id]["client"], game_over_info)
            room["status"] = "finished"

            self.players[player_id]["room_id"] = None
            self.players[opponent_id]["room_id"] = None
            self.players[player_id]["status"] = "waiting"
            self.players[opponent_id]["status"] = "waiting"

    def check_winner(self, board, col, row, player_number):
        directions = [
            [(0, 1), (0, -1)],
            [(1, 0), (-1, 0)],
            [(1, 1), (-1, -1)],
            [(1, -1), (-1, 1)],
        ]

        for direction_pair in directions:
            count = 1

            for dx, dy in direction_pair:
                x, y = col, row
                while True:
                    x += dx
                    y += dy
                    if (
                        x < 0
                        or x >= 15
                        or y < 0
                        or y >= 15
                        or board[x][y] != player_number
                    ):
                        break
                    count += 1

            if count >= 5:
                return player_number

        return None

    def handle_quit_room(self, player_id):
        room_id = self.players[player_id]["room_id"]
        if not room_id or room_id not in self.rooms:
            return

        room = self.rooms[room_id]
        opponent_id = (
            room["players"][0]
            if room["players"][1] == player_id
            else room["players"][1]
        )

        if (
            opponent_id in self.players
            and self.players[opponent_id]["status"] == "playing"
        ):
            self.send_message(
                self.players[opponent_id]["client"], {"type": "opponent_quit"}
            )
            self.players[opponent_id]["room_id"] = None
            self.players[opponent_id]["status"] = "waiting"

        del self.rooms[room_id]

        self.players[player_id]["room_id"] = None
        self.players[player_id]["status"] = "waiting"

    def handle_disconnect(self, player_id):

        if player_id in self.players:

            if self.players[player_id]["room_id"]:
                self.handle_quit_room(player_id)

            if player_id in self.waiting_players:
                self.waiting_players.remove(player_id)
            del self.players[player_id]
            print(f"玩家 {player_id} 断开连接")

    def send_message(self, client, message):
        try:
            client.send(json.dumps(message).encode("utf-8"))
        except Exception as e:
            print(f"发送消息失败: {e}")


if __name__ == "__main__":
    ChatServer()
