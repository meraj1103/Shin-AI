"""
test_advanced_logic_and_personality.py — Comprehensive tests for Shin's Advanced Calculations,
Logic, Unit Conversions, Date Reasoning, and Living Personality
"""

import sys
import os
from pathlib import Path
import pytest

_SHIN_DIR = Path(__file__).resolve().parent.parent
if str(_SHIN_DIR) not in sys.path:
    sys.path.insert(0, str(_SHIN_DIR))
_CORE_DIR = _SHIN_DIR / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from nlp import parse_intent, enforce_female_grammar
from commands import dispatch
import calculator
import personality


class TestAdvancedCalculations:
    def test_basic_arithmetic(self):
        res = parse_intent("calculate 25 times 4")
        assert res["intent"] == "calculate"
        ans = dispatch(res)
        assert "100" in ans

    def test_power_and_roots(self):
        res = parse_intent("calculate 2 to the power 8")
        ans = dispatch(res)
        assert "256" in ans

        res_sqrt = parse_intent("sqrt of 144")
        ans_sqrt = dispatch(res_sqrt)
        assert "12" in ans_sqrt

        res_cbrt = parse_intent("cube root of 125")
        ans_cbrt = dispatch(res_cbrt)
        assert "5" in ans_cbrt

    def test_trigonometry(self):
        res = parse_intent("sin of 90 degrees")
        ans = dispatch(res)
        assert "sin(90°) = 1" in ans

    def test_percentages_and_discounts(self):
        res = parse_intent("20% discount on 2500")
        assert res["intent"] == "calculate"
        ans = dispatch(res)
        assert "2,000" in ans and "500" in ans

        res_tax = parse_intent("18% gst on 1500")
        ans_tax = dispatch(res_tax)
        assert "270" in ans_tax and "1,770" in ans_tax

    def test_split_bill_and_tips(self):
        res = parse_intent("split 2400 between 4 people with 10% tip")
        assert res["intent"] == "calculate"
        ans = dispatch(res)
        assert "660" in ans  # (2400 + 240) / 4 = 660

    def test_multipliers_and_fractions(self):
        res = parse_intent("half of 480")
        assert res["intent"] == "calculate"
        ans = dispatch(res)
        assert "240" in ans

        res_q = parse_intent("quarter of 200")
        ans_q = dispatch(res_q)
        assert "50" in ans_q

    def test_statistics(self):
        res = parse_intent("average of 10, 20, 30")
        assert res["intent"] == "calculate"
        ans = dispatch(res)
        assert "20" in ans

        res_sum = parse_intent("sum of 15, 25, 40")
        ans_sum = dispatch(res_sum)
        assert "80" in ans_sum

    def test_factorial(self):
        res = parse_intent("factorial of 5")
        assert res["intent"] == "calculate"
        ans = dispatch(res)
        assert "120" in ans


class TestUniversalUnitConverter:
    def test_length_conversion(self):
        res = dispatch({"intent": "convert", "args": {"value": 10, "from_unit": "km", "to_unit": "miles"}})
        assert "6.21371" in res

        res_ft = dispatch({"intent": "convert", "args": {"value": 1, "from_unit": "meter", "to_unit": "feet"}})
        assert "3.28084" in res_ft

    def test_temperature_conversion(self):
        res = dispatch({"intent": "convert", "args": {"value": 100, "from_unit": "celsius", "to_unit": "fahrenheit"}})
        assert "212" in res

        res_c = dispatch({"intent": "convert", "args": {"value": 32, "from_unit": "fahrenheit", "to_unit": "celsius"}})
        assert "0" in res_c

    def test_mass_conversion(self):
        res = dispatch({"intent": "convert", "args": {"value": 5, "from_unit": "kg", "to_unit": "pounds"}})
        assert "11.0231" in res

    def test_digital_storage_conversion(self):
        res = dispatch({"intent": "convert", "args": {"value": 1024, "from_unit": "mb", "to_unit": "gb"}})
        assert "1 gb" in res.lower()

    def test_currency_conversion(self):
        res = dispatch({"intent": "convert", "args": {"value": 100, "from_unit": "USD", "to_unit": "INR"}})
        assert "INR" in res


class TestDateAndTemporalReasoning:
    def test_days_until_event(self):
        res = parse_intent("how many days until Christmas")
        assert res["intent"] == "date_reasoning"
        ans = dispatch(res)
        assert "Christmas" in ans and "days" in ans

    def test_historical_day_of_week(self):
        res = parse_intent("what day was 15 August 1947")
        assert res["intent"] == "date_reasoning"
        ans = dispatch(res)
        assert "Friday" in ans

    def test_relative_date_delta(self):
        res = parse_intent("what is the date after 45 days")
        assert res["intent"] == "date_reasoning"
        ans = dispatch(res)
        assert "45 days from today will be" in ans

    def test_international_world_time(self):
        res = parse_intent("what time is it in Tokyo")
        assert res["intent"] == "date_reasoning"
        ans = dispatch(res)
        assert "In Tokyo" in ans


class TestPersonalityAndGrammar:
    def test_female_grammar(self):
        assert enforce_female_grammar("Main samajh gaya.") == "Main samajh gayi."
        assert enforce_female_grammar("Main karta hoon.") == "Main karti hoon."
        assert enforce_female_grammar("Main bataunga.") == "Main bataungi."

    def test_no_masculine_slips_in_pools(self):
        for pool_name, phrases in personality._POOLS.items():
            for p in phrases:
                low = p.lower()
                assert "karta hoon" not in low, f"Found 'karta hoon' in pool '{pool_name}': {p}"
                assert "bolta hoon" not in low, f"Found 'bolta hoon' in pool '{pool_name}': {p}"
                assert "samajhta hoon" not in low, f"Found 'samajhta hoon' in pool '{pool_name}': {p}"

