import pygame
import threading
import socket
import pathlib
import os
import copy
import sys
import json
import tkinter as tk
from tkinter import messagebox


try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 5477))
except socket.error:
    print("程序已在运行！")
    sys.exit(1)


def info(title, message):
    def show_info_in_main_thread():
        event = pygame.event.Event(
            pygame.USEREVENT,
            {"action": "show_info", "title": title, "message": message},
        )
        pygame.event.post(event)

    threading.Thread(target=show_info_in_main_thread).start()


def warning(title, message):
    def show_warning_in_main_thread():
        event = pygame.event.Event(
            pygame.USEREVENT,
            {"action": "show_warning", "title": title, "message": message},
        )

    threading.Thread(target=show_warning_in_main_thread).start()


class ConnectionServer:
    def __init__(self, host="127.0.0.1", port=547):
        self.room_id = None
        self.player_id = None
        self.player_number = None
        self.opponent_id = None
        self.is_connected = False
        self.is_matched = False
        self.tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.tcp_client.connect((host, port))
            self.is_connected = True
            threading.Thread(target=self.receive_messages, daemon=True).start()
        except ConnectionRefusedError:
            warning("连接失败", "无法连接到服务器，请确保服务器已启动。")
            self.is_connected = False
            return None

    def send_message(self, message):
        if not self.is_connected:
            return
        try:
            self.tcp_client.send(json.dumps(message).encode("utf-8"))
        except Exception as e:
            print(f"发送消息失败: {e}")
            self.is_connected = False

    def receive_messages(self):
        global game
        while self.is_connected:
            try:
                data = self.tcp_client.recv(1024).decode("utf-8")
                if not data:
                    self.is_connected = False
                    break

                message = json.loads(data)
                self.handle_message(message)
            except Exception as e:
                print(f"接收消息失败: {e}")
                self.is_connected = False
                break

    def handle_message(self, message: dict):
        global game, n
        message_type = message.get("type")

        if message_type == "connect":
            self.player_id = message.get("player_id")
            print(f"连接成功，玩家ID: {self.player_id}")

        elif message_type == "matched":
            self.room_id = message.get("room_id")
            self.player_number = message.get("player_number")
            self.opponent_id = message.get("opponent_id")
            self.is_matched = True
            game.player = 1
            info(
                "匹配成功",
                f"已匹配到对手，您是{'黑子' if self.player_number == 1 else '白子'}",
            )

        elif message_type == "move":
            player_id = message.get("player_id")
            col = message.get("col")
            row = message.get("row")
            player_number = message.get("player_number")
            if player_id != self.player_id:
                game.board[col][row] = player_number
                game.down = (col, row)
                game.player = self.player_number  # 轮到自己落子

        elif message_type == "game_over":
            # 游戏结束
            winner = message.get("winner")
            winner_number = message.get("winner_number")

            if winner == self.player_id:
                game.winner = "你赢了！"
            else:
                game.winner = "对手赢了！"

            # 重置匹配状态
            self.is_matched = False
            self.room_id = None
            self.player_number = None
            self.opponent_id = None

        elif message_type == "opponent_quit":
            # 对手退出
            info("对手退出", "对手已退出游戏")
            game.winner = "对手退出，你赢了！"
            # 重置匹配状态
            self.is_matched = False
            self.room_id = None

    def request_match(self):
        if not self.is_connected:
            warning("连接失败", "未连接到服务器，无法匹配")
            return False

        # 确保重置匹配状态，以便第二次匹配能正确处理
        self.is_matched = False
        self.room_id = None
        self.player_number = None
        self.opponent_id = None

        self.send_message({"type": "match"})
        return True

    def send_move(self, col, row):
        # 发送落子信息
        if not self.is_connected or not self.is_matched:
            return False

        self.send_message({"type": "move", "col": col, "row": row})
        return True

    def quit_room(self):
        # 退出房间
        if not self.is_connected or not self.is_matched:
            return

        self.send_message({"type": "quit"})
        self.is_matched = False
        self.room_id = None

    def close(self):
        # 关闭连接
        self.is_connected = False
        try:
            self.tcp_client.close()
        except:
            pass


# 初始化
pygame.init()
# 计算窗口的宽和格子的间距
width = pygame.display.Info().current_h * 0.8
width = int(width - (width % 15))
spacing = int(width / 15)
margins = int(spacing / 2)
# 计算按钮大小
rect_height = pygame.display.Info().current_h * 0.1
button_width = (width - 6 * margins) / 5
button_height = rect_height * 0.8
# 设置窗口标题
pygame.display.set_caption("五子棋")
# 设置窗口的大小
screen = pygame.display.set_mode((width, width + rect_height))
# 当前绝对路径
folder = pathlib.Path(__file__).parent.resolve()
# 设置最大帧数
FPS = 60
# 加载背景音乐
pygame.mixer.music.load(os.path.join(folder, "data", "bgm.mp3"))
pygame.mixer.music.play(-1)
pygame.mixer.music.set_volume(0.5)
# 设置窗口图标
icon = pygame.image.load(os.path.join(folder, "data", "icon.png"))
pygame.display.set_icon(icon)


class Button:
    def __init__(
        self, x, y, width, height, text, color, click_color, text_color
    ) -> None:
        self.text = text
        self.color = color
        self.click_color = click_color
        self.text_color = text_color
        self.rect = pygame.Rect(x, y, width, height)
        self.clicked = False

    def draw(self, screen):
        if self.clicked:
            pygame.draw.rect(screen, self.click_color, self.rect)
        else:
            pygame.draw.rect(screen, self.color, self.rect)
        font = pygame.font.Font(
            os.path.join(folder, "data", "simhei.ttf"), int(button_height / 2.5)
        )
        text_surface = font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)


def handles_event(event):
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if button.rect.collidepoint(event.pos):
            if (
                button.clicked is False
                and button_ai.clicked is False
                and button_room.clicked is False
            ):
                button.clicked = True
                game.started = True
                if game.winner != 0:
                    game.player = 1
                    game.winner = None
                    game.board = [[0] * 15 for i in range(15)]
                    game.down = (-1, -1)
        elif button_ai.rect.collidepoint(event.pos):
            if (
                button.clicked is False
                and button_ai.clicked is False
                and button_room.clicked is False
            ):
                button_ai.clicked = True
                game.started = True
                if game.winner != 0:
                    game.player = 1
                    game.winner = None
                    game.board = [[0] * 15 for i in range(15)]
                    game.down = (-1, -1)
        elif button_room.rect.collidepoint(event.pos):
            global n
            if (
                button.clicked is False
                and button_ai.clicked is False
                and button_room.clicked is False
            ):
                # 检查服务器连接状态
                if not game.server.is_connected:
                    warning("连接失败", "无法连接到服务器，请确保服务器已启动。")
                    return

                button_room.clicked = True
                game.started = True
                # 请求匹配
                if game.server.request_match():
                    info("等待", "正在等待其他玩家加入房间...")

                if game.winner != 0:
                    game.player = 1
                    game.winner = None
                    game.board = [[0] * 15 for i in range(15)]
                    game.down = (-1, -1)
        elif button_restart.rect.collidepoint(event.pos):
            if button.clicked or button_ai.clicked or button_room.clicked:
                button.clicked = False
                button_ai.clicked = False

                # 如果在在线模式，需要退出房间
                if button_room.clicked:
                    game.server.quit_room()
                    # 重置匹配状态
                    game.server.is_matched = False
                    game.server.room_id = None
                    game.server.player_number = None
                    game.server.opponent_id = None

                button_room.clicked = False
                game.started = False
                game.player = 1
                game.winner = None
                game.board = [[0] * 15 for i in range(15)]
                game.down = (-1, -1)
        elif button_quit.rect.collidepoint(event.pos):
            game.server.close()
            pygame.quit()
            sys.exit()


class Game:
    def __init__(self, server_ip="127.0.0.1", server_port=547) -> None:
        self.started = False
        self.player = 1
        self.winner = None
        self.board = [[0] * 15 for i in range(15)]
        self.down = (-1, -1)
        self.clock = pygame.time.Clock()
        self.server = ConnectionServer(server_ip, server_port)

    def start(self):
        # 绘制背景
        screen.fill("#EE9A49")
        for x in range(15):
            pygame.draw.line(
                screen,
                "#000000",
                [margins + spacing * x, margins],
                [margins + spacing * x, width - margins],
                2,
            )  # 绘制竖线
        for y in range(15):
            pygame.draw.line(
                screen,
                "#000000",
                [margins, margins + spacing * y],
                [width - margins, margins + spacing * y],
                2,
            )  # 绘制横线
        pygame.draw.circle(
            screen, "#000000", [margins + 7 * spacing, margins + 7 * spacing], 8
        )  # 天元
        pygame.draw.circle(
            screen, "#000000", [margins + 3 * spacing, margins + 3 * spacing], 6
        )  # 左上角星位
        pygame.draw.circle(
            screen, "#000000", [width - margins - 3 * spacing, margins + 3 * spacing], 6
        )  # 右上角星位
        pygame.draw.circle(
            screen, "#000000", [margins + 3 * spacing, width - margins - 3 * spacing], 6
        )  # 左下角星位
        pygame.draw.circle(
            screen,
            "#000000",
            [width - margins - 3 * spacing, width - margins - 3 * spacing],
            6,
        )  # 右下角星位
        # 绘制提示框
        if self.down != (-1, -1):
            pygame.draw.rect(
                screen,
                "red",
                [self.down[0] * spacing, self.down[1] * spacing, spacing, spacing],
                2,
            )

        # 绘制落子提示
        x, y = pygame.mouse.get_pos()
        if y <= width:
            x = round((x - margins) / spacing) * spacing + margins
            y = round((y - margins) / spacing) * spacing + margins
            pygame.draw.rect(
                screen, "#FFFFFF", [x - margins, y - margins, spacing, spacing], 2
            )

        # 绘制按钮
        button.draw(screen)
        button_ai.draw(screen)
        button_restart.draw(screen)
        button_room.draw(screen)
        button_quit.draw(screen)

        # 绘制落子
        for col in range(15):
            for row in range(15):
                if self.board[col][row] == 1:
                    pygame.draw.circle(
                        screen,
                        "#000000",
                        [col * spacing + margins, row * spacing + margins],
                        margins - 2,
                    )
                elif self.board[col][row] == 2:
                    pygame.draw.circle(
                        screen,
                        "#FFFFFF",
                        [col * spacing + margins, row * spacing + margins],
                        margins - 2,
                    )

        # 绘制赢家
        if self.winner:
            font = pygame.font.Font(
                os.path.join(folder, "data", "simhei.ttf"), margins * 3
            )
            text_surface = font.render(self.winner, True, "red")
            text_position = (
                (width - font.size(self.winner)[0]) / 2,
                (width - font.size(self.winner)[1]) / 2,
            )
            screen.blit(text_surface, text_position)
            pygame.display.update()
            button.clicked = False
            button_ai.clicked = False
            # 在线模式下也需要重置状态
            if button_room.clicked:
                button_room.clicked = False
                # 重置匹配状态
                self.server.is_matched = False
                self.server.room_id = None
                self.server.player_number = None
                self.server.opponent_id = None
            self.started = False
            self.down = (-1, -1)

    def mouse_click(self, x, y):
        global n
        if self.started:
            if y <= width:
                col = round((x - margins) / spacing)
                row = round((y - margins) / spacing)
                if button.clicked:  # 双人模式
                    if self.board[col][row] == 0:
                        self.down = (col, row)
                        self.board[col][row] = self.player
                        if self.five():
                            self.winner = (
                                "黑子赢了！" if self.player == 1 else "白子赢了！"
                            )
                        elif not self.get_valid_move():
                            self.winner = "平局！"
                        self.player = abs(self.player - 3)
                elif button_ai.clicked:  # AI模式
                    pos = (col, row)
                    if self.valid_input(pos):
                        self.board[col][row] = 1
                        if self.five() or not self.get_valid_move():
                            self.winner = "你赢了！" if self.five() else "平局！"
                        else:
                            self.player = 2
                elif button_room.clicked:  # 在线模式
                    # 检查是否轮到自己落子
                    if (
                        self.server.is_matched
                        and self.player == self.server.player_number
                    ):
                        if self.board[col][row] == 0:
                            # 发送落子信息到服务器
                            if self.server.send_move(col, row):
                                # 更新本地棋盘
                                self.down = (col, row)
                                self.board[col][row] = self.player
                                # 切换玩家（服务器会通过消息再次切换回来）
                                self.player = abs(self.player - 3)

    def ai_down(self):
        move = self.get_pos(self.board)
        self.board[move[0]][move[1]] = 2
        self.down = move
        if self.five():
            self.winner = "你赢了！" if self.five() == 1 else "AI赢了！"
        else:
            self.player = 1

    def five(self):
        # 左上，上，右上，左，右，左下，下，右下
        way = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

        for i in range(15):
            for j in range(15):
                if self.board[i][j] != 0:
                    get = self.board[i][j]

                    for w in way:
                        now = (i, j)
                        count = 1

                        while True:
                            if (now[0] + w[0] not in range(15)) or (
                                now[1] + w[1] not in range(15)
                            ):
                                break

                            now = (now[0] + w[0], now[1] + w[1])

                            if self.board[now[0]][now[1]] != get:
                                break
                            else:
                                count += 1

                                if count == 5:
                                    return get
        return False

    def valid_input(self, pos):
        if pos[0] not in range(15) or pos[1] not in range(15):
            return False
        if self.board[pos[0]][pos[1]] != 0:
            return False
        return True

    def get_valid_move(self):
        ret = []
        for i in range(15):
            for j in range(15):
                if self.board[i][j] == 0:
                    ret.append((i, j))
        return ret

    def get_charge_pos(self, board):
        way = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        ret = []

        for i in range(15):
            for j in range(15):
                if board[i][j] != 0:
                    for w in way:
                        pos = (i + w[0], j + w[1])
                        if pos[0] not in range(15) or pos[1] not in range(15):
                            continue
                        if (board[pos[0]][pos[1]] == 0) and (pos not in ret):
                            ret.append(pos)

        return ret

    def get_line_score(self, line):
        # 连五 ： 100000, 活四，双冲四，冲四活三 ： 10000, 双活三 ： 5000, 活三眠三 ： 1000
        # 眠四 ： 500, 活三 ： 200, 双活二 ： 100, 眠三 ： 50, 活二眠二 ： 10, 活二 ： 5
        # 眠二 ：3, 死四 ： -5, 死三 ： -5, 死二 ： -5

        score = 0

        # 连五
        for i in line:
            if i.find("22222") != -1:
                score += 100000
                break

        # 活四
        for i in line:
            if i.find("022220") != -1:
                score += 50000
                break

        # 双冲四
        count = 0
        for i in line:
            for size in ["022221", "122220", "20222", "22202", "22022"]:
                if i.find(size) != -1:
                    count += 1
                    break

            if count == 2:
                score += 10000
                break

        # 冲四活三
        ft = [0, 0]
        for i in line:
            if not ft[0]:
                for size in ["022221", "122220", "20222", "22202", "22022"]:
                    if i.find(size) != -1:
                        ft[0] = 1
                        break

            if not ft[1]:
                for size in ["02220", "2022", "2202"]:
                    if i.find(size) != -1:
                        ft[1] = 1
                        break

            if ft[0] and ft[1]:
                score += 10000
                break

        # 双活三
        count = 0
        for i in line:
            for size in ["02220", "2022", "2202"]:
                if i.find(size) != -1:
                    count += 1
                    break

            if count == 2:
                score += 10000
                break

        # 活三眠三
        tt = [0, 0]
        for i in line:
            if not tt[0]:
                for size in ["02220", "2022", "2202"]:
                    if i.find(size) != -1:
                        tt[0] = 1
                        break

            if not tt[1]:
                for size in [
                    "002221",
                    "122200",
                    "020221",
                    "122020",
                    "022021",
                    "120220",
                    "20022",
                    "22002",
                    "20202",
                    "1022201",
                ]:
                    if i.find(size) != -1:
                        tt[1] = 1
                    break

            if tt[0] and tt[1]:
                score += 1000
                break

        # 眠四

        # 活三
        count = 0
        for i in line:
            for size in ["02220", "2022", "2202"]:
                if i.find(size) != -1:
                    count += 1
                    break
        score += count * 200

        # 双活二
        count = 0
        for i in line:
            for size in ["002200", "02020", "2002"]:
                if i.find(size) != -1:
                    count += 1
                    break
            if count == 2:
                score += 100
                break

        # 眠三
        count = 0
        for i in line:
            for size in [
                "002221",
                "122200",
                "020221",
                "122020",
                "022021",
                "120220",
                "20022",
                "22002",
                "20202",
                "1022201",
            ]:
                if i.find(size) != -1:
                    count += 1
                    break
        score += count * 50

        # 活二眠二
        dd = [0, 0]
        for i in line:
            if not dd[0]:
                for size in ["002200", "02020", "2002"]:
                    if i.find(size) != -1:
                        dd[0] = 1
                        break

            if not dd[1]:
                for size in [
                    "000221",
                    "122000",
                    "002021",
                    "120200",
                    "020021",
                    "120020",
                    "20002",
                ]:
                    if i.find(size) != -1:
                        dd[1] = 1
                        break

            if dd[0] and dd[1]:
                score += 10
                break

        # 活二
        count = 0
        for i in line:
            for size in ["002200", "02020", "2002"]:
                if i.find(size) != -1:
                    count += 1
                    break
        score += count * 5

        # 眠二
        count = 0
        for i in line:
            for size in [
                "000221",
                "122000",
                "002021",
                "120200",
                "020021",
                "120020",
                "20002",
            ]:
                if i.find(size) != -1:
                    count += 1
                    break
        score += count * 3

        # 死四，死三，死二
        count = 0
        for i in line:
            if i.find("122221") != -1:
                count += 1
            if i.find("12221") != -1:
                count += 1
            if i.find("1221") != -1:
                count += 1
        score += count * -5

        return score

    def get_score(self, pos, board):

        ori = copy.deepcopy(board)
        ori[pos[0]][pos[1]] = 2

        # 横，竖
        h = str(ori[pos[0]])[1:-1].replace(",", "").replace(" ", "")
        s = (
            str([ori[i][pos[1]] for i in range(15)])[1:-1]
            .replace(",", "")
            .replace(" ", "")
        )

        # 左斜
        lx = (
            str(
                [
                    ori[i][i - pos[0] + pos[1]]
                    for i in range(15)
                    if (i - pos[0] + pos[1]) in range(15)
                ]
            )[1:-1]
            .replace(",", "")
            .replace(" ", "")
        )

        # 右斜
        rx = (
            str(
                [
                    ori[i][pos[0] + pos[1] - i]
                    for i in range(15)
                    if (pos[0] + pos[1] - i) in range(15)
                ]
            )[1:-1]
            .replace(",", "")
            .replace(" ", "")
        )

        return self.get_line_score([h, s, lx, rx])

    def opp_board(self, board):
        o_board = [[0] * 15 for i in range(15)]

        for i in range(15):
            for j in range(15):
                if board[i][j] != 0:
                    o_board[i][j] = 1 if board[i][j] == 2 else 2

        return o_board

    def get_pos(self, board):
        pos = self.get_charge_pos(board)

        get = (-1, -1)
        score = -float("inf")

        for p in pos:
            o_board = self.opp_board(board)
            s = self.get_score(p, board) + self.get_score(p, o_board)
            if s > score:
                get = p
                score = s

        return get


game = Game("39.107.242.163")
button = Button(
    margins,
    width,
    button_width,
    button_height,
    "双人模式",
    (153, 51, 250),
    (221, 160, 221),
    (255, 255, 255),
)
button_ai = Button(
    margins * 2 + button_width,
    width,
    button_width,
    button_height,
    "AI模式",
    (255, 127, 0),
    (255, 150, 50),
    (255, 255, 255),
)
button_room = Button(
    margins * 3 + button_width * 2,
    width,
    button_width,
    button_height,
    "在线匹配",
    (51, 51, 255),
    (0, 128, 255),
    (255, 255, 255),
)
button_restart = Button(
    margins * 4 + button_width * 3,
    width,
    button_width,
    button_height,
    "重新开始",
    (15, 173, 14),
    (15, 173, 14),
    (255, 255, 255),
)
button_quit = Button(
    margins * 5 + button_width * 4,
    width,
    button_width,
    button_height,
    "退出",
    (224, 55, 51),
    (224, 55, 51),
    (255, 255, 255),
)


while True:
    game.clock.tick(FPS)
    for event in pygame.event.get():
        if event.type == pygame.USEREVENT:
            if hasattr(event, "dict") and "action" in event.dict:
                if event.dict["action"] == "show_info":
                    root = tk.Tk()
                    root.withdraw()
                    messagebox.showinfo(event.dict["title"], event.dict["message"])
                    root.destroy()
                elif event.dict["action"] == "show_warning":
                    root = tk.Tk()
                    root.withdraw()
                    messagebox.showwarning(event.dict["title"], event.dict["message"])
                    root.destroy()
        elif event.type == pygame.QUIT:
            game.server.close()
            pygame.quit()
            sys.exit()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            x, y = pygame.mouse.get_pos()
            handles_event(event)
            game.mouse_click(x, y)
            if button_ai.clicked and game.player == 2:
                game.ai_down()

    if button_ai.clicked and game.player == 2:
        game.ai_down()

    game.start()

    pygame.display.update()
