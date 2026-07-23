from chat_engine import PhantasmChat
from ui import TerminalUI

def main():
    chat = PhantasmChat()
    ui = TerminalUI()
    
    ui.clear_screen()
    print("=== Phantasm 终端 v1.3 ===")
    
    while True:
        user_input = input("\n[你] > ").strip()
        if user_input.lower() in ['exit', 'quit']: break
        
        print("\n[影子] ", end='')
        reply = chat.get_response(user_input)
        ui.typing_print(reply)

if __name__ == "__main__":
    main()