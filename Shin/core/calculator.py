"""
calculator.py — Advanced Calculation, Unit Conversion, Date Reasoning & Logic Engine for Shin
=============================================================================================
Provides deterministic, high-precision evaluation for:
  1. Arithmetic, Algebra, Scientific Math, Trigonometry, Statistics
  2. Financial Math (Discounts, GST/Taxes, Loan EMI, Bill Splitting & Tips)
  3. Multi-Category Unit Conversions (Length, Mass, Temp, Data, Speed, Area, Volume)
  4. Real-time & Offline Currency Conversions (USD, INR, EUR, GBP, JPY, CAD, AUD, etc.)
  5. Date, Time & Calendar Calculations (Days until, date deltas, day of week, timezones)
  6. Natural Language Math & Logic Problem Solver
"""

from __future__ import annotations

import ast
from datetime import datetime, date, timedelta, timezone
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Try importing SymPy for symbolic / algebraic precision
try:
    import sympy as _sp
    _HAS_SYMPY = True
except ImportError:
    _sp = None
    _HAS_SYMPY = False

# Try importing dateutil for natural relative date parsing
try:
    import dateutil.parser as _date_parser
    from dateutil.relativedelta import relativedelta as _relativedelta
    _HAS_DATEUTIL = True
except ImportError:
    _date_parser = None
    _relativedelta = None
    _HAS_DATEUTIL = False


# ============================================================================
# BLOCK 1: NUMBER FORMATTING & SAFE AST EVALUATION
# ============================================================================

def format_number(val: Union[int, float]) -> str:
    """Format numeric outputs cleanly without trailing float noise."""
    if isinstance(val, (int, float)):
        if math.isinf(val):
            return "infinity"
        if math.isnan(val):
            return "undefined"
        if abs(val - round(val)) < 1e-9:
            return f"{int(round(val)):,}"
        # Keep up to 6 significant figures
        formatted = f"{val:.6g}"
        if "e" not in formatted and "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return formatted
    return str(val)


# ============================================================================
# BLOCK 2: ADVANCED MATH & FINANCIAL REASONING
# ============================================================================

_SAFE_MATH_CONSTANTS = {
    'pi': math.pi,
    'e': math.e,
    'tau': math.tau,
}

_SAFE_MATH_FUNCTIONS = {
    'sqrt': math.sqrt,
    'cbrt': lambda x: math.pow(x, 1/3) if x >= 0 else -math.pow(-x, 1/3),
    'abs': abs,
    'round': round,
    'floor': math.floor,
    'ceil': math.ceil,
    'log': math.log10,
    'log10': math.log10,
    'log2': math.log2,
    'ln': math.log,
    'sin': lambda x: math.sin(math.radians(x)),
    'cos': lambda x: math.cos(math.radians(x)),
    'tan': lambda x: math.tan(math.radians(x)),
    'asin': lambda x: math.degrees(math.asin(x)),
    'acos': lambda x: math.degrees(math.acos(x)),
    'atan': lambda x: math.degrees(math.atan(x)),
    'radians': math.radians,
    'degrees': math.degrees,
    'factorial': math.factorial,
    'fact': math.factorial,
    'gcd': math.gcd,
    'lcm': getattr(math, 'lcm', lambda a, b: abs(a * b) // math.gcd(a, b)),
    'hypot': math.hypot,
}


def _safe_eval_ast(expr: str) -> float:
    """Evaluate clean mathematical expressions securely with AST parsing."""
    tree = ast.parse(expr.strip(), mode='eval')

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            l, r = _eval(node.left), _eval(node.right)
            ops = {
                ast.Add: lambda a, b: a + b,
                ast.Sub: lambda a, b: a - b,
                ast.Mult: lambda a, b: a * b,
                ast.Div: lambda a, b: a / b,
                ast.FloorDiv: lambda a, b: a // b,
                ast.Mod: lambda a, b: a % b,
                ast.Pow: lambda a, b: a ** b,
            }
            op_fn = ops.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
            return op_fn(l, r)
        if isinstance(node, ast.UnaryOp):
            val = _eval(node.operand)
            if isinstance(node.op, ast.USub):
                return -val
            if isinstance(node.op, ast.UAdd):
                return val
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fn = _SAFE_MATH_FUNCTIONS.get(node.func.id.lower())
            if not fn:
                raise ValueError(f"Unsupported function: {node.func.id}")
            return fn(*[_eval(a) for a in node.args])
        if isinstance(node, ast.Name) and node.id.lower() in _SAFE_MATH_CONSTANTS:
            return _SAFE_MATH_CONSTANTS[node.id.lower()]
        raise ValueError(f"Unsupported AST node: {ast.dump(node)}")

    return _eval(tree)


def evaluate_expression(expression: str) -> str:
    """
    Evaluate math, percentages, discounts, GST/taxes, statistics, and word math.
    Returns natural, spoken Hinglish/English output.
    """
    raw = expression.strip()
    expr = raw.lower()
    if not expr:
        return "Please give me a math expression or calculation to solve."

    # 1. Discount / Sale calculation: "20% discount on 2500" or "25 percent off 1200"
    disc_m = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:%|percent)\s+(?:discount\s+(?:on|for)|off)\s+(?:rs\.?|inr|\$)?\s*(\d+(?:\.\d+)?)',
        expr
    )
    if disc_m:
        rate = float(disc_m.group(1))
        original = float(disc_m.group(2))
        discount_amount = original * (rate / 100.0)
        final_price = original - discount_amount
        return (
            f"{format_number(rate)}% off {format_number(original)} is {format_number(final_price)} "
            f"(You save {format_number(discount_amount)})."
        )

    # 2. GST / Tax calculation: "18% gst on 1500" or "5 percent tax on 500"
    tax_m = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:%|percent)\s+(?:gst|tax|vat)\s+(?:on|for)\s+(?:rs\.?|inr|\$)?\s*(\d+(?:\.\d+)?)',
        expr
    )
    if tax_m:
        rate = float(tax_m.group(1))
        base = float(tax_m.group(2))
        tax_val = base * (rate / 100.0)
        total = base + tax_val
        return (
            f"{format_number(rate)}% tax on {format_number(base)} is {format_number(tax_val)}. "
            f"Total amount is {format_number(total)}."
        )

    # 3. Tip & Split Bill: "split 2400 among 4 people with 10% tip"
    split_m = re.search(
        r'split\s+(?:rs\.?|inr|\$)?\s*(\d+(?:\.\d+)?)\s+(?:between|among)\s+(\d+)\s*(?:people|friends|persons)?'
        r'(?:\s+with\s+(\d+(?:\.\d+)?)\s*(?:%|percent)\s+tip)?',
        expr
    )
    if split_m:
        bill = float(split_m.group(1))
        people = int(split_m.group(2))
        tip_pct = float(split_m.group(3)) if split_m.group(3) else 0.0
        if people <= 0:
            return "Number of people must be greater than zero!"
        tip_amount = bill * (tip_pct / 100.0)
        total_bill = bill + tip_amount
        per_person = total_bill / people
        tip_text = f" including {format_number(tip_pct)}% tip ({format_number(tip_amount)})" if tip_pct > 0 else ""
        return (
            f"For a bill of {format_number(bill)}{tip_text}, split among {people} people, "
            f"each person pays {format_number(per_person)} (Total: {format_number(total_bill)})."
        )

    # 4. Loan EMI Calculation: "emi for 500000 at 9 percent for 5 years"
    emi_m = re.search(
        r'emi\s+(?:for\s+)?(?:loan\s+of\s+)?(?:rs\.?|inr|\$)?\s*(\d+(?:\.\d+)?)\s+(?:at\s+)?(\d+(?:\.\d+)?)\s*(?:%|percent)?\s*(?:interest\s+)?(?:for\s+)?(\d+(?:\.\d+)?)\s*(years?|months?)',
        expr
    )
    if emi_m:
        principal = float(emi_m.group(1))
        annual_rate = float(emi_m.group(2))
        tenure_val = float(emi_m.group(3))
        tenure_unit = emi_m.group(4)
        n_months = int(tenure_val * 12) if "year" in tenure_unit else int(tenure_val)
        if n_months <= 0:
            return "Tenure must be at least 1 month."
        r = (annual_rate / 12.0) / 100.0
        if r == 0:
            emi = principal / n_months
        else:
            emi = (principal * r * ((1 + r) ** n_months)) / (((1 + r) ** n_months) - 1)
        total_payment = emi * n_months
        total_interest = total_payment - principal
        return (
            f"Monthly EMI for {format_number(principal)} at {format_number(annual_rate)}% for {n_months} months "
            f"is {format_number(round(emi, 2))}. Total interest payable: {format_number(round(total_interest, 2))}."
        )

    # 5. List Statistics: "average of 12, 18, 24, 30" | "median of 1, 5, 2, 8, 7" | "sum of 15, 25, 40"
    stat_m = re.search(
        r'^(average|mean|median|sum|minimum|min|maximum|max)\s+of\s+([0-9\s,\.\-]+)$',
        expr
    )
    if stat_m:
        stat_type = stat_m.group(1)
        numbers = [float(x.strip()) for x in re.split(r'[, ]+', stat_m.group(2).strip()) if x.strip()]
        if numbers:
            if stat_type in ("average", "mean"):
                res = sum(numbers) / len(numbers)
                return f"The average of the {len(numbers)} numbers is {format_number(res)}."
            if stat_type == "median":
                s = sorted(numbers)
                mid = len(s) // 2
                res = s[mid] if len(s) % 2 != 0 else (s[mid - 1] + s[mid]) / 2.0
                return f"The median is {format_number(res)}."
            if stat_type == "sum":
                return f"The sum is {format_number(sum(numbers))}."
            if stat_type in ("min", "minimum"):
                return f"The minimum is {format_number(min(numbers))}."
            if stat_type in ("max", "maximum"):
                return f"The maximum is {format_number(max(numbers))}."

    # 6. Standard Percentage: "15% of 200" or "what is 25 percent of 80"
    pct_m = re.match(
        r'^(?:what\s+is\s+)?(\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(\d+(?:\.\d+)?)$',
        expr
    )
    if pct_m:
        pct = float(pct_m.group(1))
        num = float(pct_m.group(2))
        res = (pct / 100.0) * num
        return f"{format_number(pct)}% of {format_number(num)} is {format_number(res)}."

    # 7. Natural language fractions & multipliers:
    # "half of 480" | "quarter of 200" | "one third of 90" | "double of 45"
    mult_m = re.match(
        r'^(?:what\s+is\s+)?(half|quarter|one\s+third|one\s+fourth|double|triple)\s+of\s+(\d+(?:\.\d+)?)$',
        expr
    )
    if mult_m:
        word, num_val = mult_m.group(1), float(mult_m.group(2))
        factors = {
            "half": 0.5,
            "quarter": 0.25,
            "one fourth": 0.25,
            "one third": 1/3,
            "double": 2.0,
            "triple": 3.0,
        }
        res = num_val * factors[word]
        return f"{word.capitalize()} of {format_number(num_val)} is {format_number(res)}."

    # 8. Factorial: "5 factorial" or "factorial of 6"
    fact_m = re.match(r'^(?:(?:what\s+is\s+)?factorial\s+of\s+(\d+)|(\d+)\s*!|(\d+)\s+factorial)$', expr)
    if fact_m:
        n = int(fact_m.group(1) or fact_m.group(2) or fact_m.group(3))
        if n > 170:
            return "Factorial of numbers above 170 overflows standard floating point limits!"
        res = math.factorial(n)
        return f"{n}! is {format_number(res)}."

    # 9. Square root / Cube root
    root_m = re.match(r'^(?:square\s+root|sqrt)\s+of\s+(\d+(?:\.\d+)?)$', expr)
    if root_m:
        n = float(root_m.group(1))
        return f"Square root of {format_number(n)} is {format_number(math.sqrt(n))}."

    cbrt_m = re.match(r'^(?:cube\s+root|cbrt)\s+of\s+(\d+(?:\.\d+)?)$', expr)
    if cbrt_m:
        n = float(cbrt_m.group(1))
        res = math.pow(n, 1/3)
        return f"Cube root of {format_number(n)} is {format_number(res)}."

    # 10. Trigonometry with degrees: "sin of 90 degrees" | "cos 45" | "tan of 30"
    trig_m = re.match(r'^(sin|cos|tan)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:degrees?)?$', expr)
    if trig_m:
        fn_name, angle = trig_m.group(1), float(trig_m.group(2))
        fn = {"sin": math.sin, "cos": math.cos, "tan": math.tan}[fn_name]
        res = fn(math.radians(angle))
        return f"{fn_name}({format_number(angle)}°) = {format_number(res)}."

    # Normalize Natural Language Math Tokens to Standard Symbols
    normalized = expr
    replacements = [
        (r'\bmultiplied\s+by\b', '*'),
        (r'\btimes\b', '*'),
        (r'\binto\b', '*'),
        (r'\bdivided\s+by\b', '/'),
        (r'\bover\b', '/'),
        (r'\bplus\b', '+'),
        (r'\badd\b', '+'),
        (r'\bminus\b', '-'),
        (r'\bsubtract\b', '-'),
        (r'\bto\s+the\s+power\s+(?:of\s+)?\b', '**'),
        (r'\braised\s+to\s+(?:the\s+power\s+of\s+)?\b', '**'),
        (r'\bpower\b', '**'),
        (r'\bsquared\b', '**2'),
        (r'\bcubed\b', '**3'),
        (r'×', '*'),
        (r'÷', '/'),
        (r'\^', '**'),
    ]
    for pat, rep in replacements:
        normalized = re.sub(pat, rep, normalized, flags=re.IGNORECASE)

    # Clean leading "what is", "calculate", "solve", etc.
    normalized = re.sub(r'^(?:what\s+is|what\'s|calculate|compute|solve|work\s+out)\s+', '', normalized).strip()

    # Balance any unclosed parentheses
    open_count = normalized.count('(')
    close_count = normalized.count(')')
    if open_count > close_count:
        normalized += ')' * (open_count - close_count)

    # Attempt safe AST evaluation first
    try:
        val = _safe_eval_ast(normalized)
        return f"The result is {format_number(val)}."
    except ZeroDivisionError:
        return "I can't divide by zero! That leads to infinity."
    except Exception as ast_exc:
        logger.debug("AST eval failed for %r (%s), trying SymPy fallback.", normalized, ast_exc)

    # SymPy fallback for symbolic solving, algebra or complex equations
    if _HAS_SYMPY:
        try:
            sym_expr = _sp.sympify(normalized)
            res = sym_expr.evalf()
            if res.is_number:
                return f"The result is {format_number(float(res))}."
            simplified = _sp.simplify(sym_expr)
            return f"The simplified expression is {simplified}."
        except Exception as sym_exc:
            logger.debug("SymPy eval failed for %r: %s", normalized, sym_exc)

    return "Sorry, I couldn't evaluate that math expression. Please rephrase it."


# ============================================================================
# BLOCK 3: UNIT CONVERSIONS & COMPREHENSIVE CONVERTER
# ============================================================================

# Multi-dimensional Conversion Factors (to Base Unit):
# Base Units: Length -> Meter | Mass -> Gram | Volume -> Liter | Data -> Byte | Speed -> m/s | Time -> Second | Area -> m²
_UNIT_CATEGORIES: Dict[str, Dict[str, float]] = {
    "length": {
        "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
        "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0, "kilometre": 1000.0,
        "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01, "centimetre": 0.01,
        "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
        "mile": 1609.344, "miles": 1609.344,
        "yard": 0.9144, "yards": 0.9144, "yd": 0.9144,
        "foot": 0.3048, "feet": 0.3048, "ft": 0.3048,
        "inch": 0.0254, "inches": 0.0254, "in": 0.0254,
        "nautical mile": 1852.0, "nautical miles": 1852.0,
    },
    "mass": {
        "g": 1.0, "gram": 1.0, "grams": 1.0,
        "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0, "kilos": 1000.0,
        "mg": 0.001, "milligram": 0.001, "milligrams": 0.001,
        "pound": 453.59237, "pounds": 453.59237, "lb": 453.59237, "lbs": 453.59237,
        "ounce": 28.349523, "ounces": 28.349523, "oz": 28.349523,
        "ton": 1_000_000.0, "tons": 1_000_000.0, "tonne": 1_000_000.0, "tonnes": 1_000_000.0,
        "quintal": 100_000.0, "quintals": 100_000.0,
    },
    "volume": {
        "l": 1.0, "liter": 1.0, "liters": 1.0, "litre": 1.0, "litres": 1.0,
        "ml": 0.001, "milliliter": 0.001, "milliliters": 0.001,
        "gallon": 3.785411784, "gallons": 3.785411784, "gal": 3.785411784,
        "fluid ounce": 0.0295735, "fluid ounces": 0.0295735, "fl oz": 0.0295735,
        "cup": 0.236588, "cups": 0.236588,
        "tablespoon": 0.0147868, "tablespoons": 0.0147868, "tbsp": 0.0147868,
        "teaspoon": 0.00492892, "teaspoons": 0.00492892, "tsp": 0.00492892,
    },
    "data": {
        "b": 1.0, "byte": 1.0, "bytes": 1.0,
        "bit": 0.125, "bits": 0.125,
        "kb": 1024.0, "kilobyte": 1024.0, "kilobytes": 1024.0,
        "mb": 1024.0 ** 2, "megabyte": 1024.0 ** 2, "megabytes": 1024.0 ** 2,
        "gb": 1024.0 ** 3, "gigabyte": 1024.0 ** 3, "gigabytes": 1024.0 ** 3,
        "tb": 1024.0 ** 4, "terabyte": 1024.0 ** 4, "terabytes": 1024.0 ** 4,
        "pb": 1024.0 ** 5, "petabyte": 1024.0 ** 5, "petabytes": 1024.0 ** 5,
    },
    "speed": {
        "m/s": 1.0, "mps": 1.0, "meter per second": 1.0,
        "km/h": 1 / 3.6, "kph": 1 / 3.6, "kmh": 1 / 3.6, "kilometer per hour": 1 / 3.6,
        "mph": 0.44704, "mile per hour": 0.44704, "miles per hour": 0.44704,
        "knot": 0.514444, "knots": 0.514444,
        "ft/s": 0.3048, "fps": 0.3048, "feet per second": 0.3048,
    },
    "time": {
        "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
        "ms": 0.001, "millisecond": 0.001, "milliseconds": 0.001,
        "min": 60.0, "minute": 60.0, "minutes": 60.0,
        "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
        "day": 86400.0, "days": 86400.0,
        "week": 604800.0, "weeks": 604800.0,
        "month": 2629746.0, "months": 2629746.0,  # ~30.4375 days
        "year": 31556952.0, "years": 31556952.0,  # 365.2425 days
    },
    "area": {
        "sq m": 1.0, "sq meter": 1.0, "square meter": 1.0, "square meters": 1.0,
        "sq km": 1_000_000.0, "square kilometer": 1_000_000.0,
        "sq ft": 0.092903, "sq feet": 0.092903, "square feet": 0.092903, "sqft": 0.092903,
        "sq inch": 0.00064516, "square inch": 0.00064516, "sq inches": 0.00064516,
        "acre": 4046.8564, "acres": 4046.8564,
        "hectare": 10000.0, "hectares": 10000.0,
        "bigha": 2529.285, "bighas": 2529.285,
    }
}

# Offline fallback currency exchange rates relative to 1 USD
_FALLBACK_CURRENCY_RATES = {
    "USD": 1.0,
    "INR": 86.85,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 154.50,
    "CAD": 1.39,
    "AUD": 1.52,
    "AED": 3.67,
    "SGD": 1.34,
    "CNY": 7.23,
    "CHF": 0.88,
}

_CURRENCY_ALIASES = {
    "rupee": "INR", "rupees": "INR", "rs": "INR", "inr": "INR", "₹": "INR",
    "dollar": "USD", "dollars": "USD", "usd": "USD", "$": "USD", "bucks": "USD",
    "euro": "EUR", "euros": "EUR", "eur": "EUR", "€": "EUR",
    "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "£": "GBP",
    "yen": "JPY", "jpy": "JPY", "¥": "JPY",
    "dirham": "AED", "dirhams": "AED", "aed": "AED",
    "cad": "CAD", "canadian dollar": "CAD", "canadian dollars": "CAD",
    "aud": "AUD", "australian dollar": "AUD", "australian dollars": "AUD",
    "sgd": "SGD", "singapore dollar": "SGD",
    "yuan": "CNY", "cny": "CNY",
}


def convert_temperature(value: float, from_u: str, to_u: str) -> Optional[str]:
    """Convert temperatures between Celsius, Fahrenheit, and Kelvin."""
    norm = {
        "celsius": "celsius", "c": "celsius", "centigrade": "celsius",
        "fahrenheit": "fahrenheit", "f": "fahrenheit",
        "kelvin": "kelvin", "k": "kelvin",
    }
    f_norm = norm.get(from_u.lower().strip())
    t_norm = norm.get(to_u.lower().strip())
    if not f_norm or not t_norm:
        return None

    # Convert to Celsius
    if f_norm == "celsius":
        c = value
    elif f_norm == "fahrenheit":
        c = (value - 32) * 5 / 9
    else:  # kelvin
        c = value - 273.15

    # Convert from Celsius to Target
    if t_norm == "celsius":
        res = c
    elif t_norm == "fahrenheit":
        res = c * 9 / 5 + 32
    else:  # kelvin
        res = c + 273.15

    return f"{format_number(value)} {from_u} is {format_number(round(res, 2))} {to_u}."


def convert_currency(value: float, from_curr: str, to_curr: str) -> Optional[str]:
    """Convert currency using live API with reliable offline rate fallback."""
    f_code = _CURRENCY_ALIASES.get(from_curr.lower(), from_curr.upper())
    t_code = _CURRENCY_ALIASES.get(to_curr.lower(), to_curr.upper())

    if f_code not in _FALLBACK_CURRENCY_RATES and t_code not in _FALLBACK_CURRENCY_RATES:
        return None

    # Try live fetch
    rate_found = False
    rate = None
    try:
        import requests
        resp = requests.get(f"https://api.exchangerate-api.com/v4/latest/{f_code}", timeout=4)
        if resp.status_code == 200:
            rates = resp.json().get("rates", {})
            if t_code in rates:
                rate = rates[t_code]
                rate_found = True
    except Exception as exc:
        logger.debug("Live currency exchange fetch failed: %s", exc)

    # Fallback to local rates
    if not rate_found:
        if f_code in _FALLBACK_CURRENCY_RATES and t_code in _FALLBACK_CURRENCY_RATES:
            # f_code -> USD -> t_code
            val_in_usd = value / _FALLBACK_CURRENCY_RATES[f_code]
            converted = val_in_usd * _FALLBACK_CURRENCY_RATES[t_code]
            return (
                f"{format_number(value)} {f_code} is approximately {format_number(round(converted, 2))} {t_code} "
                f"(using estimated baseline exchange rates)."
            )
        return None

    converted = value * rate
    return f"{format_number(value)} {f_code} is {format_number(round(converted, 2))} {t_code}."


def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """Universal converter for physics units, digital storage, and currencies."""
    f_clean = from_unit.strip().lower()
    t_clean = to_unit.strip().lower()

    if not f_clean or not t_clean:
        return "Please specify both units to convert between (e.g. 'convert 5 km to miles')."

    # 1. Temperature check
    t_res = convert_temperature(value, f_clean, t_clean)
    if t_res:
        return t_res

    # 2. Currency check
    c_res = convert_currency(value, f_clean, t_clean)
    if c_res:
        return c_res

    # 3. Categorized physical and digital units
    for category, table in _UNIT_CATEGORIES.items():
        if f_clean in table and t_clean in table:
            # Convert to category base, then to target
            val_in_base = value * table[f_clean]
            res = val_in_base / table[t_clean]
            return f"{format_number(value)} {from_unit} is {format_number(res)} {to_unit}."

    return (
        f"I don't know how to convert from {from_unit} to {to_unit}. "
        "I can convert length, weight, volume, digital storage, speed, time, area, temperature, and major currencies."
    )


# ============================================================================
# BLOCK 4: DATE, TIME & TEMPORAL CALENDAR LOGIC
# ============================================================================

_COMMON_EVENTS = {
    "new year": (1, 1),
    "new year's day": (1, 1),
    "republic day": (1, 26),
    "valentine's day": (2, 14),
    "earth day": (4, 22),
    "independence day": (8, 15),
    "gandhi jayanti": (10, 2),
    "halloween": (10, 31),
    "christmas": (12, 25),
    "christmas day": (12, 25),
    "new year's eve": (12, 31),
}

_CITY_OFFSETS: Dict[str, Tuple[int, int]] = {
    # City/Country: (hours, minutes) relative to UTC
    "london": (0, 0),
    "uk": (0, 0),
    "england": (0, 0),
    "new york": (-5, 0),
    "nyc": (-5, 0),
    "los angeles": (-8, 0),
    "la": (-8, 0),
    "san francisco": (-8, 0),
    "california": (-8, 0),
    "seattle": (-8, 0),
    "chicago": (-6, 0),
    "tokyo": (9, 0),
    "japan": (9, 0),
    "dubai": (4, 0),
    "uae": (4, 0),
    "singapore": (8, 0),
    "sydney": (11, 0),
    "australia": (10, 0),
    "melbourne": (11, 0),
    "paris": (1, 0),
    "france": (1, 0),
    "berlin": (1, 0),
    "germany": (1, 0),
    "toronto": (-5, 0),
    "canada": (-5, 0),
    "delhi": (5, 30),
    "mumbai": (5, 30),
    "bangalore": (5, 30),
    "hyderabad": (5, 30),
    "india": (5, 30),
}


def reason_date_and_time(query: str, now: Optional[datetime] = None) -> str:
    """
    Solve date arithmetic, days until events, day of week, and international time.
    """
    now = now or datetime.now()
    q = query.lower().strip()

    # 1. World Time / Time in [City]: "what time is it in Tokyo" | "time in New York"
    tz_m = re.search(r'\b(?:time\s+in|time\s+at|what\s+time\s+is\s+it\s+in)\s+([a-zA-Z\s]+?)(?:\s*right\s+now|\s*\?)*$', q)
    if tz_m:
        city = tz_m.group(1).strip()
        if city in _CITY_OFFSETS:
            h_off, m_off = _CITY_OFFSETS[city]
            utc_now = datetime.now(timezone.utc)
            delta = timedelta(hours=h_off, minutes=m_off)
            remote_time = utc_now + delta
            time_str = remote_time.strftime("%I:%M %p")
            date_str = remote_time.strftime("%A, %d %B %Y")
            return f"In {city.title()}, the current time is {time_str} on {date_str}."

    # 2. Days until event or date: "how many days until Christmas" | "days until New Year"
    until_m = re.search(r'\b(?:how\s+many\s+days\s+(?:until|left\s+for|before|till)|days\s+to)\s+(.+)$', q)
    if until_m:
        target_name = until_m.group(1).strip().rstrip("?")
        # Check standard annual events
        if target_name in _COMMON_EVENTS:
            m, d = _COMMON_EVENTS[target_name]
            target_date = date(now.year, m, d)
            if target_date < now.date():
                target_date = date(now.year + 1, m, d)
            diff = (target_date - now.date()).days
            if diff == 0:
                return f"Today is {target_name.title()}! Celebrate and enjoy!"
            if diff == 1:
                return f"Tomorrow is {target_name.title()}!"
            return f"There are {diff} days until {target_name.title()} ({target_date.strftime('%B %d, %Y')})."

        # Try parsing target date with dateutil
        if _HAS_DATEUTIL:
            try:
                parsed = _date_parser.parse(target_name, fuzzy=True, default=now)
                target_date = parsed.date()
                if target_date < now.date() and target_date.month >= now.month:
                    target_date = date(now.year + 1, target_date.month, target_date.day)
                diff = (target_date - now.date()).days
                return f"There are {diff} days until {target_date.strftime('%A, %B %d, %Y')}."
            except Exception:
                pass

    # 3. Relative date delta: "what is the date after 45 days" | "date 3 weeks from now" | "in 10 days"
    delta_m = re.search(
        r'(?:(?:date\s+)?(?:in|after)\s+(\d+)\s*(days?|weeks?|months?|years?)|(?:date\s+)?(\d+)\s*(days?|weeks?|months?|years?)\s+(?:from\s+(?:now|today)|after|later|ahead))',
        q
    )
    if delta_m:
        val_str = delta_m.group(1) or delta_m.group(3)
        unit = delta_m.group(2) or delta_m.group(4)
        val = int(val_str)
        if "day" in unit:
            target = now + timedelta(days=val)
        elif "week" in unit:
            target = now + timedelta(weeks=val)
        elif "month" in unit and _HAS_DATEUTIL:
            target = now + _relativedelta(months=val)
        elif "year" in unit and _HAS_DATEUTIL:
            target = now + _relativedelta(years=val)
        else:
            target = now + timedelta(days=val * 30)
        return f"{val} {unit} from today will be {target.strftime('%A, %B %d, %Y')}."

    # 4. Past date delta: "what date was 20 days ago"
    past_delta_m = re.search(
        r'(?:what\s+date\s+was\s+)?(\d+)\s*(days?|weeks?|months?|years?)\s+ago',
        q
    )
    if past_delta_m:
        val = int(past_delta_m.group(1))
        unit = past_delta_m.group(2)
        if "day" in unit:
            target = now - timedelta(days=val)
        elif "week" in unit:
            target = now - timedelta(weeks=val)
        elif "month" in unit and _HAS_DATEUTIL:
            target = now - _relativedelta(months=val)
        elif "year" in unit and _HAS_DATEUTIL:
            target = now - _relativedelta(years=val)
        else:
            target = now - timedelta(days=val * 30)
        return f"{val} {unit} ago was {target.strftime('%A, %B %d, %Y')}."

    # 5. Day of the week for a specific historical or future date: "what day was 15 August 1947"
    day_m = re.search(r'\b(?:what\s+day\s+(?:was|will\s+be|is)\s+(?:it\s+on\s+)?)(.+)$', q)
    if day_m and _HAS_DATEUTIL:
        date_str = day_m.group(1).strip().rstrip("?")
        try:
            parsed = _date_parser.parse(date_str, fuzzy=True)
            return f"{parsed.strftime('%B %d, %Y')} was a {parsed.strftime('%A')}."
        except Exception:
            pass

    return f"Today is {now.strftime('%A, %B %d, %Y')}, and the current time is {now.strftime('%I:%M %p')}."
