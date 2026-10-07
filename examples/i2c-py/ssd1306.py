#!/usr/bin/env python3
"""Minimal, dependency-free SSD1306 (128x64, I2C) driver for Linux.

Uses only the stdlib: /dev/i2c-N via the I2C_SLAVE ioctl. No smbus/PIL.

Example:
    python3 ssd1306.py "Hello Oz64"
    python3 ssd1306.py --bus 3 --addr 0x3c --size 1 "line 1\\nline 2"
"""

import argparse
import fcntl
import os
import struct
import sys

I2C_SLAVE = 0x0703
WIDTH, HEIGHT = 128, 64

# 5x7 font, drawn as ASCII art (one string per row, 5 columns).
# '#' = lit pixel. Lowercase is folded to uppercase.
_FONT_ART = {
    " ": ["     "] * 7,
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#...#", "#.#.#", "##.##", "#...#"],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": [".###.", "#...#", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "#...#", ".###."],
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    ",": [".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."],
    ":": [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
    ";": [".....", ".##..", ".##..", ".....", ".##..", ".##..", ".#..."],
    "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    "_": [".....", ".....", ".....", ".....", ".....", ".....", "#####"],
    "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    "=": [".....", ".....", "#####", ".....", "#####", ".....", "....."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    "/": ["....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."],
    "(": ["..##.", ".#...", ".#...", ".#...", ".#...", ".#...", "..##."],
    ")": [".##..", "...#.", "...#.", "...#.", "...#.", "...#.", ".##.."],
    "'": ["..#..", "..#..", ".....", ".....", ".....", ".....", "....."],
    '"': [".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."],
    "*": [".....", "#.#.#", ".###.", "#####", ".###.", "#.#.#", "....."],
}


def _encode_font():
    font = {}
    for ch, rows in _FONT_ART.items():
        cols = []
        for x in range(5):
            b = 0
            for y in range(7):
                if rows[y][x] == "#":
                    b |= 1 << y
            cols.append(b)
        font[ch] = bytes(cols)
    return font


FONT = _encode_font()
GLYPH_W, GLYPH_H = 5, 7
ADVANCE = 6  # 5 columns + 1 space


class SSD1306:
    def __init__(self, bus=3, addr=0x3C):
        self.addr = addr
        self.fd = os.open(f"/dev/i2c-{bus}", os.O_RDWR)
        fcntl.ioctl(self.fd, I2C_SLAVE, addr)
        self.buf = bytearray(WIDTH * HEIGHT // 8)
        self._init_panel()

    def _cmd(self, *cmds):
        os.write(self.fd, bytes([0x00]) + bytes(cmds))

    def _data(self, payload):
        # Send in <=32-byte chunks; prefix each with the 0x40 data control byte.
        for i in range(0, len(payload), 32):
            os.write(self.fd, bytes([0x40]) + bytes(payload[i:i + 32]))

    def _init_panel(self):
        self._cmd(
            0xAE,              # display off
            0xD5, 0x80,        # clock divide / oscillator
            0xA8, 0x3F,        # multiplex ratio = 64
            0xD3, 0x00,        # display offset
            0x40,              # start line 0
            0x8D, 0x14,        # charge pump on
            0x20, 0x00,        # memory addressing = horizontal
            0xA1,              # segment remap
            0xC8,              # COM scan direction remapped
            0xDA, 0x12,        # COM pins config
            0x81, 0xCF,        # contrast
            0xD9, 0xF1,        # pre-charge
            0xDB, 0x40,        # VCOMH deselect
            0xA4,              # resume RAM content
            0xA6,              # normal (not inverted)
            0x2E,              # deactivate scroll
            0xAF,              # display on
        )

    def clear(self):
        for i in range(len(self.buf)):
            self.buf[i] = 0

    def pixel(self, x, y, on=True):
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            return
        idx = x + (y // 8) * WIDTH
        if on:
            self.buf[idx] |= 1 << (y % 8)
        else:
            self.buf[idx] &= ~(1 << (y % 8))

    def text(self, x, y, s):
        for ch in s:
            glyph = FONT.get(ch, FONT.get(ch.upper(), FONT["?"]))
            for cx in range(GLYPH_W):
                for cy in range(GLYPH_H):
                    if glyph[cx] & (1 << cy):
                        self.pixel(x + cx, y + cy, True)
            x += ADVANCE
        return x

    def invert(self):
        for i in range(len(self.buf)):
            self.buf[i] ^= 0xFF

    def show(self):
        self._cmd(0x21, 0, WIDTH - 1)  # column range
        self._cmd(0x22, 0, HEIGHT // 8 - 1)  # page range
        self._data(self.buf)

    def close(self):
        os.close(self.fd)


def main(argv=None):
    p = argparse.ArgumentParser(description="Show text on an SSD1306 I2C OLED")
    p.add_argument("text", nargs="?", default="Hello Oz64", help="text (use \\n for newline)")
    p.add_argument("--bus", type=int, default=3, help="I2C bus number (default 3)")
    p.add_argument("--addr", type=lambda v: int(v, 0), default=0x3C)
    p.add_argument("--invert", action="store_true")
    args = p.parse_args(argv)

    text = args.text.replace("\\n", "\n")
    dev = SSD1306(bus=args.bus, addr=args.addr)
    try:
        dev.clear()
        y = 0
        for line in text.split("\n"):
            dev.text(0, y, line)
            y += GLYPH_H + 2
        if args.invert:
            dev.invert()
        dev.show()
        print(f"wrote {text!r} to /dev/i2c-{args.bus} @ {hex(args.addr)}")
    finally:
        dev.close()


if __name__ == "__main__":
    main()
