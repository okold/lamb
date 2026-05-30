import sys
import os
import re
import json
from typing import List, Literal
from pydantic import BaseModel

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
from npc import NPC
from actor import DEFAULT_ADDRESS

MAX_ERROR_PAIRS = 3

class ShipPlacement(BaseModel):
    ship: Literal["CARRIER", "BATTLESHIP", "CRUISER", "SUBMARINE", "DESTROYER"]
    orientation: Literal["HORIZONTAL", "VERTICAL"]
    x: int
    y: int

class PlaceShipsAction(BaseModel):
    action: Literal["place_ships"]
    content: List[ShipPlacement]

class FireAction(BaseModel):
    action: Literal["fire"]
    x: int
    y: int

SYSTEM_MESSAGE = """You are playing a game of Battleship on a 10x10 grid (columns 0-9, rows 0-9).

SHIP PLACEMENT:
You must place 5 ships. Each ship occupies consecutive cells.
- DESTROYER: 2 cells
- SUBMARINE: 3 cells
- CRUISER: 3 cells
- BATTLESHIP: 4 cells
- CARRIER: 5 cells

HORIZONTAL ships extend rightward from (x, y): they occupy (x, y), (x+1, y), ...
VERTICAL ships extend downward from (x, y): they occupy (x, y), (x, y+1), ...
Ships must not overlap and must not go out of bounds (0-9).

When asked to place ships, return exactly:
{"action": "place_ships", "content": [
    {"ship": "CARRIER",     "orientation": "HORIZONTAL", "x": 0, "y": 0},
    {"ship": "BATTLESHIP",  "orientation": "VERTICAL",   "x": 5, "y": 0},
    {"ship": "CRUISER",     "orientation": "HORIZONTAL", "x": 2, "y": 5},
    {"ship": "SUBMARINE",   "orientation": "VERTICAL",   "x": 8, "y": 3},
    {"ship": "DESTROYER",   "orientation": "HORIZONTAL", "x": 4, "y": 9}
]}

FIRING:
On your turn, choose a coordinate from the VALID COORDINATES list in your character sheet.
Return exactly:
{"action": "fire", "x": <0-9>, "y": <0-9>}
"""

SHOT_PATTERN = re.compile(r"shot at \((\d+),(\d+)\): (HIT|MISS)", re.IGNORECASE)


class ShipNPC(NPC):

    def __init__(self,
                 name,
                 personality,
                 description="A battleship AI.",
                 gender="indeterminate",
                 game_model="llama3.1:8b",
                 summary_model="llama4:16x17b",
                 logger=None,
                 csv_logger=None,
                 seed=1234,
                 address=DEFAULT_ADDRESS,
                 timestamp=None):

        super().__init__(
            name=name,
            personality=personality,
            goal="Sink all enemy ships before your own are sunk.",
            description=description,
            can_speak=False,
            gender=gender,
            game_model=game_model,
            summary_model=summary_model,
            turn_based=True,
            logger=logger,
            csv_logger=csv_logger,
            strategy="window",
            seed=seed,
            address=address,
        )
        self.context.context_limit = 10
        self.context.context_keep = 10

        self.SYSTEM_MESSAGE = SYSTEM_MESSAGE
        self.ships_placed = False
        self.shot_grid = [["." for _ in range(10)] for _ in range(10)]
        self.last_error = []
        self._npc_log_path = None

        self._npc_log_path = None
        self._timestamp = timestamp

    # --- Logging ---

    def npc_log(self, msg):
        from datetime import datetime
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        #print(line, flush=True)
        if self._npc_log_path is None:
            os.makedirs("logs", exist_ok=True)
            prefix = f"{self._timestamp}_" if self._timestamp else ""
            self._npc_log_path = f"logs/{prefix}{self.name}.log"
            with open(self._npc_log_path, 'w') as f:
                f.write(f"=== {self.name} log ===\n")
        with open(self._npc_log_path, 'a') as f:
            f.write(line + "\n")

    # --- Shot tracking ---

    def record_shot(self, text: str):
        """Update the persistent shot grid from a shot result string."""
        m = SHOT_PATTERN.search(text)
        if m:
            x, y, result = int(m.group(1)), int(m.group(2)), m.group(3)
            self.shot_grid[y][x] = "X" if result == "HIT" else "o"

    def build_shot_matrix_old(self) -> str:
        hits    = [(x, y) for y in range(10) for x in range(10) if self.shot_grid[y][x] == "X"]
        misses  = [(x, y) for y in range(10) for x in range(10) if self.shot_grid[y][x] == "o"]
        untried = [(x, y) for y in range(10) for x in range(10) if self.shot_grid[y][x] == "."]
 
        hits_str    = ", ".join(f"({x},{y})" for x, y in hits)    or "(none yet)"
        misses_str  = ", ".join(f"({x},{y})" for x, y in misses)  or "(none yet)"
        untried_str = ", ".join(f"({x},{y})" for x, y in untried)
 
        return (
            f"----INVALID COORDINATES----\n"
            f"Hits: {hits_str}\n"
            f"Misses: {misses_str}\n\n"
            f"----VALID COORDINATES----\n"
            f"Valid targets:\n{untried_str}\n"
        )
 
    def build_shot_matrix(self) -> str:
        SYMBOLS = {".": "open", "X": "hit", "o": "miss"}
        rows = []
        for y in range(10):
            row = "  ".join(f"({x},{y},{SYMBOLS[self.shot_grid[y][x]]})" for x in range(10))
            rows.append(row)
        
        untried = [(x, y) for y in range(10) for x in range(10) if self.shot_grid[y][x] == "."]
        untried_str = ", ".join(f"({x},{y})" for x, y in untried)
        
        return (
            f"----SHOT BOARD----\n"
            f"{chr(10).join(rows)}\n\n"
            f"----VALID TARGETS----\n"
            f"{untried_str}\n"
        )

    # --- NPC interface ---

    def character_sheet(self) -> str:
        return (
            f"Player: {self.name}\n\n"
            #f"Shot board (. = untried, X = hit, o = miss):\n"
            f"{self.build_shot_matrix()}\n"
            f"HINT: If a coordinate is a hit, adjacent cells are also likely to hit!"
        )

    def gen_system_prompt_old(self):
        prompt = [
            {"role": "system", "content": self.SYSTEM_MESSAGE}
        ] + self.context.context

        if not self.ships_placed:
            prompt.append({"role": "system", "content": "Place your ships now. Return the place_ships JSON."})
        else:
            #print(self.character_sheet())
            prompt.append({"role": "system", "content": self.character_sheet() + "\nYour turn. Pick a coordinate from the Valid targets list and return the fire JSON."})

        return prompt

    def gen_system_prompt(self):
        # Reclassify error messages as user messages so the model
        # treats them as feedback rather than just more rules.
        rewritten_context = []
        for msg in self.context.context:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if isinstance(content, str) and "(10,10)" in content:
                    continue  # skip exhaustion fallback noise
                if msg.get("role") == "system":
                    if isinstance(content, str) and ("Invalid shot" in content or "You shot at" in content or "Your opponent" in content):
                        rewritten_context.append({"role": "user", "content": content})
                        continue
            rewritten_context.append(msg)

        prompt = [
            {"role": "system", "content": self.SYSTEM_MESSAGE}
        ] + rewritten_context + self.last_error

        if not self.ships_placed:
            prompt.append({"role": "system", "content": "Place your ships now. Return the place_ships JSON."})
        else:
            prompt.append({"role": "system", "content": self.character_sheet() + "\nYour turn. Pick a coordinate from the Valid targets list and return the fire JSON."})

        return prompt

    def generate_summary_message(self) -> str:
        return ""

    def update_role(self, new_role):
        """Intercept the role message the world sends on confirmed placement."""
        if "All ships placed" in str(new_role):
            self.ships_placed = True
        return super().update_role(new_role)

    def _untried_str(self) -> str:
        untried = [(x, y) for y in range(10) for x in range(10) if self.shot_grid[y][x] == "."]
        return ", ".join(f"({x},{y})" for x, y in untried)


    def act(self):
        # Scan every context message for shot results and update the grid.
        # record_shot is idempotent (writes the same value to the same cell),
        # so re-scanning trimmed-and-restored context is safe.
        for msg in self.context.context:
            payload = msg if isinstance(msg, str) else msg.get("content", "")
            if isinstance(payload, dict):
                payload = payload.get("content", "")
            if isinstance(payload, str):
                self.record_shot(payload)
 
        action_model = PlaceShipsAction if not self.ships_placed else FireAction
 
        max_retries = 50
        for attempt in range(max_retries):
            prompt = self.gen_system_prompt()


            self.npc_log(f"attempt {attempt+1}/{max_retries} | prompt length: {len(prompt)}")
            for m in prompt:
                role = m.get("role", "?")
                snippet = str(m.get("content", ""))[:120].replace("\n", " ")
                self.npc_log(f"  [{role}] {snippet}")

            if self.ships_placed:
                content, _, tokens_in, tokens_out, eval_in, eval_out = self.llm.prompt(
                    prompt, enforce_model=action_model, keep_alive=1800, think=False, max_tokens=20
                )
            else:
                content, _, tokens_in, tokens_out, eval_in, eval_out = self.llm.prompt(
                    prompt, enforce_model=action_model, keep_alive=1800, think=False
                )

            self.npc_log(f"  -> raw response: {str(content)[:200].replace(chr(10), ' ')}")

            try:
                clean = content.strip() if content else ""
                if clean.startswith("```"):
                    clean = clean.removeprefix("```json").removeprefix("```").strip()
                    clean = clean.removesuffix("```").strip()
                output = json.loads(clean)

                # Client-side validation for fire actions — catch invalid targets
                # before they ever reach the world
                if output.get("action") == "fire":
                    x, y = output.get("x"), output.get("y")
                    if not (0 <= x <= 9 and 0 <= y <= 9) or self.shot_grid[y][x] != ".":
                        self.npc_log(f"  [CLIENT REJECT] ({x},{y}) not in valid targets")
                        if content:
                            self.last_error.append({"role": "assistant", "content": clean})
                        self.last_error.append({"role": "system", "content":
                            f"({x},{y}) is not a valid target and was rejected by the game server."
                            f"You MUST pick from the valid coordinates list:\n{self._untried_str()}"
                        })

                        while len(self.last_error) > MAX_ERROR_PAIRS * 2:
                            self.last_error.pop(0)  # drop oldest pair
                        continue

                self.npc_log(f"  [SUCCESS] sending: {clean[:100]}")
                self.context.append({"role": "assistant", "content": clean})
                self.conn.send(output)
                self.last_error = []
                return

            except Exception as e:
                self.npc_log(f"  [PARSE FAIL] attempt {attempt+1}: {e}")
                self.npc_log(f"  [PARSE FAIL] raw: {str(content)[:200].replace(chr(10), ' ')}")
                if content:
                    self.last_error.append({"role": "assistant", "content": content})
                    self.last_error.append({"role": "user", "content": f"Your previous response was invalid and rejected by the game server. Return ONLY valid JSON, no explanation, no reasoning, no markdown."})

                    while len(self.last_error) > MAX_ERROR_PAIRS * 2:
                        self.last_error.pop(0)  # drop oldest pair

        # All retries exhausted — use hardcoded fallback
        self.npc_log(f"  [EXHAUSTED] all retries failed, using fallback")
        if not self.ships_placed:
            self.conn.send({
                "action": "place_ships",
                "content": [
                    {"ship": "CARRIER",    "orientation": "HORIZONTAL", "x": 0, "y": 0},
                    {"ship": "BATTLESHIP", "orientation": "HORIZONTAL", "x": 0, "y": 2},
                    {"ship": "CRUISER",    "orientation": "HORIZONTAL", "x": 0, "y": 4},
                    {"ship": "SUBMARINE",  "orientation": "HORIZONTAL", "x": 0, "y": 6},
                    {"ship": "DESTROYER",  "orientation": "HORIZONTAL", "x": 0, "y": 8},
                ]
            })
            self.ships_placed = True
        else:
            self.conn.send({"action": "fire", "x": 10, "y": 10})