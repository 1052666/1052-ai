# Calculator Skill

This skill provides basic mathematical operations. It can be used to perform addition, subtraction, multiplication, and division.

## Available Functions

All functions are located in the file `calc.py`.

### 1. Addition
*   **Function Name**: `add`
*   **Description**: Calculates the sum of two numbers.
*   **Arguments**:
    *   `a` (number): The first number.
    *   `b` (number): The second number.
*   **Example Usage**:
    To calculate 3 + 5, call `execute_skill_function` with:
    ```json
    {
      "skill_name": "calculator",
      "file_name": "calc.py",
      "function_name": "add",
      "kwargs": {"a": 3, "b": 5}
    }
    ```

### 2. Subtraction
*   **Function Name**: `subtract`
*   **Description**: Calculates the difference (a - b).
*   **Arguments**:
    *   `a` (number): Minuend.
    *   `b` (number): Subtrahend.

### 3. Multiplication
*   **Function Name**: `multiply`
*   **Description**: Calculates the product (a * b).
*   **Arguments**:
    *   `a` (number): Multiplicand.
    *   `b` (number): Multiplier.

### 4. Division
*   **Function Name**: `divide`
*   **Description**: Calculates the quotient (a / b).
*   **Arguments**:
    *   `a` (number): Dividend.
    *   `b` (number): Divisor (cannot be 0).
