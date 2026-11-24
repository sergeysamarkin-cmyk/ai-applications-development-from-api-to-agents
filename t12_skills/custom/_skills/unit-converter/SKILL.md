---
name: unit-converter
description: "Converts values between units of length, weight, volume, area, speed, time, data, pressure, energy, and temperature. Use it when the user asks to convert a value or asks how many units of one kind are in another, for example 98.6 F to Celsius, 1.5 TB to MB, 3 cups to ml, or 127 km/h to mph and knots."
license: Apache-2.0
compatibility: Requires the execute_code tool (MCP Python Code Interpreter).
metadata:
  author: ai-powered-apps-development-expert
  version: "1.0"
allowed-tools: execute_code
---

# Unit Converter

Converts a value from one unit to another. The conversion logic is in `scripts/convert.py`. You run it with `execute_code`.

Supported units and invocation examples are in [examples.md](examples.md). How `execute_code` keeps state is explained in [references/how-code-execution-works.md](references/how-code-execution-works.md).

## Workflow

### Step 1: Load the script (first call, session_id = "")

Call `execute_code` with:

- `script_path`: `unit-converter/scripts/convert.py`
- `code`: the conversion code from Step 2
- `session_id`: `""`

The result is JSON. If it has `success: true`, read `session_info.session_id` and save it for reuse.

### Step 2: Write the conversion call

The code must call `convert_units(value, from_unit, to_unit)` and print the category, input, and result. Use `fmt()` from the script to format the number. Example for "Convert 98.6°F to Celsius":

```python
value, category = convert_units(98.6, "fahrenheit", "celsius")
print(f"Category: {category}")
print(f"Input:    98.6 fahrenheit")
print(f"Result:   {fmt(value)} celsius")
```

### Step 3: Return output

Return the printed output as it is. Do not convert the numbers yourself.

For a request with several targets, such as "98.6°F to Celsius and Kelvin", run one call per target in the same session, or print all results in one call.

### Step 4: Reuse session

On follow-up conversions, skip Step 1. Pass only `code` and the saved `session_id`. The script stays loaded in the session, so `convert_units` and `fmt` are still available.

### Step 5: Error handling

- Unknown unit or incompatible categories (for example kg to meters): report the error text and list the supported units from [examples.md](examples.md).
- Invalid number: ask the user to clarify the value.
- Expired session (the result says the session was not found or has expired): silently restart from Step 1 with `session_id = ""`.
