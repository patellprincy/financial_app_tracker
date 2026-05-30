package com.finsightai.data.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import okhttp3.MultipartBody
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part

interface StatementApiService {

    @Multipart
    @POST("statements/upload")
    suspend fun uploadStatement(
        @Part file: MultipartBody.Part
    ): StatementUploadResponseDto
}

@Serializable
data class StatementUploadResponseDto(
    @SerialName("upload_id") val uploadId: String,
    @SerialName("file_name") val fileName: String,
    val status: String,
    @SerialName("total_transactions") val totalTransactions: Int,
    val transactions: List<ExtractedTransactionDto>,
    @SerialName("parse_error") val parseError: String? = null
)

@Serializable
data class ExtractedTransactionDto(
    @SerialName("transaction_date") val transactionDate: String,
    val description: String,
    val amount: Double,
    @SerialName("raw_text") val rawText: String
)
