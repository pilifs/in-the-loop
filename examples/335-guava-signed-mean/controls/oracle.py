import json
import sys


def driver_args():
    return ["--observations"]


def grid(width):
    minimum, maximum = -(1 << (width - 1)), (1 << (width - 1)) - 1
    return (minimum, minimum + 1, minimum // 2, -2, -1, 0, 1, 2, (maximum // 2) + 1, maximum - 1, maximum)


def problems(lines):
    remaining = {(w, x, y) for w in (32, 64) for x in grid(w) for y in grid(w)}
    differences = []
    for line in lines:
        row = json.loads(line)
        width, x, y, got, big_integer = (row[k] for k in ("width", "x", "y", "got", "oracle"))
        if (width, x, y) not in remaining or any(type(v) is not int for v in (width, x, y, got, big_integer)):
            raise ValueError("unknown or duplicate mean input")
        remaining.remove((width, x, y))
        expected = (x + y) // 2
        if big_integer != expected:
            raise ValueError("BigInteger disagrees with exact addition and arithmetic shift")
        if got != expected:
            differences.append([[width, x, y], f"mean {got}, expected {expected}"])
    if remaining:
        raise ValueError("incomplete boundary grid")
    return differences


def reduced_width():
    """Test the independently carried top bit against exact integer arithmetic."""
    checked = 0
    for width in range(2, 9):
        modulus = 1 << width
        for a in range(-modulus // 2, modulus // 2):
            for b in range(-modulus // 2, modulus // 2):
                low = (a + b) % modulus
                carry = low < (a % modulus)
                upper = (a < 0) ^ (b < 0) ^ carry
                # The upper bit has weight -modulus in the signed, widened sum.
                assert (low - int(upper) * modulus) >> 1 == (a + b) // 2
                checked += 1
    return checked


if __name__ == "__main__" and sys.argv[1:] == ["self-test"]:
    print(reduced_width(), "reduced-width pairs checked")
