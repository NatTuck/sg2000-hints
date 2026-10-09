import sys

from ssd1306 import SSD1306


def draw(dev, text):
    # Task 5: replace this with pixel drawing
    dev.text(0, 0, text)


def main():
    text = " ".join(sys.argv[1:]) or "Hello, OLED!"
    dev = SSD1306(bus=1, addr=0x3C)
    try:
        dev.clear()
        draw(dev, text)
        dev.show()
        print(f"wrote {text!r} to /dev/i2c-1 @ 0x3c")
    finally:
        dev.close()


if __name__ == "__main__":
    main()
