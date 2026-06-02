package com.finsightai.data.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import okhttp3.MultipartBody
import retrofit2.http.Body
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path

interface StatementApiService {

    @Multipart
    @POST("statements/upload")
    suspend fun uploadStatement(
        @Part file: MultipartBody.Part
    ): StatementUploadResponseDto

    // Phase 3B: import only the user-approved preview rows. JWT is attached by
    // AuthInterceptor (applied in RetrofitClient.buildRetrofit).
    @POST("statements/{uploadId}/import")
    suspend fun importStatementTransactions(
        @Path("uploadId") uploadId: String,
        @Body request: StatementImportRequestDto
    ): StatementImportResponseDto
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

// ── Phase 3B: import request/response ───────────────────────────────────────

@Serializable
data class StatementImportRequestDto(
    val transactions: List<StatementImportTransactionDto>
)

@Serializable
data class StatementImportTransactionDto(
    @SerialName("transaction_date") val transactionDate: String,
    val description: String,
    val amount: Double,
    @SerialName("raw_text") val rawText: String
)

@Serializable
data class StatementImportResponseDto(
    @SerialName("upload_id") val uploadId: String,
    val status: String,
    @SerialName("imported_transactions") val importedTransactions: Int,
    @SerialName("failed_transactions") val failedTransactions: Int
    // The backend also returns the full imported transactions list; we don't
    // need it on the client (Json.ignoreUnknownKeys=true skips it).
)
