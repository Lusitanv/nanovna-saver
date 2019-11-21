#  NanoVNASaver
#  A python program to view and export Touchstone data from a NanoVNA
#  Copyright (C) 2019.  Rune B. Broberg
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
import sys
import unittest

# Import targets to be tested
from NanoVNASaver.Touchstone import Options, Touchstone

class TestTouchstoneOptions(unittest.TestCase):
    def setUp(self):
        self.opts = Options()

    def test_defaults(self):
        self.assertEqual(self.opts.unit, "ghz")
        self.assertEqual(self.opts.parameter, "s")
        self.assertEqual(self.opts.format, "ma")
        self.assertEqual(self.opts.resistance, 50)
        self.assertEqual(self.opts.factor, 1000000000)
        self.assertEqual(str(self.opts), "# GHZ S MA R 50")

    def test_parse(self):
        self.assertRaisesRegex(
            TypeError, "Not an option line:",
            self.opts.parse, "")
        self.assertRaisesRegex(
            TypeError, "Not an option line: !",
            self.opts.parse, "!")
        self.assertRaisesRegex(
            TypeError, "Illegal option line: # ILLEGAL",
            self.opts.parse, "# ILLEGAL")
        self.assertRaisesRegex(
            TypeError, "Illegal option line: # GHz mhz",
            self.opts.parse, "# GHz mhz")
        self.opts.parse('# khz')
        self.assertEqual(str(self.opts), "# KHZ S MA R 50")
        self.assertEqual(self.opts.factor, 1000)
        self.opts.parse('# r 123 ri hz y')
        self.assertEqual(str(self.opts), "# HZ Y RI R 123")
        self.assertEqual(self.opts.factor, 1)

class TestTouchstoneTouchstone(unittest.TestCase):

    def test_load(self):
        ts = Touchstone("./test/data/valid.s1p")
        ts.load()
        self.assertEqual(str(ts.opts), "# HZ S RI R 50")
        self.assertEqual(len(ts.s11data), 1010)
        self.assertEqual(len(ts.s21data), 0)

        ts = Touchstone("./test/data/valid.s2p")
        ts.load()
        self.assertEqual(str(ts.opts), "# HZ S RI R 50")
        self.assertEqual(len(ts.s11data), 1020)
        self.assertEqual(len(ts.s21data), 1020)
        self.assertEqual(len(ts.s12data), 1020)
        self.assertEqual(len(ts.s22data), 1020)
        self.assertIn("! Vector Network Analyzer VNA R2", ts.comments)

if __name__ == '__main__':
    unittest.main(verbosity=2)
