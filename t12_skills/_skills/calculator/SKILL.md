---
name: calculator
description: Safely evaluates math expressions with the calculator script. Use it when the user asks to calculate, compute, evaluate, or solve arithmetic, powers, roots, logarithms, trigonometry, or expressions with pi and e. Do not compute such results in your head.
---

# Calculator Skill

## Quick Start

Run the script from the shell with the whole expression in double quotes:

```
python /skills/calculator/scripts/calculate.py "<expression>"
```

Example:

```
python /skills/calculator/scripts/calculate.py "(144 * 3) + sqrt(256) - 2^8"
```

## Supported Operations

- Arithmetic: `+`, `-`, `*`, `/`
- Floor division and modulo: `//`, `%`
- Power / exponentiation: `^` or `**` (the script converts `^` to `**`)
- Square root: `sqrt(x)`
- Trigonometric functions: `sin(x)`, `cos(x)`, `tan(x)` (angles in radians)
- Logarithms: `log(x)` (natural), `log10(x)`
- Other functions: `abs(x)`, `round(x)`, `floor(x)`, `ceil(x)`
- Constants: `pi`, `e`
- Grouping with parentheses

Anything else (variables, imports, other functions) is rejected by the script.

## Workflow

1. Take the math from the user request and write it as one expression. Use `^` or `**` for powers and `pi` for π.
2. Run the script with the expression in double quotes, as shown in Quick Start.
3. Read the output:
   - `Result: <value>` means success. Report the value to the user, and show the expression you calculated.
   - `Error: ...` means the expression is invalid or unsupported. Explain the problem and ask the user for a corrected expression.
   - Division by zero is reported as an error. Say so clearly instead of guessing a value.
4. Do not change the script output. Return the result as it is, with the expression.

## Examples

| User request                 | Expression to run             | Expected result (approx.) |
|------------------------------|-------------------------------|---------------------------|
| What is 2^10?                | `2^10`                        | 1024                      |
| What is sin(pi / 2) + cos(0)? | `sin(pi / 2) + cos(0)`       | 2                         |
| What is 2^10 + sqrt(144)?    | `2^10 + sqrt(144)`            | 1036                      |
