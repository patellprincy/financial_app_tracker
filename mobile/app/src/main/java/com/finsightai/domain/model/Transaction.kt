package com.finsightai.domain.model

import java.time.LocalDate

data class Transaction(
    val id: String,
    val merchant: String,
    val category: TransactionCategory,
    val amount: Double,
    val date: LocalDate,
    val notes: String = "",
    val type: TransactionType = TransactionType.EXPENSE
)

enum class TransactionType {
    INCOME, EXPENSE
}

enum class TransactionCategory(val displayName: String, val emoji: String) {
    FOOD("Food & Dining", "🍔"),
    TRANSPORT("Transport", "🚗"),
    SHOPPING("Shopping", "🛍️"),
    ENTERTAINMENT("Entertainment", "🎬"),
    UTILITIES("Utilities", "⚡"),
    HEALTH("Health", "💊"),
    EDUCATION("Education", "📚"),
    TRAVEL("Travel", "✈️"),
    GROCERIES("Groceries", "🛒"),
    INCOME("Income", "💰"),
    OTHER("Other", "📦")
}
