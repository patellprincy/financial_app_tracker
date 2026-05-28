package com.finsightai.data.repository

import android.util.Log
import com.finsightai.data.network.InsightsApiService
import com.finsightai.domain.model.InsightItem
import com.finsightai.domain.model.InsightSummary
import com.finsightai.domain.model.InsightType
import com.finsightai.domain.model.InsightsResponse
import com.finsightai.domain.repository.InsightsRepository
import retrofit2.HttpException

class InsightsRepositoryImpl(
    private val apiService: InsightsApiService
) : InsightsRepository {

    override suspend fun getInsights(): Result<InsightsResponse> = runCatching {
        Log.d("InsightsRepo", "getInsights: calling API")
        val response = apiService.getInsights()
        Log.d("InsightsRepo", "getInsights: success — items=${response.items.size}")

        val summary = InsightSummary(
            totalInsights = response.summary.totalInsights,
            unusualCount = response.summary.unusualCount,
            tipsCount = response.summary.tipsCount,
            patternCount = response.summary.patternCount
        )

        val items = response.items.map { dto ->
            InsightItem(
                id = dto.id.toString(),
                title = dto.title,
                description = dto.description,
                type = dto.type.toInsightType(),
                value = dto.value,
                transactionId = dto.transactionId,
                severity = dto.severity,
                createdAt = dto.createdAt
            )
        }

        InsightsResponse(summary = summary, items = items)
    }.onFailure { ex ->
        when (ex) {
            is HttpException -> Log.e("InsightsRepo", "getInsights: HTTP ${ex.code()} ${ex.message()}")
            else -> Log.e("InsightsRepo", "getInsights: ${ex.javaClass.simpleName} — ${ex.message}")
        }
    }

    private fun String.toInsightType(): InsightType = when (this.lowercase()) {
        "unusual" -> InsightType.UNUSUAL
        "tip" -> InsightType.SUGGESTION
        "pattern" -> InsightType.PATTERN
        else -> InsightType.UNUSUAL
    }
}
