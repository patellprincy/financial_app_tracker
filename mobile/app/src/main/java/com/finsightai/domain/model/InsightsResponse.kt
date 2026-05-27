package com.finsightai.domain.model

data class InsightsResponse(
    val summary: InsightSummary,
    val items: List<InsightItem>
)
