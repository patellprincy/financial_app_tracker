package com.finsightai.domain.repository

import com.finsightai.domain.model.DashboardData
import com.finsightai.domain.model.Transaction

interface TransactionRepository {
    suspend fun addManualTransaction(merchant: String, amount: Double, notes: String): Result<Transaction>
    suspend fun getTransactions(): Result<List<Transaction>>
    suspend fun getTransactionById(transactionId: String): Result<Transaction>
    suspend fun getDashboard(): Result<DashboardData>
}
