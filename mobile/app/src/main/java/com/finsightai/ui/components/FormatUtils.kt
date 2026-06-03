package com.finsightai.ui.components

import java.util.Locale

/**
 * Display-only helpers. Amounts from the backend are always positive —
 * transaction_type ("expense" / "income") carries the direction.
 * No abs() needed; these simply format the value for display.
 */

/** "$199" — whole dollars. Used for dashboard summaries and category cards. */
fun formatAmount(amount: Double): String =
    "\$${String.format(Locale.getDefault(), "%,.0f", amount)}"

/** "$8.42" — two decimal places. Used for transaction detail views. */
fun formatAmountWithCents(amount: Double): String =
    "\$${String.format(Locale.getDefault(), "%,.2f", amount)}"
