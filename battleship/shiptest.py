import sys
import os
import time
from multiprocessing.connection import Listener
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from shipworld import ShipWorld
from shipnpc import ShipNPC
from randomnpc import RandomNPC

ADDRESS = ("localhost", 6000)
GAME_TIMEOUT = 1800 

if __name__ == "__main__":

    combs = [("llama", "random"), ("qwen", "random")]

    for run_idx in range(20):

        for comb in combs:

            timestamp = int(datetime.now().strftime("%Y%m%d%H%M%S"))
            print(f"\n=== Run {run_idx + 1}/20, matchup: {comb}, timestamp: {timestamp} ===\n", flush=True)

            listener = Listener(ADDRESS)

            world = ShipWorld(seed=timestamp, listener=listener, timestamp=timestamp)

            llama = ShipNPC(
                name="Llama 8B",
                personality="Llama",
                seed=timestamp,
                address=ADDRESS,
                game_model="llama3.1:8b",
                timestamp=timestamp
            )

            qwen = ShipNPC(
                name="Qwen 9B",
                personality="Qwen",
                seed=timestamp,
                address=ADDRESS,
                game_model="qwen3.5:9b",
                timestamp=timestamp
            )

            randnpc = RandomNPC(
                name="Random",
                seed=timestamp,
                address=ADDRESS,
            )

            if comb == ("llama", "random"):
                npc1 = llama
                npc2 = randnpc
            elif comb == ("qwen", "random"):
                npc1 = qwen
                npc2 = randnpc
            else:
                npc1 = randnpc
                npc2 = randnpc

            world.start()
            time.sleep(1)

            npc1.start()
            npc2.start()

            # Wait for the world to finish, but don't trust it to exit cleanly
            world.join(timeout=GAME_TIMEOUT)
            if world.is_alive():
                print(f"[WARN] World process did not exit cleanly, terminating.", flush=True)
                world.terminate()
                world.join()

            npc1.terminate()
            npc2.terminate()
            npc1.join()
            npc2.join()

            try:
                listener.close()
            except Exception as e:
                print(f"[WARN] Listener close failed: {e}", flush=True)

            # Small pause to let the OS release the port before the next bind
            time.sleep(2)

            print(f"=== End run {run_idx + 1}, matchup {comb} ===\n", flush=True)

    print("All runs complete. Check logs/ for results.")