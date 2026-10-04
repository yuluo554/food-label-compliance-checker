"""python -m food_label_checker 入口（Windows 下建议 `py -X utf8 -m food_label_checker`）。"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
