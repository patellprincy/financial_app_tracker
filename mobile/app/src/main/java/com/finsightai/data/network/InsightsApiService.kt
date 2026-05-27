package com.finsightai.data.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.GET

interface InsightsApiService {
    @GET("insights")
    suspend fun getInsights(): InsightsResponseDto
}

@Serializable
data class InsightsResponseDto(
    val summary: InsightSummaryDto,
    val items: List<InsightItemDto>
)

@Serializable
data class InsightSummaryDto(
    @SerialName("total_insights") val totalInsights: Int,
    @SerialName("unusual_count") val unusualCount: Int,
    @SerialName("tips_count") val tipsCount: Int,
    @SerialName("pattern_count") val patternCount: Int
)

@Serializable
data class InsightItemDto(
    val id: Int,
    val type: String,
    val title: String,
    val description: String,
    val value: String,
    @SerialName("transaction_id") val transactionId: Int? = null,
    val severity: String,
    @SerialName("created_at") val createdAt: String
)
