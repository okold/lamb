import sys
import os
import time
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
from world import World
from room import Room

from battleship import BattleShipGame, Ship, Orientation, Salvo

LOG_DIR = "logs"

class ShipWorld(World):

    PLAYER_COUNT = 2

    def __init__(self, cli=None, seed=1234, listener=None, timestamp=None):
        self.battle_room = Room("battle")

        super().__init__(
            cli=cli,
            default_room=self.battle_room,
            turn_based=True,
            seed=seed,
            listener=listener,
        )

        self.game = BattleShipGame()
        self.player_map = {}
        self._timestamp = timestamp
        self._log_path = None

    def _init_log(self):
        """Called inside the process, not in __init__."""
        os.makedirs(LOG_DIR, exist_ok=True)
        timestamp = self._timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_path = os.path.join(LOG_DIR, f"{timestamp}_shipworld.log")
        with open(self._log_path, 'w') as f:
            f.write(f"=== ShipWorld log {timestamp} ===\n")

    ### LOGGING

    def log(self, msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        if self._log_path:
            with open(self._log_path, 'a') as f:
                f.write(line + "\n")

    ### DISPLAY HELPERS

    def print_grids(self, player_num, name):
        target_num = 2 if player_num == 1 else 1
        target_grid = self.game.targets[player_num]
        enemy_ships  = self.game.ships[target_num]
        size = self.game.grid_size

        SYMBOLS = {0: ".", 1: "X", 2: "o"}
        SHIP_HIT = "X"
        SHIP_CELL = "#"

        header = "  " + " ".join(str(i) for i in range(size))
        gap = "    "
        print(f"\n=== {name} firing ===", flush=True)
        print(f"{'YOUR SHOTS':^25}{gap}{'ENEMY FLEET (truth)':^25}", flush=True)
        print(f"{header}{gap}{header}", flush=True)
        for y in range(size):
            left  = " ".join(SYMBOLS[target_grid[y][x]] for x in range(size))
            right = " ".join(
                (SHIP_HIT if target_grid[y][x] == 1 else SHIP_CELL)
                if enemy_ships[y][x] != 0
                else SYMBOLS[target_grid[y][x]]
                for x in range(size)
            )
            print(f"{y} {left}{gap}{y} {right}", flush=True)
        print(flush=True)

    def print_ship_layout(self, player_num, name):
        grid = self.game.ships[player_num]
        size = self.game.grid_size
        header = "  " + " ".join(str(i) for i in range(size))
        print(f"\n=== {name}'s fleet ===", flush=True)
        print(header, flush=True)
        for y in range(size):
            row = " ".join(str(grid[y][x]) if grid[y][x] != 0 else "." for x in range(size))
            print(f"{y} {row}", flush=True)
        print(flush=True)

    ### ABSTRACT METHOD IMPLEMENTATIONS

    def setup(self):
        self._init_log()

        self.log("Waiting for 2 players to connect...")
        while True:
            with self.actors_lock:
                if len(self.actors) == self.PLAYER_COUNT:
                    self.accept_connections = False
                    break
            time.sleep(1)

        for i, name in enumerate(self.actors, start=1):
            self.player_map[name] = i
            self.actors[name]["player_num"] = i
            self.actors[name]["status"] = "active"

        self.log(f"Players connected: {list(self.player_map.keys())}")

        for name, num in self.player_map.items():
            self.send_to_actor(name, f"You are Player {num}. Place your ships.", "role")
            self.send_act_token(name)

        pending = list(self.player_map.keys())
        while pending:
            for name in list(pending):
                msg = self.try_recv(self.actors[name]["conn"])
                if msg and msg.get("action") == "place_ships":
                    player_num = self.player_map[name]
                    placements = msg["content"]
                    success = True
                    
                    # Reject submissions with wrong number of ships
                    if len(placements) != 5:
                        self.log(f"[PLACEMENT FAIL] {name}: sent {len(placements)} ships, need exactly 5")
                        self.send_to_actor(name, f"You sent {len(placements)} ships but must place exactly 5. Try again.", "context")
                        success = False
                    else:
                        for p in placements:
                            result = self.game.place_ship(
                                player_num,
                                Ship[p["ship"]],
                                Orientation[p["orientation"]],
                                p["x"],
                                p["y"],
                            )
                            if not result:
                                self.log(f"[PLACEMENT FAIL] {name}: {p['ship']} at ({p['x']},{p['y']}) {p['orientation']}")
                                self.send_to_actor(name, f"Invalid placement for {p['ship']}. Placement rejected. Try a different placement.", "context")
                                self.game.ships[player_num] = [[0] * self.game.grid_size for _ in range(self.game.grid_size)]
                                success = False
                                break
                    if success:
                        self.log(f"{name} placed all ships.")
                        self.send_to_actor(name, "All ships placed. Waiting for opponent...", "context")
                        self.send_to_actor(name, "All ships placed", "role")
                        self.print_ship_layout(player_num, name)
                        pending.remove(name)
                    else:
                        self.send_act_token(name)
            time.sleep(0.5)

        self.log("All ships placed. Game starting!")
        for name in self.actors:
            self.send_to_actor(name, "Both players are ready. Game on!", "context")

    def turn_based_loop(self):
        turn_order = list(self.player_map.keys())
        shot_counts = {name: 0 for name in turn_order}

        while not self.end:
            for name in turn_order:
                player_num = self.player_map[name]

                #self.send_to_actor(name, "It's your turn. Fire a shot.", "context")
                self.send_act_token(name)

                valid = False
                while not valid:
                    while True:
                        msg = self.actors[name]["conn"].recv()
                        if msg.get("action") == "fire":
                            break
                        # Got a non-fire action (e.g. stale place_ships) — re-prompt
                        self.log(f"[UNEXPECTED ACTION] {name} sent {msg.get('action')} during firing; re-prompting.")
                        #self.send_to_actor(name, "It's your turn. Fire a shot.", "context")
                        self.send_act_token(name)

                    x, y = msg["x"], msg["y"]
                    valid = self.game.fire_shot(player_num, x, y)

                    if not valid:
                        self.log(f"[INVALID SHOT] {name} -> ({x},{y}), retrying.")
                        self.send_to_actor(name, f"Invalid shot at ({x},{y}) — already fired there or out of bounds. Try a position within the valid coordinates list.", "context")
                        self.send_act_token(name)

                shot_counts[name] += 1
                result = self.game.targets[player_num][y][x]
                outcome = "HIT" if result == Salvo.HIT.value else "MISS"

                self.print_grids(player_num, name)
                self.log(f"{name} shot #{shot_counts[name]} -> ({x},{y}): {outcome}")

                self.send_to_actor(name, f"You shot at ({x},{y}): {outcome}", "context")
                opponent_name = [n for n in self.actors if n != name][0]
                self.send_to_actor(opponent_name, f"Your opponent fired at ({x},{y}): {outcome}", "context")

                winner_num = self.game.check_win()
                if winner_num:
                    winner_name = next(n for n, num in self.player_map.items() if num == winner_num)
                    loser_name = opponent_name if winner_name == name else name
                    self.log(f"Game over! {winner_name} wins in {shot_counts[winner_name]} shots! ({loser_name} took {shot_counts[loser_name]})")
                    for n in self.actors:
                        self.send_to_actor(n, f"Game over! {winner_name} wins!", "context")
                    self.end = True
                    break

                time.sleep(self.WAIT_TIME)

            if self.end:
                break

    def real_time_loop(self):
        pass

    def cleanup(self):
        try:
            self.print_queue.put("Game ended.")  # unblock print_loop
        except:
            pass
        try:
            self.flagged_actors = list(self.actors.keys())
            self.clean_flagged_actors()
        except:
            pass
        try:
            self.listener.close()
        except:
            pass