package com.finsightai.ui.components

import java.util.Locale

/**
 * Display-only helpers. Always render amounts as unsigned dollar values.
 *
 * Backend amounts are signed (expenses < 0, income > 0). These functions
 * apply abs() so the UI never shows a leading minus sign. Transaction type,
 * color, and category labels carry the income/expense context instead.
 */

/** "$199" — whole dollars, no sign. Used for dashboard summaries and cards. */
fun formatAmount(amount: Double): String =
    "\$${String.format(Locale.getDefault(), "%,.0f", kotlin.math.abs(amount))}"

/** "$8.42" — two decimal places, no sign. Used for transaction detail views. */
fun formatAmountWithCents(amount: Double): String =
    "\$${String.format(Locale.getDefault(), "%,.2f", kotlin.math.abs(amount))}"
