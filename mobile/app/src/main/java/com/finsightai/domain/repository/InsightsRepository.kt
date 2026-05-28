package com.finsightai.domain.repository

import com.finsightai.domain.model.InsightsResponse

interface InsightsRepository {
    suspend fun getInsights(): Result<InsightsResponse>
}
