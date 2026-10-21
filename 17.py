"""
لعبة التعبان - Snake Game
مكتوبة بمكتبة turtle

التحكم:
    الأسهم أو W A S D  -> تحريك التعبان
    P                  -> إيقاف مؤقت / تكملة
    Space              -> إعادة اللعب بعد الخسارة
"""

import turtle
import random
import time

# ===================== الإعدادات =====================
WIDTH = 600          # عرض الشاشة
HEIGHT = 600         # طول الشاشة
STEP = 20            # حجم الخطوة = حجم مربع التعبان
START_DELAY = 0.12   # سرعة البداية (كل ما يقل يبقى أسرع)
MIN_DELAY = 0.05     # أقصى سرعة
LIMIT_X = WIDTH // 2 - STEP // 2
LIMIT_Y = HEIGHT // 2 - STEP // 2

UP, DOWN, LEFT, RIGHT = 90, 270, 180, 0


# ===================== التعبان =====================
class Snake:
    def __init__(self):
        self.segments = []
        self.create_snake()

    def create_snake(self):
        """يعمل تعبان من 3 حتت في نص الشاشة"""
        for i in range(3):
            self.add_segment((-STEP * i, 0))
        self.head = self.segments[0]
        self.head.color("lime")
        self.can_turn = True

    def add_segment(self, position):
        seg = turtle.Turtle("square")
        seg.color("green")
        seg.penup()
        seg.goto(position)
        self.segments.append(seg)

    def extend(self):
        """يطوّل التعبان حتة لما ياكل"""
        self.add_segment(self.segments[-1].position())

    def move(self):
        # كل حتة تروح مكان اللي قدامها (من الديل للراس)
        for i in range(len(self.segments) - 1, 0, -1):
            self.segments[i].goto(self.segments[i - 1].position())
        self.head.forward(STEP)
        self.can_turn = True

    def turn(self, new_heading, opposite):
        # منع الرجوع على نفسه، ومنع لفتين في نفس الخطوة
        if self.can_turn and self.head.heading() != opposite:
            self.head.setheading(new_heading)
            self.can_turn = False

    def up(self):
        self.turn(UP, DOWN)

    def down(self):
        self.turn(DOWN, UP)

    def left(self):
        self.turn(LEFT, RIGHT)

    def right(self):
        self.turn(RIGHT, LEFT)

    def hit_wall(self):
        x, y = self.head.xcor(), self.head.ycor()
        return abs(x) > LIMIT_X or abs(y) > LIMIT_Y

    def hit_self(self):
        for seg in self.segments[1:]:
            if self.head.distance(seg) < STEP / 2:
                return True
        return False

    def occupies(self, x, y):
        """هل فيه حتة من التعبان في النقطة دي؟"""
        return any(seg.distance(x, y) < STEP / 2 for seg in self.segments)

    def reset(self):
        for seg in self.segments:
            seg.hideturtle()
        self.segments.clear()
        self.create_snake()


# ===================== الأكل =====================
class Food(turtle.Turtle):
    def __init__(self):
        super().__init__("circle")
        self.color("red")
        self.shapesize(0.8, 0.8)
        self.penup()
        self.speed(0)

    def refresh(self, snake):
        """يحط الأكل في مكان عشوائي مش فوق التعبان"""
        cells_x = LIMIT_X // STEP
        cells_y = LIMIT_Y // STEP
        while True:
            x = random.randint(-cells_x, cells_x) * STEP
            y = random.randint(-cells_y, cells_y) * STEP
            if not snake.occupies(x, y):
                self.goto(x, y)
                return


# ===================== لوحة السكور =====================
class Scoreboard(turtle.Turtle):
    def __init__(self):
        super().__init__()
        self.hideturtle()
        self.penup()
        self.color("white")
        self.score = 0
        self.high_score = 0
        self.show()

    def show(self):
        self.clear()
        self.goto(0, HEIGHT // 2 - 40)
        self.write(f"Score: {self.score}    High Score: {self.high_score}",
                   align="center", font=("Arial", 16, "bold"))

    def add_point(self):
        self.score += 1
        self.high_score = max(self.high_score, self.score)
        self.show()

    def message(self, text, sub=""):
        self.goto(0, 0)
        self.write(text, align="center", font=("Arial", 28, "bold"))
        if sub:
            self.goto(0, -40)
            self.write(sub, align="center", font=("Arial", 14, "normal"))

    def reset(self):
        self.score = 0
        self.show()


# ===================== اللعبة =====================
class Game:
    def __init__(self):
        self.screen = turtle.Screen()
        self.screen.setup(WIDTH, HEIGHT)
        self.screen.bgcolor("black")
        self.screen.title("Snake Game")
        self.screen.tracer(0)  # إحنا اللي بنحدّث الشاشة بإيدينا

        self.draw_border()
        self.snake = Snake()
        self.food = Food()
        self.scoreboard = Scoreboard()
        self.food.refresh(self.snake)

        self.game_over = False
        self.paused = False
        self.delay = START_DELAY
        self.bind_keys()

    def draw_border(self):
        pen = turtle.Turtle()
        pen.hideturtle()
        pen.penup()
        pen.color("gray")
        pen.pensize(2)
        pen.goto(-LIMIT_X - STEP // 2, -LIMIT_Y - STEP // 2)
        pen.pendown()
        for side in (WIDTH, HEIGHT, WIDTH, HEIGHT):
            pen.forward(side)
            pen.left(90)

    def bind_keys(self):
        s = self.screen
        s.listen()
        for key, action in (("Up", self.snake.up), ("w", self.snake.up),
                            ("Down", self.snake.down), ("s", self.snake.down),
                            ("Left", self.snake.left), ("a", self.snake.left),
                            ("Right", self.snake.right), ("d", self.snake.right)):
            s.onkeypress(action, key)
        s.onkeypress(self.toggle_pause, "p")
        s.onkeypress(self.restart, "space")

    def toggle_pause(self):
        if self.game_over:
            return
        self.paused = not self.paused
        if self.paused:
            self.scoreboard.message("PAUSED", "Press P to continue")
        else:
            self.scoreboard.show()

    def restart(self):
        if not self.game_over:
            return
        self.snake.reset()
        self.scoreboard.reset()
        self.food.refresh(self.snake)
        self.delay = START_DELAY
        self.game_over = False

    def end_game(self):
        self.game_over = True
        self.scoreboard.message("GAME OVER", "Press SPACE to play again")

    def step(self):
        """خطوة واحدة من اللعبة"""
        self.snake.move()

        # أكل الأكل؟
        if self.snake.head.distance(self.food) < STEP / 2:
            self.snake.extend()
            self.scoreboard.add_point()
            self.food.refresh(self.snake)
            # كل ما ياكل يسرع شوية
            self.delay = max(MIN_DELAY, self.delay - 0.003)

        # خسر؟
        if self.snake.hit_wall() or self.snake.hit_self():
            self.end_game()

    def run(self):
        try:
            while True:
                if not self.game_over and not self.paused:
                    self.step()
                self.screen.update()
                time.sleep(self.delay)
        except turtle.Terminator:
            pass  # الشباك اتقفل


if __name__ == "__main__":
    Game().run()