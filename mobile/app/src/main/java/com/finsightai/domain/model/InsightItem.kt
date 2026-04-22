package com.finsightai.domain.model

data class InsightItem(
    val id: String,
    val title: String,
    val description: String,
    val type: InsightType,
    val value: String = ""
)

enum class InsightType {
    PATTERN, UNUSUAL, SUGGESTION
}
