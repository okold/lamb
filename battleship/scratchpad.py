from enum import Enum

grid_size = 10
p1_ships = [[0] * grid_size for _ in range(grid_size)]
p1_targets = [[0] * grid_size for _ in range(grid_size)]
p2_ships = [[0] * grid_size for _ in range(grid_size)]
p2_targets = [[0] * grid_size for _ in range(grid_size)]

class Orientation(Enum):
    VERTICAL = 1
    HORIZONTAL = 2

class Ship(Enum):
    DESTROYER = 1
    SUBMARINE = 2
    CRUISER = 3
    BATTLESHIP = 4
    CARRIER = 5

class Salvo(Enum):
    UNKNOWN = 0
    HIT = 1
    MISS = 2

def ship_size(ship):
    if ship == Ship.DESTROYER:
        return 2
    elif ship == Ship.SUBMARINE or ship == Ship.CRUISER:
        return 3
    elif ship == Ship.BATTLESHIP:
        return 4
    elif ship == Ship.CARRIER:
        return 5
    else: 
        return 0

# vertical ships are oriented going down
# horizontal ships are oriented going right
def place_ship(grid, ship, orientation, x, y):

    size = ship_size(ship)

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

def print_grid(grid):
    for row in grid:
        for item in row:
            print(item, end="")
        print()

place_ship(p1_ships, Ship.DESTROYER, Orientation.VERTICAL, 9, 8)
place_ship(p1_ships, Ship.SUBMARINE, Orientation.VERTICAL, 4, 6)
place_ship(p1_ships, Ship.CRUISER, Orientation.HORIZONTAL, 6, 5)
place_ship(p1_ships, Ship.BATTLESHIP, Orientation.VERTICAL, 1, 1)
place_ship(p1_ships, Ship.CARRIER, Orientation.HORIZONTAL, 3, 2)
print_grid(p1_ships)

# returns false if move is invalid (duplicate or out of bounds)
# returns true if move is valid (hit or miss)
def fire_shot(target_ships, target_grid, x, y):
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

print(fire_shot(p1_ships, p2_targets, 0, 0), Salvo(p2_targets[0][0]).name)
print(fire_shot(p1_ships, p2_targets, 1, 1), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 10, 10))
print_grid(p2_targets)

def check_win(target_ships, target_grid):
    for x in range(grid_size):
        for y in range(grid_size):
            if target_ships[y][x] != 0 and target_grid[y][x] != Salvo.HIT.value:
                return False
    return True

print(check_win(p1_ships, p2_targets))

print(fire_shot(p1_ships, p2_targets, 1, 2), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 1, 3), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 1, 4), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 3, 2), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 4, 2), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 5, 2), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 6, 2), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 7, 2), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 9, 8), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 9, 9), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 4, 6), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 4, 7), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 4, 8), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 6, 5), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 7, 5), Salvo(p2_targets[1][1]).name)
print(fire_shot(p1_ships, p2_targets, 8, 5), Salvo(p2_targets[1][1]).name)
print_grid(p2_targets)

print(check_win(p1_ships, p2_targets))