#!/bin/bash

set -euo pipefail

cat > /app/workspace/solution.lean  <<'EOF'

import Library.Theory.Parity
import Library.Tactic.Induction
import Library.Tactic.ModCases
import Library.Tactic.Extra
import Library.Tactic.Numbers
import Library.Tactic.Addarith
import Library.Tactic.Use

def T : ℕ → ℚ
  | 0 => 3
  | n + 1 => T n - 1 / 2 ^ (n + 1)

theorem problemsolution (n : ℕ) : T n ≥ 2 := by
  -- First establish the closed form: T n = 2 + 1 / 2 ^ n
  have closed : T n = 2 + 1 / 2 ^ n := by
    simple_induction n with k IH
    · calc
        T 0 = 3 := by rw [T]
        _ = 2 + (1 / (2 ^ 0)) := by numbers
    · calc
        T (k + 1) = T k - 1 / (2 ^ (k + 1)) := by rw [T]
        _ = 2 + 1 / (2 ^ k) - 1 / (2 ^ (k + 1)) := by rw [IH]
        _ = 2 + 2 / (2 ^ (k + 1)) - 1 / (2 ^ (k + 1)) := by ring
        _ = 2 + 1 / (2 ^ (k + 1)) := by ring
  -- Now show 1 / 2^n ≥ 0 over ℚ to conclude T n ≥ 2
  have hfrac_nonneg : 0 ≤ 1 / (2 : ℚ) ^ n := by
    have hbase : 0 < (2 : ℚ) := by numbers
    have hpow_pos : 0 ≤ (2 : ℚ) ^ n := le_of_lt (pow_pos hbase _)
    exact div_nonneg (show 0 ≤ (1 : ℚ) from by exact zero_le_one) hpow_pos
  have bound : 2 + 1 / (2 : ℚ) ^ n ≥ 2 :=
    le_add_of_nonneg_right hfrac_nonneg
  calc
    T n = 2 + 1 / 2 ^ n := closed
    _ ≥ 2 := bound
EOF
