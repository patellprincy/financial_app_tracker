package com.finsightai.domain.model

import java.time.LocalDate

data class Transaction(
    val id: String,
    val merchant: String,
    val categoryId: Int,
    val categoryName: String,
    val amount: Double,
    val date: LocalDate,
    val notes: String = "",
    val type: TransactionType = TransactionType.EXPENSE
)

// enum as only either of the transaction type is to be used
enum class TransactionType {
    INCOME, EXPENSE
}
