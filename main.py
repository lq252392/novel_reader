import tkinter as tk
from ui.app import ReaderApp

def main():
    root = tk.Tk()
    
    # 修复 Win10/11 高 DPI 模糊问题
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    app = ReaderApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
