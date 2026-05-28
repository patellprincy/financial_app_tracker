package com.finsightai.domain.model

data class InsightSummary(
    val totalInsights: Int,
    val unusualCount: Int,
    val tipsCount: Int,
    val patternCount: Int
)
