#coding: utf-8

import sys


class drawer(object):
    bar_length = 60

    def __init__(self, total_count):
        self.total_count = total_count
        self.prev_per = None
        self.bar_picture = ''.join(
            ('|' if i % (self.bar_length / 2) == 0 else \
            '+' if i % (self.bar_length / 10) == 0 else \
            '-') \
            for i in range(1, self.bar_length))

    def progress(self, count):
        if count < 0: count = 0
        if count > self.total_count: count = self.total_count

        per = count * 100.0 / self.total_count
        if not (count == self.total_count or self.prev_per is None or per >= self.prev_per + 0.1):
            return
        self.prev_per = per
        perb = int(count * self.bar_length / self.total_count)
        sys.stderr.write('\r%4.1f%% |%s%s|' % (per, '#' * perb, self.bar_picture[perb:]))

    def done(self):
        if self.prev_per is not None:
            sys.stderr.write('\r%s\r' % (' ' * (9 + self.bar_length)))

    def __enter__(self):
        return self.progress

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.done()


if __name__ == '__main__':
    import time

    total_count = 45

    sys.stderr.write("START!\n")
    with drawer(total_count) as progress:
        for c in range(0, total_count + 1):
            time.sleep(0.05)
            progress(c)
    sys.stderr.write("DONE.\n")
