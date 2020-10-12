import os
import math
import pickle
import functools


BLACK            = "000000"
WHITE            = "ffffff"
RED              = "ff0000"
GREEN            = "00ff00"
BLUE             = "0000ff"
ORANGE           = "ffff00"
YELLOW           = "d8ff00"
DARK_ORANGE      = "484800"
MID_ORANGE       = "989800"
BRIGHT_ORANGE    = "c0c000"
DARK_BLUE_GRAY   = "102a3b"
MID_BLUE_GRAY    = "215172"
BRIGHT_BLUE_GRAY = "42a2e4"
BRIGHT_GRAY      = "d0d0d0"
BRIGHT_RED       = "b00000"
DARK_GRAY        = "383838"
DARK_RED         = "800000"
BRIGHT_GREEN     = "00b800"


def normalize_hex_color(color):
    if color[0] == "#":
        return color[1:]
    return color


def add_hashtag(color):
    if color[0] == "#":
        return color
    return f"#{color}"


def hex_to_dec(color):
    c = normalize_hex_color(color)
    return tuple(int(c[i:i+2], 16) for i in range(0, 6, 2))


def dec_to_hex(triplet):
    return "%02.x%02.x%02.x" % triplet


def to_hex(fn):

    @functools.wraps(fn)
    def inner(*args, **kwargs):
        return dec_to_hex(fn(*args, **kwargs))

    return inner


@to_hex
def complement(color, scale=1):
    triplet = hex_to_dec(color)
    return tuple(int((1-scale)*c + scale * (255 - c)) for c in triplet)


def lin(start, stop, scaling):
    return start + round((stop - start)*scaling)


@to_hex
def gradient(value, max_value, colors, scaling=None):
    if value < 0:
        return colors[0]
    elif value >= max_value:
        return colors[-1]
    num_intervals = len(colors) - 1
    scaled_value = value * num_intervals / max_value
    idx = math.floor(scaled_value)
    start, stop = colors[idx], colors[idx+1]
    scaling_factor = scaled_value - idx
    if scaling:
        scaling_factor = min(1, scaling_factor * scaling)
    return tuple(lin(start[i], stop[i], scaling_factor) for i in range(3))


@functools.lru_cache(maxsize=1)
def get_ascii_colors():
    CUR_DIR = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(CUR_DIR, "colors.dat"), "rb") as f:
        return pickle.load(f)


def distance(color, other):
    return sum((color[i] - other[i])**2 for i in range(len(color))) ** 0.5


def to_ascii_color(color):
    dec = hex_to_dec(color)
    ascii = get_ascii_colors()
    return min((distance(c, dec), i) for i, c in enumerate(ascii))[1]
