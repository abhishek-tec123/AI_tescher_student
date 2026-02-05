# Sample Math Queries for Progressive vs Degressive Testing

Use these with the intent-based agent (subject: **Math**, class: e.g. **10th**) to test level-up / level-down and response length changes.

---

## Progressive (10 queries – clear/correct questions → NO_CONFUSION)

These should count as **correct** and move toward level up + shorter responses (3 correct → short, 5 correct → very short).

1. What is a linear equation?
2. Explain the Pythagorean theorem.
3. How do we find the area of a triangle?
4. What is the value of sin 90 degrees?
5. Define quadratic equation.
6. How do you solve 2x + 5 = 15?
7. What is the formula for the circumference of a circle?
8. Explain what slope means in a line.
9. What is the difference between mean and median?
10. How do we add two fractions with different denominators?

---

## Degressive (10 queries – show confusion/misconception → CONCEPT_GAP / FORMULA_CONFUSION / PROCEDURAL_ERROR)

These should count as **wrong** and move toward level down + longer responses (3 wrong → short, 5 wrong → long).

1. Is 0 divided by 0 equal to 1?
2. Why is 2 + 3 × 4 equal to 20? (wrong order of operations)
3. Can the square root of a negative number be 5?
4. Is the sum of angles in a triangle always 360 degrees?
5. Is (a + b)² equal to a² + b²?
6. Is cot 90 degrees equal to 0?
7. If x² = 9, then is x always 3?
8. Is the area of a circle 2πr?
9. Is 0.999... less than 1?
10. Do we add exponents when multiplying same base? Like 2³ × 2² = 2⁵? (this one is actually correct – 2³×2²=2⁵; so skip or use: “Is 2³ + 2² = 2⁵?”)

**Alternative degressive (clear misconceptions):**

1. Is 0/0 = 1?
2. So 3 + 4 × 2 = 14, right? (wrong: should be 11)
3. Square root of -4 is 2, correct?
4. Triangle angles add up to 360°, right?
5. (x + y)² = x² + y², isn’t it?
6. Cot 90° is 0, right?
7. If x² = 9 then x = 3 only, right?
8. Area of circle is 2πr, right?
9. 0.999... is less than 1, right?
10. 2³ + 2² = 2⁵, right?

---

## Quick test flow

**Progressive (5 in a row):**  
Send these 5 one after another (same student_id, subject Math) → expect level up + `response_length` short/very short.

- What is a linear equation?
- What is the Pythagorean theorem?
- How do you find the area of a triangle?
- What is sin 90 degrees?
- Define quadratic equation.

**Degressive (5 in a row):**  
Send these 5 one after another → expect level down + `confidence_level` low + `response_length` long.

- Is 0/0 equal to 1?
- Is (a + b)² = a² + b²?
- Is cot 90 degrees equal to 0?
- Triangle angles sum to 360°, right?
- Is the area of a circle 2πr?
