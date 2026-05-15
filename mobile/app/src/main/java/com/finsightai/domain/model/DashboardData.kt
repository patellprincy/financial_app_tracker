package com.finsightai.domain.model

data class DashboardSummary(
    val totalExpenses: Double = 0.0,
    val totalIncome: Double = 0.0,
    val topCategory: String = "",
    val spendingTrend: String = "Stable"
)

data class CategoryBreakdown(
    val categoryId: Int,
    val categoryName: String,
    val amount: Double,
    val percentage: Float
)

data class DashboardData(
    val summary: DashboardSummary = DashboardSummary(),
    val categoryBreakdown: List<CategoryBreakdown> = emptyList(),
    val recentTransactions: List<Transaction> = emptyList()
)
