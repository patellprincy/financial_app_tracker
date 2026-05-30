package com.finsightai.domain.model

data class StatementUploadResponse(
    val uploadId: String,
    val fileName: String,
    val status: String,
    val totalTransactions: Int,
    val transactions: List<ExtractedTransaction>,
    val parseError: String?
)

data class ExtractedTransaction(
    val transactionDate: String,
    val description: String,
    val amount: Double,
    val rawText: String
)
