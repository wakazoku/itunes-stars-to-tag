"""ダブルクリック起動用のランチャー。

拡張子 ``.pyw`` で起動すると Python は ``pythonw.exe`` を使い、
黒いコンソールウィンドウを表示せず GUI だけが立ち上がる。
"""
from gui import main


if __name__ == "__main__":
    main()
