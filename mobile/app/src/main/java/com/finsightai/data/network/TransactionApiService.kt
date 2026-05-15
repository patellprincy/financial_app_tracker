package com.finsightai.data.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface TransactionApiService {

    @POST("transactions/manual")
    suspend fun addManualTransaction(
        @Body request: ManualTransactionRequest
    ): TransactionDto

    @GET("transactions")
    suspend fun getTransactions(): List<TransactionDto>

    @GET("transactions/dashboard")
    suspend fun getDashboard(): DashboardDto
}

@Serializable
data class ManualTransactionRequest(
    val merchant: String,
    val amount: Double,
    val notes: String
)

@Serializable
data class TransactionDto(
    val id: Int,
    @SerialName("user_id") val userId: String,
    val merchant: String,
    val amount: Double,
    val notes: String,
    @SerialName("transaction_type") val transactionType: String,
    @SerialName("category_id") val categoryId: Int,
    @SerialName("category_name") val categoryName: String,
    val confidence: Double,
    val reason: String,
    @SerialName("created_at") val createdAt: String
)

@Serializable
data class DashboardDto(
    @SerialName("total_expense") val totalExpense: Double,
    @SerialName("total_income") val totalIncome: Double,
    @SerialName("category_breakdown") val categoryBreakdown: List<CategoryBreakdownDto>,
    @SerialName("recent_transactions") val recentTransactions: List<TransactionDto>
)

@Serializable
data class CategoryBreakdownDto(
    @SerialName("category_id") val categoryId: Int,
    @SerialName("category_name") val categoryName: String,
    val amount: Double,
    val percentage: Double
)