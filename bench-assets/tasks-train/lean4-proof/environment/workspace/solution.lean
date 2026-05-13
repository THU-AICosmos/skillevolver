
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
