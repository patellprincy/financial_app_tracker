package com.finsightai.domain.model

data class InsightItem(
    val id: String,
    val title: String,
    val description: String,
    val type: InsightType,
    val value: String = "",
    val transactionId: Int? = null,
    val severity: String = "low",
    val createdAt: String = ""
)

enum class InsightType {
    PATTERN, UNUSUAL, SUGGESTION
}
