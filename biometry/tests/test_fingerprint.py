"""Fingerprint util: aHash is stable per image, distinct across images, and
tolerant of small content changes."""
from PIL import Image, ImageDraw

from engine.fingerprint import ahash, distance, matches


def _img(fill, mark=None):
    im = Image.new("RGB", (120, 240), fill)
    if mark:
        ImageDraw.Draw(im).rectangle(mark, fill=(0, 0, 0))
    return im


def test_same_image_hashes_identically():
    im = _img((200, 200, 200), mark=(10, 10, 60, 60))
    assert ahash(im) == ahash(im)
    assert distance(ahash(im), ahash(im)) == 0


def test_different_layouts_are_far_apart():
    a = ahash(_img((255, 255, 255), mark=(5, 5, 50, 50)))        # mark top-left
    b = ahash(_img((255, 255, 255), mark=(70, 180, 115, 230)))   # mark bottom-right
    assert distance(a, b) > 28
    assert not matches(a, b)


def test_small_content_change_still_matches():
    base = _img((255, 255, 255), mark=(10, 10, 110, 120))
    tweaked = _img((255, 255, 255), mark=(10, 10, 110, 120))
    ImageDraw.Draw(tweaked).rectangle((12, 200, 40, 210), fill=(40, 40, 40))  # a small "list item"
    assert matches(ahash(base), ahash(tweaked))


def test_bad_input_is_handled():
    assert ahash("not an image") == ""
    assert distance("", "abc") >= 10 ** 9
    assert not matches("", "0" * 64)
