#  NanoVNASaver - a python program to view and export Touchstone data from a NanoVNA
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
from NanoVNASaver import RFTools
rft = RFTools.RFTools()

class TestCases(unittest.TestCase):

    def test_basicSIUnits(self):
        # simple well-formed integers with correct SI units
        self.assertEqual(rft.parseFrequency('123Hz'), 123)
        self.assertEqual(rft.parseFrequency('123456Hz'), 123456)
        self.assertEqual(rft.parseFrequency('123kHz'), 123000)
        self.assertEqual(rft.parseFrequency('123456kHz'), 123456000)
        self.assertEqual(rft.parseFrequency('123MHz'), 123000000)
        self.assertEqual(rft.parseFrequency('123456MHz'), 123456000000)
        self.assertEqual(rft.parseFrequency('123GHz'), 123000000000)
        self.assertEqual(rft.parseFrequency('123456GHz'), 123456000000000)

    def test_commonMistakeKHz_vs_kHz(self):
        # some poorly formatted values that still work as expected
        self.assertEqual(rft.parseFrequency('123kHz'), 123000)
        self.assertEqual(rft.parseFrequency('123KHz'), 123000)

    def test_illegalInputValues(self):
        # poorly formatted inputs that are identified as illegal
        self.assertEqual(rft.parseFrequency('Junk'), -1)
        self.assertEqual(rft.parseFrequency('Garbage'), -1)
        self.assertEqual(rft.parseFrequency('123.Junk'), -1)

    def test_missingDigitsAfterPeriod(self):
        # some poorly formatted values that still work as expected
        self.assertEqual(rft.parseFrequency('123.'), 123)
        self.assertEqual(rft.parseFrequency('123.Hz'), 123)
        self.assertEqual(rft.parseFrequency('123.kHz'), 123000)
        self.assertEqual(rft.parseFrequency('123.MHz'), 123000000)
        self.assertEqual(rft.parseFrequency('123.GHz'), 123000000000)

    def test_unusualSIUnits(self):
        #######################################################################
        # Current behavior: unusual SI values that are legal, but inappropriate
        # for this application provide unexpected outputs. This behavior is
        # based on the FULL set of SI prefixes defined in SITools (below).
        #PREFIXES = ("y", "z", "a", "f", "p", "n", "µ", "m",
        #            "", "k", "M", "G", "T", "P", "E", "Z", "Y")
        #######################################################################
        self.assertEqual(rft.parseFrequency('123EHz'), 123000000000000000000)
        self.assertEqual(rft.parseFrequency('123PHz'), 123000000000000000)
        self.assertEqual(rft.parseFrequency('123THz'), 123000000000000)
        self.assertEqual(rft.parseFrequency('123YHz'), 122999999999999998473273344)
        self.assertEqual(rft.parseFrequency('123ZHz'), 123000000000000002097152)
        self.assertEqual(rft.parseFrequency('123aHz'), 0)
        self.assertEqual(rft.parseFrequency('123fHz'), 0)
        self.assertEqual(rft.parseFrequency('123mHz'), 0)
        self.assertEqual(rft.parseFrequency('123nHz'), 0)
        self.assertEqual(rft.parseFrequency('123pHz'), 0)
        self.assertEqual(rft.parseFrequency('123yHz'), 0)
        self.assertEqual(rft.parseFrequency('123zHz'), 0)

        #######################################################################
        # Recommend: Reducing the legal SI values defined in SITools (see
        # below). This makes it more likely that typos will result in a -1
        # failure code instead of being interpreted as an SI unit.
        # PREFIXES = ("", "k", "M", "G")
        #######################################################################
        '''
        self.assertEqual(rft.parseFrequency('123EHz'), -1)
        self.assertEqual(rft.parseFrequency('123PHz'), -1)
        self.assertEqual(rft.parseFrequency('123THz'), -1)
        self.assertEqual(rft.parseFrequency('123YHz'), -1)
        self.assertEqual(rft.parseFrequency('123ZHz'), -1)
        self.assertEqual(rft.parseFrequency('123aHz'), -1)
        self.assertEqual(rft.parseFrequency('123fHz'), -1)
        self.assertEqual(rft.parseFrequency('123mHz'), -1)
        self.assertEqual(rft.parseFrequency('123nHz'), -1)
        self.assertEqual(rft.parseFrequency('123pHz'), -1)
        self.assertEqual(rft.parseFrequency('123yHz'), -1)
        self.assertEqual(rft.parseFrequency('123zHz'), -1)
    '''

    def test_partialHzText(self):
        #######################################################################
        # The current behavior for accidentally missing the H in Hz, is a
        # detection of 'z' SI unit (zepto = 10^-21), which then rounded to 0.
        # After reduction of legal SI values in SITools, this would return
        # a -1 failure code instead.
        #######################################################################
        self.assertEqual(rft.parseFrequency('123z'), 0)
        self.assertEqual(rft.parseFrequency('123.z'), 0)
        self.assertEqual(rft.parseFrequency('1.23z'), 0)
        '''
        self.assertEqual(rft.parseFrequency('123z'), -1)
        self.assertEqual(rft.parseFrequency('123.z'), -1)
        self.assertEqual(rft.parseFrequency('1.23z'), -1)
        '''

    def test_basicExponentialNotation(self):
        # check basic exponential notation
        self.assertEqual(rft.parseFrequency('123e3'), 123000)
        self.assertEqual(rft.parseFrequency('123e6'), 123000000)
        self.assertEqual(rft.parseFrequency('123e9'), 123000000000)
        self.assertEqual(rft.parseFrequency('123e4'), 1230000)
        self.assertEqual(rft.parseFrequency('123e12'), 123000000000000)
        self.assertEqual(rft.parseFrequency('123e18'), 123000000000000000000)

    def test_negativeExponentialNotation(self):
        # negative exponential values resulting in N < 0, return 0
        self.assertEqual(rft.parseFrequency('123e-3'), 0)
        self.assertEqual(rft.parseFrequency('1234e-4'), 0)
        self.assertEqual(rft.parseFrequency('12345e-5'), 0)
        self.assertEqual(rft.parseFrequency('12345678e-8'), 0)
        # negative exponential values resulting in N > 0, return N
        self.assertEqual(rft.parseFrequency('100000e-5'), 1)
        self.assertEqual(rft.parseFrequency('100000e-4'), 10)
        self.assertEqual(rft.parseFrequency('100000e-3'), 100)
        self.assertEqual(rft.parseFrequency('100000e-2'), 1000)
        self.assertEqual(rft.parseFrequency('100000e-1'), 10000)

    def test_multiplePeriods(self):
        # multiple periods are properly detected as bad
        self.assertEqual(rft.parseFrequency('123..Hz'), -1)
        self.assertEqual(rft.parseFrequency('123...Hz'), -1)
        self.assertEqual(rft.parseFrequency('123....Hz'), -1)
        self.assertEqual(rft.parseFrequency('1.23.Hz'), -1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
