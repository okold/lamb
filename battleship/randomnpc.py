import sys
import os
import random
import time

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
from actor import Actor, DEFAULT_ADDRESS
from battleship import Ship, Orientation

SHIPS = [
    ("CARRIER",    5, "HORIZONTAL"),
    ("BATTLESHIP", 4, "HORIZONTAL"),
    ("CRUISER",    3, "HORIZONTAL"),
    ("SUBMARINE",  3, "HORIZONTAL"),
    ("DESTROYER",  2, "HORIZONTAL"),
]

class RandomNPC(Actor):

    def __init__(self, name, seed=1234, address=DEFAULT_ADDRESS):
        super().__init__(
            name=name,
            personality="",
            goal="",
            address=address,
        )
        self.seed = seed
        self.ships_placed = False
        self.untried = [(x, y) for y in range(10) for x in range(10)]

    def place_ships_randomly(self):
        """Generates a valid random ship placement by brute force."""
        while True:
            grid = [[0] * 10 for _ in range(10)]
            placements = []
            success = True

            for ship_name, size, _ in SHIPS:
                placed = False
                attempts = 0
                while not placed and attempts < 200:
                    attempts += 1
                    orientation = random.choice(["HORIZONTAL", "VERTICAL"])
                    if orientation == "HORIZONTAL":
                        x = random.randint(0, 9 - size)
                        y = random.randint(0, 9)
                        cells = [(x + i, y) for i in range(size)]
                    else:
                        x = random.randint(0, 9)
                        y = random.randint(0, 9 - size)
                        cells = [(x, y + i) for i in range(size)]

                    if all(grid[cy][cx] == 0 for cx, cy in cells):
                        for cx, cy in cells:
                            grid[cy][cx] = 1
                        placements.append({
                            "ship": ship_name,
                            "orientation": orientation,
                            "x": x,
                            "y": y,
                        })
                        placed = True

                if not placed:
                    success = False
                    break

            if success:
                return placements

    def run(self):
        random.seed(self.seed)
        self.connect()

        while True:
            try:
                msg = self.conn.recv()
                msg_type = msg.get("type")

                if msg_type == "act_token":
                    if not self.ships_placed:
                        placements = self.place_ships_randomly()
                        self.conn.send({"action": "place_ships", "content": placements})
                    else:
                        x, y = self.untried.pop(random.randrange(len(self.untried)))
                        self.conn.send({"action": "fire", "x": x, "y": y})

                elif msg_type == "context":
                    payload = msg.get("content", "")
                    # content may be a plain string or a {"role": ..., "content": ...} dict
                    if isinstance(payload, dict):
                        payload = payload.get("content", "")
                    if isinstance(payload, str) and "All ships placed" in payload:
                        self.ships_placed = True

            except EOFError:
                break
            except ConnectionResetError:
                break

        try:
            self.conn.close()
        except:
            pass