from enum import Enum

class Orientation(Enum):
    VERTICAL = 1
    HORIZONTAL = 2

class Ship(Enum):
    DESTROYER = 1
    SUBMARINE = 2
    CRUISER = 3
    BATTLESHIP = 4
    CARRIER = 5

ship_size = {
    Ship.DESTROYER: 2,
    Ship.SUBMARINE: 3,
    Ship.CRUISER: 3,
    Ship.BATTLESHIP: 4,
    Ship.CARRIER: 5
}

class Salvo(Enum):
    UNKNOWN = 0
    HIT = 1
    MISS = 2

class BattleShipGame():
    def __init__(self, grid_size = 10):
        self.grid_size = grid_size

        self.ships = {
            1: [[0] * grid_size for _ in range(grid_size)],
            2: [[0] * grid_size for _ in range(grid_size)]
        }

        self.targets = {
            1: [[0] * grid_size for _ in range(grid_size)],
            2: [[0] * grid_size for _ in range(grid_size)]
        }

    def print_grid(self, grid):
        for row in grid:
            for item in row:
                print(item, end="")
            print()

    def print_ships(self, player):
        self.print_grid(self.ships[player])

    def print_targets(self, player):
        self.print_grid(self.targets[player])    

    # vertical ships are oriented going down
    # horizontal ships are oriented going right
    # returns true on success
    # returns false on failure
    # excepts on invalid player
    def place_ship(self, player, ship, orientation, x, y):

        size = ship_size[ship]
        grid = self.ships[player]

        if orientation == Orientation.HORIZONTAL:
            try:
                for x_check in range(x, x+size):
                    if grid[y][x_check] != 0:
                        return False
            except IndexError:
                return False
                
            for x_place in range(x, x+size):
                grid[y][x_place] = ship.value
            return True
            
        if orientation == Orientation.VERTICAL:
            try:
                for y_check in range(y, y+size):
                    if grid[y_check][x] != 0:
                        return False
            except IndexError:
                return False

            for y_place in range(y, y+size):
                grid[y_place][x] = ship.value
            return True
        
    # returns false if move is invalid (duplicate or out of bounds)
    # returns true if move is valid (hit or miss)
    def fire_shot(self, player, x, y):
    
        if player == 1:
            target = 2
        elif player == 2:
            target = 1
        else:
            raise ValueError("Invalid player number")

        target_grid = self.targets[player]
        target_ships = self.ships[target]

        try:
            if target_grid[y][x] != 0:
                return False
            else:
                if target_ships[y][x] != 0:
                    target_grid[y][x] = Salvo.HIT.value
                else:
                    target_grid[y][x] = Salvo.MISS.value
                return True
        except IndexError:
            return False
        
    def check_win(self):

        for player, target in [(1, 2), (2, 1)]:
            target_ships = self.ships[target]
            target_grid = self.targets[player]
            won = True

            for x in range(self.grid_size):
                for y in range(self.grid_size):
                    if target_ships[y][x] != 0 and target_grid[y][x] != Salvo.HIT.value:
                        won = False
                        break
                if not won:
                    break
            if won:
                return player
            
        return 0

        
if __name__ == "__main__":
    game = BattleShipGame()
 
    # --- Place ships ---
    # Player 1
    game.place_ship(1, Ship.DESTROYER,  Orientation.VERTICAL,   9, 8)
    game.place_ship(1, Ship.SUBMARINE,  Orientation.VERTICAL,   4, 6)
    game.place_ship(1, Ship.CRUISER,    Orientation.HORIZONTAL, 6, 5)
    game.place_ship(1, Ship.BATTLESHIP, Orientation.VERTICAL,   1, 1)
    game.place_ship(1, Ship.CARRIER,    Orientation.HORIZONTAL, 3, 2)
 
    # Player 2
    game.place_ship(2, Ship.DESTROYER,  Orientation.HORIZONTAL, 0, 0)
    game.place_ship(2, Ship.SUBMARINE,  Orientation.VERTICAL,   7, 3)
    game.place_ship(2, Ship.CRUISER,    Orientation.HORIZONTAL, 2, 7)
    game.place_ship(2, Ship.BATTLESHIP, Orientation.VERTICAL,   5, 5)
    game.place_ship(2, Ship.CARRIER,    Orientation.HORIZONTAL, 0, 9)
 
    print("=== Player 1 ships ===")
    game.print_ships(1)
    print("=== Player 2 ships ===")
    game.print_ships(2)
 
    # --- Sanity check: no winner at start ---
    assert game.check_win() == 0, "Expected no winner at start"
    print("\ncheck_win() at start: 0 (correct)")
 
    # --- Fire some shots, mix of hits and misses ---
    # Player 1 shoots at player 2
    assert game.fire_shot(1, 0, 0) == True   # hit: destroyer
    assert game.fire_shot(1, 1, 0) == True   # hit: destroyer
    assert game.fire_shot(1, 3, 3) == True   # miss
    assert game.fire_shot(1, 0, 0) == False  # duplicate shot, invalid
 
    # Player 2 shoots at player 1
    assert game.fire_shot(2, 1, 1) == True   # hit: battleship
    assert game.fire_shot(2, 9, 9) == True   # miss
    assert game.fire_shot(2, 10, 10) == False  # out of bounds
 
    assert game.check_win() == 0, "Expected no winner mid-game"
    print("check_win() mid-game: 0 (correct)")
 
    # --- Player 1 sinks all of player 2's ships ---
    # Destroyer already hit at (0,0) and (1,0)
    # Submarine at (7, 3..5)
    game.fire_shot(1, 7, 3)
    game.fire_shot(1, 7, 4)
    game.fire_shot(1, 7, 5)
    # Cruiser at (2..4, 7)
    game.fire_shot(1, 2, 7)
    game.fire_shot(1, 3, 7)
    game.fire_shot(1, 4, 7)
    # Battleship at (5, 5..8)
    game.fire_shot(1, 5, 5)
    game.fire_shot(1, 5, 6)
    game.fire_shot(1, 5, 7)
    game.fire_shot(1, 5, 8)
    # Carrier at (0..4, 9)
    game.fire_shot(1, 0, 9)
    game.fire_shot(1, 1, 9)
    game.fire_shot(1, 2, 9)
    game.fire_shot(1, 3, 9)
    game.fire_shot(1, 4, 9)
 
    winner = game.check_win()
    assert winner == 1, f"Expected player 1 to win, got {winner}"
    print(f"check_win() after player 1 sinks all ships: {winner} (correct)")
 
    print("\n=== Player 1 target grid ===")
    game.print_targets(1)
    print("\nAll assertions passed!")
