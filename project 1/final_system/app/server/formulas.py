"""
formulas.py — معادلات الخامات
-----------------------------
كل نوع شغل ليه "تركيبة": خامات وكمية كل خامة للقطعة الواحدة. الكمية رقم ثابت أو معادلة بالمقاسات.

شكل المعادلة (بالعربى زى ما بتتكتب فى الإعدادات):
    تقريب(([جاكيت الطول] + [بنطلون الطول] + [جاكيت طول الكم]) ÷ 100 + 0.4, 0.25)
  - [المجموعة اسم المقاس]  ← قيمة المقاس من طلب العميل (بالسنتيمتر زى ما اتكتب)
  - + − × ÷ ( )  والأرقام العربى أو الإنجليزى
  - أكبر(أ، ب)  أصغر(أ، ب)
  - لو(شرط، القيمة لو صح، القيمة لو غلط)   مثال: لو([جاكيت الصدر] > 110، 0.25، 0)
  - تقريب(القيمة، 0.25)  ← بيقرّب لفوق لأقرب ربع متر
المعادلة بتتحسب بأمان (مفيش أى أوامر تانية ممكن تتنفذ).
"""

import ast
import math
import re

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫،×÷−", "0123456789.,*/-")
FUNCTIONS = {"أكبر": "max_", "أصغر": "min_", "لو": "if_", "تقريب": "up_"}
_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp, ast.Call, ast.Name, ast.Load,
                  ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd, ast.Gt, ast.GtE, ast.Lt,
                  ast.LtE, ast.Eq, ast.NotEq, ast.And, ast.Or)


class FormulaError(Exception):
    """المعادلة مكتوبة غلط (رسالة عربى)."""


class MissingMeasure(Exception):
    """مقاس مستخدم فى المعادلة مش متسجل للعميل ده."""


def _up(value, step=1):
    step = float(step) or 1
    return math.ceil(round(float(value) / step, 9)) * step


_ENV = {"max_": max, "min_": min, "if_": lambda cond, a, b=0: a if cond else b, "up_": _up}


def _normalize_name(text):
    return " ".join(str(text).replace(":", " ").replace("|", " ").split())


def measure_names(fields):
    """{"جاكيت الطول": "جاكيت|الطول"} من خانات المقاسات."""
    return {_normalize_name(f"{f['grp']} {f['name']}"): f"{f['grp']}|{f['name']}" for f in fields}


def compile_formula(text, names):
    """بيتأكد من المعادلة وبيرجّع (الكود، المقاسات المستخدمة). غلط ← FormulaError."""
    src = str(text or "").strip().translate(_DIGITS)
    if not src:
        raise FormulaError("اكتب المعادلة أو رقم")
    used = []

    def var(match):
        name = _normalize_name(match.group(1))
        key = names.get(name)
        if key is None:
            raise FormulaError(f"المقاس «{match.group(1).strip()}» مش موجود فى خانات المقاسات "
                               "(اكتبه كده: [جاكيت الطول])")
        if key not in used:
            used.append(key)
        return f"m{used.index(key)}"

    src = re.sub(r"\[([^\]]*)\]", var, src)
    for ar, py in FUNCTIONS.items():
        src = re.sub(rf"{ar}\s*\(", f"{py}(", src)
    src = re.sub(r"(?<![<>=!])=(?!=)", "==", src)       # = لوحدها جوه الشرط = يساوى
    src = src.replace(" و ", " and ").replace(" او ", " or ").replace(" أو ", " or ")
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        raise FormulaError("المعادلة مكتوبة غلط — اتأكد من الأقواس والعلامات")
    allowed_names = set(_ENV) | {f"m{i}" for i in range(len(used))}
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise FormulaError("المعادلة فيها حاجة مش مسموحة")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise FormulaError(f"«{node.id}» مش مفهومة — المقاسات تتكتب بين [ ] والدوال: "
                               "أكبر، أصغر، لو، تقريب")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise FormulaError("المعادلة فيها كلام مش أرقام")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in _ENV):
            raise FormulaError("الدوال المسموحة: أكبر، أصغر، لو، تقريب")
    return compile(tree, "<formula>", "eval"), used


def measure_value(text):
    try:
        return float(str(text).strip().translate(_DIGITS).replace(",", "."))
    except (TypeError, ValueError):
        return None


def evaluate(text, names, measurements):
    """الكمية للقطعة الواحدة. مقاس ناقص ← MissingMeasure، معادلة غلط ← FormulaError."""
    code, used = compile_formula(text, names)
    env = dict(_ENV)
    for i, key in enumerate(used):
        value = measure_value((measurements or {}).get(key))
        if value is None:
            raise MissingMeasure(key.replace("|", " "))
        env[f"m{i}"] = value
    try:
        result = eval(code, {"__builtins__": {}}, env)   # noqa: S307 - الشجرة متفحوصة فوق
    except ZeroDivisionError:
        raise FormulaError("المعادلة فيها قسمة على صفر")
    except TypeError:
        raise FormulaError("فيه دالة ناقصة أرقام (مثال صح: تقريب(2.3، 0.25))")
    try:
        return max(float(result), 0.0)
    except (TypeError, ValueError):
        raise FormulaError("المعادلة مش بتطلّع رقم")


def split_choice(line):
    """'دبل (صفين) = +0.3' ← ('دبل (صفين)', 0.3). الرقم = قماش زيادة بالمتر."""
    name, _, extra = str(line).partition("=")
    value = measure_value(extra.replace("+", "")) if extra.strip() else 0.0
    return name.strip(), value or 0.0
