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

    def test_basicIntegerValues(self):
        # simple well-formed integers with no trailing zeros. Most importantly
        # there is no loss of accuracy in the result. Returned values are not
        # truncated if result would lose meaningful data.
        '''
        Original Behavior:
        self.assertEqual(rft.formatSweepFrequency(1), '1Hz')
        self.assertEqual(rft.formatSweepFrequency(12), '12Hz')
        self.assertEqual(rft.formatSweepFrequency(123), '123Hz')
        self.assertEqual(rft.formatSweepFrequency(1234), '1.234kHz')
        self.assertEqual(rft.formatSweepFrequency(12345), '12.345kHz')
        self.assertEqual(rft.formatSweepFrequency(123456), '123.456kHz')
        self.assertEqual(rft.formatSweepFrequency(1234567), '1.234567MHz')
        self.assertEqual(rft.formatSweepFrequency(12345678), '12.345678MHz')
        self.assertEqual(rft.formatSweepFrequency(123456789), '123.456789MHz')
        '''
        # New Behavior: results in loss of accuracy again.
        self.assertEqual(rft.formatSweepFrequency(1), '1.0000Hz')
        self.assertEqual(rft.formatSweepFrequency(12), '12.000Hz')
        self.assertEqual(rft.formatSweepFrequency(123), '123.00Hz')
        self.assertEqual(rft.formatSweepFrequency(1234), '1.2340kHz')
        self.assertEqual(rft.formatSweepFrequency(12345), '12.345kHz')
        self.assertEqual(rft.formatSweepFrequency(123456), '123.46kHz')
        self.assertEqual(rft.formatSweepFrequency(1234567), '1.2346MHz')
        self.assertEqual(rft.formatSweepFrequency(12345678), '12.346MHz')
        self.assertEqual(rft.formatSweepFrequency(123456789), '123.46MHz')

    '''
    def test_defaultMinDigits(self):
        # simple integers with trailing zeros.
        # DEFAULT behavior retains 2 digits after the period, mindigits=2.
        self.assertEqual(rft.formatSweepFrequency(1000), '1.00kHz')
        self.assertEqual(rft.formatSweepFrequency(10000), '10.00kHz')
        self.assertEqual(rft.formatSweepFrequency(100000), '100.00kHz')
        self.assertEqual(rft.formatSweepFrequency(1000000), '1.00MHz')
    
    def test_nonDefaultMinDigits(self):
        # simple integers with trailing zeros. setting mindigit value to something
        # other than default, where trailing zeros >= mindigits, the number of
        # zeros shown is equal to mindigits value.
        self.assertEqual(rft.formatSweepFrequency(1000000, mindigits=0), '1MHz')
        self.assertEqual(rft.formatSweepFrequency(1000000, mindigits=1), '1.0MHz')
        self.assertEqual(rft.formatSweepFrequency(1000000, mindigits=3), '1.000MHz')
        self.assertEqual(rft.formatSweepFrequency(10000000, mindigits=4), '10.0000MHz')
        self.assertEqual(rft.formatSweepFrequency(100000000, mindigits=5), '100.00000MHz')
        self.assertEqual(rft.formatSweepFrequency(1000000000, mindigits=6), '1.000000GHz')
        # where trailing zeros < mindigits, only available zeros are shown, if the
        # result includes no decimal places (i.e. Hz values).
        self.assertEqual(rft.formatSweepFrequency(1, mindigits=4), '1Hz')
        self.assertEqual(rft.formatSweepFrequency(10, mindigits=4), '10Hz')
        self.assertEqual(rft.formatSweepFrequency(100, mindigits=4), '100Hz')
        # but where a decimal exists, and mindigits > number of available zeroes,
        # this results in extra zeroes being padded into result, even into sub-Hz
        # resolution. This is not useful for this application.
        # TODO: Consider post-processing result for maxdigits based on SI unit.
        self.assertEqual(rft.formatSweepFrequency(1000, mindigits=5), '1.00000kHz')
        self.assertEqual(rft.formatSweepFrequency(1000, mindigits=10), '1.0000000000kHz')
    '''

if __name__ == '__main__':
    unittest.main(verbosity=2)
