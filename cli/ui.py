import os
import time

class TerminalUI:
    @staticmethod
    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def typing_print(text, speed=0.03):
        for char in text:
            print(char, end='', flush=True)
            time.sleep(speed)
        print()